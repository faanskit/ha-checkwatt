"""Constants for the Checkwatt integration."""
from typing import Final

DOMAIN = "checkwatt"
CONF_MONITORED_SITES = "monitored_sites"

# Update interval for regular sensors is once every minute
# For FCR-D since it is slow and resource consuming, is set to once per 15 minute
CONF_UPDATE_INTERVAL = 1
CONF_UPDATE_INTERVAL_FCRD = 15
ATTRIBUTION = "Data provided by Checkwwatt EnergyInBalance"
MANUFACTURER = "Checkwatt"

CONF_DETAILED_SENSORS: Final = "show_details"
CONF_DETAILED_ATTRIBUTES: Final = "show_detailed_attributes"


# Misc
P_UNKNOWN = "Unknown"

# Checkwatt Sensor Attributes
CHECKWATT_MODEL = "Checkwatt"
C_ADR = "Street Address"
C_ZIP = "Zip Code"
C_CITY = "City"
C_TOMORROW = "Tomorrow revenue"
C_UPDATE_TIME = "Last update"
C_NEXT_UPDATE_TIME = "Next update"
C_FCRD_STATUS = "FCR-D Status"
C_FCRD_STATE = "FCR-D State"
C_FCRD_DATE = "FCR-D Date"
