# HA integration regressions

Run these tests inside the supported HA images, with a pyCheckwatt wheel already
installed. The tests require Python 3.13+, pytest 8.4.2 and pytest-asyncio 1.1.1.
The provided Dockerfile supplies HA and these dependencies.

Use a separate build directory containing `artifacts/*.whl`; never use a live HA
configuration as the test config. This task uses `C:\Users\jensh\source\ha-test`.
The existing `ha-test` service and its config are not used by these containers.

Artifacts used during development:

- The unmodified released `pycheckwatt-0.2.11-py3-none-any.whl` from PyPI.
- A wheel built from library commit `490e481`, with only its version changed in
  a separate source copy to `0.2.12+localtest`. This exercises the agreed future
  version boundary; it is not a published release. Use the real 0.2.12 wheel for
  the eventual release checks.

Example from the build directory, with the repository next to it under `repos`:

```powershell
docker build -f ../repos/ha-checkwatt/tests/Dockerfile --build-arg HA_VERSION=2025.12.0 --build-arg LIBRARY_WHEEL=pycheckwatt-0.2.12+localtest-py3-none-any.whl -t ha-checkwatt-regression:candidate .
docker run --rm --network none --env CHECKWATT_EXPECT_PERSISTENT_AUTH=true --mount "type=bind,source=C:/Users/jensh/source/repos/ha-checkwatt,target=/workspace,readonly" ha-checkwatt-regression:candidate
```

Repeat with HA 2026.9.0 for the current release. For the legacy runtime test,
select the 0.2.11 wheel, add build argument
`LEGACY_METADATA_WORKAROUND=--ignore-requires-python`, and set
`CHECKWATT_EXPECT_PERSISTENT_AUTH=false` when running the container. This override
is for legacy runtime regression tests only, not production installation.
Tests for functionality absent in the legacy wheel are explicitly skipped.

The environment variable is required so an unexpected library version cannot
silently exercise the wrong rollout path. The tests never use account secrets;
all HTTP requests must target the local fake server.

## Recorded local verification (2026-09-07)

| HA release | Candidate 0.2.12+localtest | Released 0.2.11 runtime |
| --- | --- | --- |
| 2025.12.0 | 15 passed | 8 passed, 7 feature-specific skips |
| 2026.9.0 | 15 passed | 8 passed, 7 feature-specific skips |

Black, Flake8 and `git diff --check` passed. The legacy runs used the explicit
metadata override described above. Candidate installation used no override.
HA emitted dependency deprecation warnings; the tests reported no failures.
These results cover the fake-server regression suite, not live account or
frontend testing, and must be repeated with the actual published library before
the enforcing release.
