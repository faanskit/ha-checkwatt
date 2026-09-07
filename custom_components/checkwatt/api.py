"""Compatibility helpers for the pyCheckwatt API."""

from importlib.metadata import PackageNotFoundError, version

from packaging.version import Version
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
    # Earlier development builds exposed the exception before retained revenue
    # was safe. The stabilized release is the persistence boundary.
    try:
        PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH = Version(
            version("pycheckwatt")
        ) >= Version("0.2.12")
    except PackageNotFoundError:
        PYCHECKWATT_SUPPORTS_PERSISTENT_AUTH = False


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
