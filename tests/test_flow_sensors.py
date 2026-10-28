"""The flow sensors must be power sensors, or HA rejects kW and hides them from power pickers."""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower

from custom_components.checkwatt.sensor import CHECKWATT_ENERGY_SENSORS


def test_flow_sensors_are_power_measurements():
    for key in ("solar_power", "battery_power", "grid_power"):
        description = CHECKWATT_ENERGY_SENSORS[key]
        assert description.device_class is SensorDeviceClass.POWER, key
        assert description.native_unit_of_measurement == UnitOfPower.KILO_WATT, key
        assert description.state_class is SensorStateClass.MEASUREMENT, key
