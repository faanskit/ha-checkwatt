"""Compatibility helpers for the pyCheckwatt API."""

from pycheckwatt import CheckwattManager

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from pycheckwatt import CheckwattRateLimitError
except ImportError:
    PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH = False

    class CheckwattRateLimitError(Exception):
        """Placeholder that cannot be raised by legacy pyCheckwatt."""

else:
    PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH = True


def create_checkwatt_manager(
    hass: HomeAssistant,
    username: str,
    password: str,
    application: str = "pyCheckwatt",
) -> CheckwattManager:
    """Create a manager using optional APIs only when they are available."""
    if PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH:
        return CheckwattManager(
            username,
            password,
            application,
            session=async_get_clientsession(hass),
            raise_on_rate_limit=True,
        )

    return CheckwattManager(username, password, application)
