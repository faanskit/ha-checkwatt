"""Constants for the CheckWatt integration."""
from typing import Final

DOMAIN = "checkwatt"

# Update interval for regular sensors is once every minute
# For FCR-D since it is slow and resource consuming, is set to once per 15 minute
CONF_UPDATE_INTERVAL = 1
CONF_UPDATE_INTERVAL_FCRD = 15
ATTRIBUTION = "Data provided by CheckWatt EnergyInBalance"
MANUFACTURER = "CheckWatt"
CHECKWATT_MODEL = "CheckWatt"

CONF_DETAILED_SENSORS: Final = "show_details"
CONF_DETAILED_ATTRIBUTES: Final = "show_detailed_attributes"
CONF_PUSH_CW_TO_RANK: Final = "push_to_cw_rankt"

# Misc
P_UNKNOWN = "Unknown"

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
C_DISCHARGE_PEAK = "discharge_peak"
C_DISPLAY_NAME = "display_name"
C_DSO = "dso"
C_ENERGY_PROVIDER = "energy_provider"
C_FCRD_DATE = "fcr_d_date"
C_FCRD_STATE = "fcr_d_state"
C_FCRD_STATUS = "fcr_d_status"
C_NEXT_UPDATE_TIME = "next_update"
C_PRICE_ZONE = "price_zone"
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
