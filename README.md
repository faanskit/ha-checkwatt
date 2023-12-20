[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/faanskit/) [![Donate](https://img.shields.io/badge/Donate-BuyMeCoffe-green.svg)](https://www.buymeacoffee.com/faanskit)

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
When the system is fully set-up it can look something like this

# Donations
I mainly did this project as a learning experience for myself and have no expectations from anyone.

If you like what have been done here and want to help I would recommend that you firstly look into supporting Home
Assistant.

You can do this by purchasing some swag from their [store](https://teespring.com/stores/home-assistant-store)
or paying for a Nabu Casa subscription. None of this could happen without them.

After you have done that if you still feel this work has been valuable to you I welcome your support through BuyMeACoffee or Paypal.

<a href="https://www.buymeacoffee.com/faanskit"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=faanskit&button_colour=FFDD00&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=ffffff"></a> [![Paypal](https://www.paypalobjects.com/digitalassets/c/website/marketing/apac/C2/logos-buttons/optimize/44_Yellow_PayPal_Pill_Button.png)](https://paypal.me/faanskit)
