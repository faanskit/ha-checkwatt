"""Real HA objects and a local HTTP server; no account credentials are used."""

import base64
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from types import MappingProxyType

from aiohttp import ClientSession, DefaultResolver, web
import pytest
import pytest_asyncio

from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components import checkwatt
from custom_components.checkwatt import api
from custom_components.checkwatt.const import (
    CONF_CM10_SENSOR,
    CONF_CWR_NAME,
    CONF_POWER_SENSORS,
    CONF_PUSH_CW_TO_RANK,
)


def jwt(expires_in=3600):
    payload = {
        "exp": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).timestamp()
    }
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )
    return f"header.{encoded}.signature"


@pytest.fixture
def entry():
    return ConfigEntry(
        state=ConfigEntryState.SETUP_IN_PROGRESS,
        version=1,
        minor_version=1,
        domain="checkwatt",
        title="Regression account",
        source="user",
        unique_id="regression",
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
        data={"username": "test@example.invalid", "password": "dummy"},
        options={
            CONF_CM10_SENSOR: False,
            CONF_POWER_SENSORS: False,
            CONF_PUSH_CW_TO_RANK: False,
            CONF_CWR_NAME: "",
        },
    )


@pytest_asyncio.fixture
async def hass(tmp_path, monkeypatch):
    instance = HomeAssistant(str(tmp_path))
    frame.async_setup(instance)
    instance.config_entries = ConfigEntries(instance, {})
    # The tests use loopback HTTP only, so avoid booting zeroconf for DNS.
    monkeypatch.setattr(
        "homeassistant.helpers.aiohttp_client._async_make_resolver",
        lambda hass: DefaultResolver(),
    )
    yield instance
    session = async_get_clientsession(instance)
    await instance.async_stop()
    if not session.closed:
        await ClientSession.close(session)


@pytest_asyncio.fixture
async def backend(monkeypatch):
    calls = Counter()
    failures = {}
    managers = []

    async def handle(request):
        path = request.path
        calls[path] += 1
        if path in failures:
            return web.Response(status=failures[path], headers={"Retry-After": "600"})
        if path == "/ha-killswitch.txt":
            return web.Response(text="0")
        if path in ("/user/Login", "/user/RefreshToken"):
            return web.json_response(
                {
                    "JwtToken": jwt(),
                    "RefreshToken": "refresh",
                    "RefreshTokenExpires": (
                        datetime.now(timezone.utc) + timedelta(days=1)
                    ).isoformat(),
                }
            )
        if path == "/controlpanel/CustomerDetail":
            return web.json_response(
                {
                    "Id": 42,
                    "FirstName": "Test",
                    "LastName": "Account",
                    "StreetAddress": "Test street",
                    "ZipCode": "12345",
                    "City": "Test",
                    "Meter": [
                        {
                            "InstallationType": "SoC",
                            "DisplayName": "Test battery",
                            "ResellerId": 1,
                            "ElhandelsbolagId": 2,
                            "RpiSerial": "TEST",
                        }
                    ],
                }
            )
        if path == "/ems/energyflow":
            return web.json_response(
                {"BatteryNow": 1, "GridNow": 2, "SolarNow": 3, "BatterySoC": 50}
            )
        if path == "/controlpanel/elhandelsbolag":
            return web.json_response([{"Id": 2, "DisplayName": "Test provider"}])
        if path == "/Site/SiteIdBySerial":
            return web.json_response({"SiteId": 42})
        if path.startswith("/revenue/"):
            return web.json_response(
                {"Revenue": [{"NetRevenue": 10}, {"NetRevenue": 20}]}
            )
        if path == "/ems/PeakBoughtMonth":
            return web.json_response({"HourPeak": 1})
        raise AssertionError(f"Unexpected API request: {request.method} {path}")

    application = web.Application()
    application.router.add_route("*", "/{path:.*}", handle)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    base_url = f"http://127.0.0.1:{runner.addresses[0][1]}"

    original_request = ClientSession._request

    async def request(session, method, url, **kwargs):
        if str(url) == "https://checkwatt.se/ha-killswitch.txt":
            url = base_url + "/ha-killswitch.txt"
        assert str(url).startswith(base_url), f"External HTTP request blocked: {url}"
        return await original_request(session, method, url, **kwargs)

    monkeypatch.setattr(ClientSession, "_request", request)
    original_factory = api.create_checkwatt_manager

    def factory(*args, **kwargs):
        manager = original_factory(*args, **kwargs)
        manager.base_url = base_url
        managers.append(manager)
        return manager

    monkeypatch.setattr(api, "create_checkwatt_manager", factory)
    monkeypatch.setattr(checkwatt, "create_checkwatt_manager", factory)
    from custom_components.checkwatt import config_flow

    monkeypatch.setattr(config_flow, "create_checkwatt_manager", factory)
    try:
        yield calls, failures, managers
    finally:
        await runner.cleanup()


@pytest_asyncio.fixture
async def coordinator(hass, entry, backend):
    instance = checkwatt.CheckwattCoordinator(hass, entry)
    yield instance
    await instance.async_shutdown()
