# Authentication and HTTP 429 rollout

The preparation release keeps `pycheckwatt~=0.2.11`. It uses a fresh manager on
every update with older libraries and retains a manager only when both the
rate-limit API and package version `>=0.2.12` are present. Version 0.2.12 is the
planned stabilized release; update this boundary if the upstream release number
changes. An exception import alone is not a persistence guarantee.

## Proposed release stages

1. Prepare and test the compatible HA integration. Legacy managers remain fresh
   per poll, while newer managers use HA's shared session, persistent tokens and
   typed throttling. Do not raise the library requirement in this preparation
   change.
2. Publish the stabilized pyCheckwatt release after its PR and release checks
   pass. Use this as a canary phase: explicitly install the released wheel in an
   isolated HA instance, restart HA, and check repeated polling and recovery.
   Merely publishing a newer wheel does not update every existing HA instance.
3. Publish the enforcing HA release with `pycheckwatt~=0.2.12` (or the actual
   agreed stabilized version). This is the stage that makes older installations
   upgrade. Remove the compatibility helper in that release or a later cleanup.

### Two release gates

Home Assistant checks whether installed packages already satisfy the manifest.
An installed 0.2.11 satisfies `~=0.2.11`, so it can remain installed after a
restart. The feature activates when a supported library is actually installed
and the Python process imports it; do not promise automatic upgrades at stage 2.
See HA's `_install_requirements_if_missing` in
[requirements.py](https://github.com/home-assistant/core/blob/2025.12.0/homeassistant/requirements.py).

The published 0.2.11 wheel declares Python `>=3.10,<3.13`, while this HA branch
requires HA 2025.12, whose runtime is Python 3.13 or newer. Therefore the
preparation release cannot be treated as a supported fresh-install release on
that HA version before the compatible library is available. Keep stage 1 as
development/canary preparation, or publish the compatible library before the
first public HA release. Do not recommend overriding Python requirements in
production. If a public HA-first release is essential, supporting an older HA
runtime needs a separate compatibility change and validation.

Publishing pyCheckwatt first and then the enforcing HA release is the simplest
public release order. The preparation stage is still useful for testing both
paths before either release.

## Local validation

The integration tests use real HA coordinator/config-flow objects and real
aiohttp traffic to a loopback fake CheckWatt server. They cover:

- Legacy clients recreated per poll and stable repeated revenue values.
- Supported clients retained, JWT reuse, refresh and shared-session ownership.
- HTTP 429 propagation to HA's scheduled retry, and setup retry separately.
- No password fallback after refresh throttling or server errors.
- Immediate retry of failed monetary fetches at the next eligible poll.
- Config validation and integration setup, unload and setup again.

The lifecycle test stubs HA's platform loaders; it does not claim to validate
entity/platform setup or the HA frontend. There are no live CheckWatt or
CheckWattRank requests. Containers run with external networking disabled and the
source mounted read-only.

See [the regression test instructions](../tests/README.md). Normal candidate
wheel installation must pass without a Python-requirement override. The legacy
runtime test explicitly bypasses 0.2.11's known metadata restriction to test
its behavior in isolation; passing that test is not an installation gate pass.
