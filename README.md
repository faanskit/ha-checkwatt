# Home Assistant Checkwatt Custom Integration
This integration uses cloud polling from the Checkwatt portal using a reverse engineered private API.

# Installation
### HACS - NOT AVAILABLE - NEED UPDATE
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=faanskit&repository=ha-esolar&category=integration)

### Manual - NOT COMPLETE
- Copy directory `custom_components/checkwatt` to your `<config dir>/custom_components` directory.
- Restart Home-Assistant.

### Development

1. Install a HA developer environment: https://developers.home-assistant.io/docs/development_environment/

2. In the terminal (inside the docker container) do this:
```
cd /workspaces/core/config
mkdir custom_components
mkdir software
cd software
git pull https://github.com/faanskit/ha-checkwatt.git
git pull https://github.com/faanskit/pyCheckwatt.git
cd ../custom_components
ln -s ../software/ha-checkwatt/custom_components/checkwatt
cd checkwatt
ln -s ../../software/pyCheckwatt/pycheckwatt
```


## Enable the integration
Go to Settings / Devices & Services / Integrations. Click **+ ADD INTERATION**

## Configuration
If you need more sensor and more detailed attributes in the sensors, you can configure the integration as follows

Go to Settings / Devices & Services / Checkwatt. Click **CONFIGURE**.

Select if you want additional sensors.

After the configuration is done you need to restart the integration. Click **...** and select **Reload**

## Final result
When the system is fully set-up it can look something like this...
