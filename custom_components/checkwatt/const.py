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
C_TOMORROW_GROSS = "Tomorrow Gross Income"
C_TOMORROW_FEES = "Tomorrow Fees"
C_TOMORROW_FEE_RATE = "Tomorrow Fee Rate"
C_TOMORROW_NET = "Tomorrow Net Income"
C_TODAY_GROSS = "Today Gross Income"
C_TODAY_FEES = "Today Fees"
C_TODAY_FEE_RATE = "Today Fee Rate"
C_ANNUAL_GROSS = "Annual Gross Income"
C_ANNUAL_FEES = "Annual Fees"
C_ANNUAL_FEE_RATE = "Annual Fee Rate"


C_UPDATE_TIME = "Last update"
C_NEXT_UPDATE_TIME = "Next update"
C_FCRD_STATUS = "FCR-D Status"
C_FCRD_STATE = "FCR-D State"
C_FCRD_DATE = "FCR-D Date"
C_CHARGE_PEAK = "Charge Peak"
C_DISCHARGE_PEAK = "Discharge Peak"
C_PRICE_ZONE = "Price zone"
C_VAT = "VAT"
