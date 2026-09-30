# Integration tests

Place `pycheckwatt-0.3.0-py3-none-any.whl` in `artifacts/` under a separate
build directory. From that directory, set `$repo` to your ha-checkwatt checkout:

```powershell
$repo = "C:/path/to/ha-checkwatt"
docker build -f "$repo/tests/Dockerfile" --build-arg HA_VERSION=2025.12.0 --build-arg LIBRARY_WHEEL=pycheckwatt-0.3.0-py3-none-any.whl -t ha-checkwatt-tests .
docker run --rm --network none --env CHECKWATT_EXPECT_PERSISTENT_AUTH=true --mount "type=bind,source=$repo,target=/workspace,readonly" ha-checkwatt-tests
```

Repeat with `HA_VERSION=2026.9.0`. Tests use local fake HTTP; platform loading
is stubbed. No live account or HA configuration is needed.

For legacy regression coverage, build with the 0.2.11 wheel and
`--build-arg LEGACY_METADATA_WORKAROUND=--ignore-requires-python`, then run with
`CHECKWATT_EXPECT_PERSISTENT_AUTH=false`. This override is for tests only.
