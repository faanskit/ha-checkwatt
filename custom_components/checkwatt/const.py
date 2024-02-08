"""Constants for the CheckWatt integration."""

from typing import Final

DOMAIN = "checkwatt"
INTEGRATION_NAME = "ha-checkwatt"

# Update interval for regular sensors is once every minute
CONF_UPDATE_INTERVAL_ALL = 1
CONF_UPDATE_INTERVAL_MONETARY = 15
ATTRIBUTION = "Data provided by CheckWatt EnergyInBalance"
MANUFACTURER = "CheckWatt"
CHECKWATT_MODEL = "CheckWatt"

CONF_POWER_SENSORS: Final = "show_details"
CONF_PUSH_CW_TO_RANK: Final = "push_to_cw_rank"
CONF_CM10_SENSOR: Final = "cm10_sensor"
CONF_CWR_NAME: Final = "cwr_name"

# Misc
P_UNKNOWN = "Unknown"

# Temp Test
BASIC_TEST = False

# CheckWatt Sensor Attributes
# NOTE Keep these names aligned with strings.json
#
C_ADR = "street_address"
C_BATTERY_POWER = "battery_power"
C_CITY = "city"
C_CM10_VERSION = "cm10_version"
C_DAILY_AVERAGE = "daily_average"
C_DISPLAY_NAME = "display_name"
C_DSO = "dso"
C_GRID_POWER = "grid_power"
C_ENERGY_PROVIDER = "energy_provider"
C_FCRD_DATE = "fcr_d_date"
C_FCRD_INFO = "fcr_d_info"
C_FCRD_STATUS = "fcr_d_status"
C_MONTH_ESITIMATE = "month_estimate"
C_NEXT_UPDATE_TIME = "next_update"
C_PRICE_ZONE = "price_zone"
C_RESELLER_ID = "reseller_id"
C_SOLAR_POWER = "solar_power"
C_UPDATE_TIME = "last_update"
C_TOMORROW_REVENUE = "tomorrow_net_revenue"
C_VAT = "vat"
C_ZIP = "zip_code"
C_CHARGE_PEAK_AC = "charge_peak_ac"
C_CHARGE_PEAK_DC = "charge_peak_dc"
C_DISCHARGE_PEAK_AC = "discharge_peak_ac"
C_DISCHARGE_PEAK_DC = "discharge_peak_dc"
C_MONTHLY_GRID_PEAK_POWER = "monthly_grid_peak_power"

# CheckWatt Event Signals
EVENT_SIGNAL_FCRD = "fcrd"
