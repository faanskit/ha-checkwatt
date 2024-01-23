"""Constants for the CheckWatt integration."""
from typing import Final

DOMAIN = "checkwatt"
INTEGRATION_NAME = "ha-checkwatt"

# Update interval for regular sensors is once every minute
# For FCR-D since it is slow and resource consuming, is set to once per 15 minute
CONF_UPDATE_INTERVAL = 1
CONF_UPDATE_INTERVAL_FCRD = 15
ATTRIBUTION = "Data provided by CheckWatt EnergyInBalance"
MANUFACTURER = "CheckWatt"
CHECKWATT_MODEL = "CheckWatt"

CONF_DETAILED_SENSORS: Final = "show_details"
CONF_DETAILED_ATTRIBUTES: Final = "show_detailed_attributes"
CONF_PUSH_CW_TO_RANK: Final = "push_to_cw_rank"
CONF_CM10_SENSOR = "cm10_sensor"

# Misc
P_UNKNOWN = "Unknown"

# Temp Test
BASIC_TEST = True

# CheckWatt Sensor Attributes
# NOTE Keep these names aligned with strings.json
#
C_ADR = "street_address"
C_ANNUAL_FEES = "annual_fees"
C_ANNUAL_FEE_RATE = "annual_fee_rate"
C_ANNUAL_GROSS = "annual_gross_income"
C_BATTERY_POWER = "battery_power"
C_CHARGE_PEAK = "charge_peak"
C_CITY = "city"
C_CM10_VERSION = "cm10_version"
C_CM10_UNDER_TEST = "cm10_under_test"
C_CM10_STATUS_DATE = "cm10_status_date"
C_DISCHARGE_PEAK = "discharge_peak"
C_DISPLAY_NAME = "display_name"
C_DSO = "dso"
C_GRID_POWER = "grid_power"
C_ENERGY_PROVIDER = "energy_provider"
C_FCRD_DATE = "fcr_d_date"
C_FCRD_INFO = "fcr_d_info"
C_FCRD_STATUS = "fcr_d_status"
C_NEXT_UPDATE_TIME = "next_update"
C_PRICE_ZONE = "price_zone"
C_SOLAR_POWER = "solar_power"
C_TODAY_FEES = "today_fees"
C_TODAY_FEE_RATE = "today_fees_rate"
C_TODAY_GROSS = "today_gross_income"
C_TOMORROW_FEES = "tomorrow_fees"
C_TOMORROW_FEE_RATE = "tomorrow_fee_rate"
C_TOMORROW_GROSS = "tomorrow_gross_income"
C_TOMORROW_NET = "tomorrow_net_income"
C_UPDATE_TIME = "last_update"
C_VAT = "vat"
C_ZIP = "zip_code"
C_CHARGE_PEAK_AC = "charge_peak_ac"
C_CHARGE_PEAK_DC = "charge_peak_dc"
C_DISCHARGE_PEAK_AC = "discharge_peak_ac"
C_DISCHARGE_PEAK_DC = "discharge_peak_dc"


# CheckWatt Event Signals
EVENT_SIGNAL_FCRD = "fcrd"
