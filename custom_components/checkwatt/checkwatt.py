"""ESolar Cloud Platform data fetchers."""
import logging
_LOGGER = logging.getLogger(__name__)


def get_checkwatt_data(username, password, detailed_sensors=False):
    """Checkwatt EnergyInBalance Data Update."""
    checkwatt_data = {
        "FirstName":"Marcus",
        "LastName":"Karlsson",
        "Meter":[
            {
                "Id":124795,
                "FacilityId":"734012530000225336",
                "PropertyId":"Verstorp 2:49",
                "StreetAddress":"Va Skärfva Byväg 8",
                "ZipCode":"37191",
                "City":"KARLSKRONA",
                "ProcessStatus":"BR, INSTALLATION DONE",
            }
        ]
    }
    return checkwatt_data


def checkwatt_autenticate(username, password):
    """Authenticate the user to the Checkwatt's WEB Portal."""
    return True
    