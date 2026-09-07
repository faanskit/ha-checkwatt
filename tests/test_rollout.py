"""Run against released legacy and candidate wheels on actual HA releases."""

import importlib.util
import os
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components import checkwatt
from custom_components.checkwatt import api, config_flow
from custom_components.checkwatt.const import CONF_UPDATE_INTERVAL_MONETARY, DOMAIN

from conftest import jwt


def test_installed_wheel_selects_expected_lifecycle():
    assert api.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH is (
        os.environ["CHECKWATT_EXPECT_PERSISTENT_AUTH"] == "true"
    )


def test_older_development_version_does_not_enable_persistence():
    spec = importlib.util.spec_from_file_location("api_under_test", api.__file__)
    module = importlib.util.module_from_spec(spec)
    with patch("importlib.metadata.version", return_value="0.2.11"):
        spec.loader.exec_module(module)
    assert module.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH is False


@pytest.mark.asyncio
async def test_repeated_polls_keep_revenue_stable(coordinator, backend, hass):
    calls, _, managers = backend
    await coordinator._async_update_data()
    # Fetch the monetary group twice, including the real library calculations.
    first = await coordinator._async_update_data()
    coordinator.update_all = 0
    second = await coordinator._async_update_data()
    assert first["monthly_net_revenue"] == second["monthly_net_revenue"] == 30
    assert first["annual_net_revenue"] == second["annual_net_revenue"]
    assert first["month_estimate"] == second["month_estimate"]
    if api.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH:
        assert len(managers) == 1
        assert calls["/user/Login"] == calls["/ha-killswitch.txt"] == 1
        assert managers[0].session is async_get_clientsession(hass)
        assert not managers[0].session.closed
    else:
        assert len(managers) == calls["/user/Login"] == 3
        assert all(manager.session.closed for manager in managers)


@pytest.mark.asyncio
async def test_expired_token_refreshes_without_password(coordinator, backend):
    if not api.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH:
        pytest.skip("Legacy wheel has no token-refresh API")
    calls, _, _ = backend
    await coordinator._async_update_data()
    coordinator.client.jwt_token = jwt(-60)
    await coordinator._async_update_data()
    assert calls["/user/Login"] == calls["/user/RefreshToken"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_refresh_failure_does_not_send_password(coordinator, backend, status):
    if not api.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH:
        pytest.skip("Legacy wheel has no token-refresh API")
    calls, failures, _ = backend
    await coordinator._async_update_data()
    coordinator.client.jwt_token = jwt(-60)
    failures["/user/RefreshToken"] = status
    with pytest.raises(UpdateFailed) as error:
        await coordinator._async_update_data()
    if status == 429:
        assert error.value.retry_after == 600
    assert calls["/user/Login"] == calls["/user/RefreshToken"] == 1


@pytest.mark.asyncio
async def test_interrupted_initialization_is_retried(coordinator, backend):
    if not api.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH:
        pytest.skip("Legacy wheel does not raise typed throttling")
    _, failures, _ = backend
    failures["/controlpanel/elhandelsbolag"] = 429
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.is_boot is True
    failures.clear()
    result = await coordinator._async_update_data()
    assert result["energy_provider"] == "Test provider"
    assert coordinator._id == 42
    assert coordinator.is_boot is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_failed_revenue_is_retried_on_next_poll(coordinator, backend, status):
    calls, failures, _ = backend
    await coordinator._async_update_data()
    failures["/revenue/42"] = status
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_all == 0
    assert coordinator.fcrd_month_net_revenue is None
    failed_calls = calls["/revenue/42"]
    failures.clear()
    result = await coordinator._async_update_data()
    assert calls["/revenue/42"] > failed_calls
    assert result["monthly_net_revenue"] == 30
    assert coordinator.update_all == CONF_UPDATE_INTERVAL_MONETARY - 1


@pytest.mark.asyncio
async def test_poll_throttling_reaches_ha_scheduler(coordinator, backend):
    if not api.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH:
        pytest.skip("Legacy wheel cannot expose Retry-After")
    _, failures, _ = backend
    await coordinator.async_config_entry_first_refresh()
    unsubscribe = coordinator.async_add_listener(lambda: None)
    failures["/controlpanel/CustomerDetail"] = 429
    try:
        with patch.object(coordinator, "_schedule_refresh") as schedule:
            await coordinator.async_refresh()
            assert coordinator.last_update_success is False
            assert coordinator._retry_after == 600
            schedule.assert_called_once()
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_setup_throttling_uses_config_entry_retry(coordinator, backend):
    _, failures, _ = backend
    failures["/controlpanel/CustomerDetail"] = 429
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()


@pytest.mark.asyncio
async def test_config_flow_success_and_rejected_credentials(hass, entry, backend):
    _, failures, _ = backend
    await config_flow.validate_input(hass, entry.data)
    failures["/user/Login"] = 401
    with pytest.raises(config_flow.InvalidAuth):
        await config_flow.validate_input(hass, entry.data)


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["/user/Login", "/ha-killswitch.txt"])
async def test_config_flow_throttling_is_not_invalid_auth(
    hass, entry, backend, endpoint
):
    if not api.PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH:
        pytest.skip("Legacy wheel cannot distinguish throttling from False")
    _, failures, _ = backend
    failures[endpoint] = 429
    with pytest.raises(config_flow.CannotConnect):
        await config_flow.validate_input(hass, entry.data)


@pytest.mark.asyncio
async def test_setup_unload_and_setup_again(hass, entry, backend):
    """Exercise integration lifecycle while replacing HA's platform loaders."""
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await checkwatt.async_setup_entry(hass, entry)
        first = hass.data[DOMAIN][entry.entry_id]
        assert await checkwatt.async_unload_entry(hass, entry)
        await first.async_shutdown()
        assert entry.entry_id not in hass.data[DOMAIN]
        assert not async_get_clientsession(hass).closed
        assert await checkwatt.async_setup_entry(hass, entry)
        second = hass.data[DOMAIN][entry.entry_id]
        assert second is not first
        assert await checkwatt.async_unload_entry(hass, entry)
        await second.async_shutdown()
        assert not async_get_clientsession(hass).closed
