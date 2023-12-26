# Home Assistant Checkwatt Custom Integration
This integration uses cloud polling from the Checkwatt Energy In Balance portal using a reverse engineered private API.

The focus on this integration is to reduce the amount of sensors published while at the same time maximize the information available and provide them as attributes.

Out-of-the box, this integration provides two sensors:
- Checkwatt Daily Yield : Your estimated yield today
- Checkwatt Annual Yield : Your estimated annual yield

The Daily Yield sensor also have an attribute that provides information about tomorrows planned yield.

# Installation
### HACS installation - NOT AVAILABLE
The integration will be published on Hacs but is currently not available there.
The process to publish on Hacs includes to provide branding material to Home Assistant developers. This process is started and when branding is approved, the integration will be published on Hacs and the below link will be made functional.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=faanskit&repository=ha-checkwatt&category=integration)



### Git installation
1. Make sure you have git installed on your machine.
2. Navigate to you home assistant configuration folder.
3. Create a `custom_components` folder of it does not exist, navigate down into it after creation.
4. Execute the following command: `git clone https://github.com/faanskit/ha-checkwatt.git checkwatt`
5. Restart Home-Assistant.

### Development installation
If you are a developer and want to contribute to this integration we strongly recommend to use the Home Assistant Developer environment.

Currently the process is quite technical, so basic understanding of software development and Linux are expected.

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

Find Checkwatt from the list of available brands:

![checkwatt config step 1](/images/configure_step_1.png)

Enter your Energy In Balance credentials and press **SUBMIT**:

Take note that Home Assistant will store your credentials and if this is a security concern for you, abort at this stage.

![checkwatt config step 2](/images/configure_step_2.png)

The integration will now install and assuming it all wend well you will get a success message and the possibility to add its sensors to an area of your choice.

![checkwatt config step 3](/images/configure_step_3.png)

On your Overview you will now have two new sensors in a new group:

![checkwatt config done](/images/configure_done.png)

These sensors will show you your planned daily and annual yield alongside with some basic attributes like Street Address, Zip Code and City.

The Daily Yield sensor will also show tomorrows planned yield as an attribute.

![checkwatt basic daily](/images/basic_sensor_daily.png)
![checkwatt basic annual](/images/basic_sensor_annual.png)


## Configuration
The integration provides basic sensors for most peoples needs. The configuration can also be a one-stop-shop for the Home Assistant Energy panel and can therefore be configured to also fetch all required data for that from Energy In Balance.

For those who need additional information, detailed attributes can be provided by configuring the integration accordingly. Through the detailed sensors you can get gross revenue, fees, fee rates, FCR-D status and much more.

If you need more sensor and more detailed attributes in the sensors,  configure the integration as follows.

Go to Settings / Devices & Services / Checkwatt. Click **CONFIGURE**:

![checkwatt options step 1](/images/options_step_1.png)

Select if you want the integration to provide energy sensors and if detailed attributes shall be provided.

Press **SUBMIT** and the configurations will be stored:

![checkwatt options step 2](/images/options_step_2.png)

After the configuration is done you need to restart the integration. Click **...** and select **Reload**
![checkwatt options step 3](/images/options_step_3.png)

After the system as reload you will have 1 device and 9 sensors available.
![checkwatt options done](/images/options_done.png)


![checkwatt detailed daily](/images/detailed_sensor_daily.png)
![checkwatt detailed annual](/images/detailed_sensor_annual.png)

## Setting up Energy Panel
With the energy sensors provided by the integration, it is possible to configure the Home Assistant Energy Panel. The Energy panel is available on the left-hand menu of Home Assistant by default.

When you enter the energy panel the first time you will be guided by a Wizard:

![checkwatt energy step 1](/images/energy_step_1.png)

For the Grid Consumption, select the Import Energy sensor from the integration and complement it with the cost tracker using the *Spot Price VAT* sensors.

Take note that you should use the sensor that includes VAT for Electricity that you purchase. Please also not that this sensor does not include markups from your electricity provider.

![checkwatt energy step 2](/images/energy_step_2.png)

For Grid Consumption, select the Export Energy sensor from the integration and complement it with the cost tracker using the *Spot Price* sensors.

Take note that you should use the sensor that excludes VAT for Electricity that you sell. 

![checkwatt energy step 3](/images/energy_step_3.png)

When configured, it looks like this. Press **SAVE + NEXT** to continue the Wizard.

![checkwatt energy step 4](/images/energy_step_4.png)

Add the Solar Energy sensor from the integration and press **SAVE + NEXT** 

![checkwatt energy step 5](/images/energy_step_5.png)

Add the Battery Energy sensors from the integration.
*Energy going in to the battery* = Battery Charging Energy Sensor
*Energy going out of the battery* = Battery Discharging Energy Sensor

 Press **SAVE + NEXT** 

![checkwatt energy step 6](/images/energy_step_6.png)

Finish off the Wizard and the result will look like this.
Please be advised that it will take a few hours before the Energy Panels start showing data.

Also, currently Energy In Balance does not always provide proper Grid Input and Output why this data cannot be relied upon.

For now, you need to pull that data from another integration.

![checkwatt energy done](/images/energy_done.png)

## Final result
When the system is fully set-up it you have sensors that provides you with your daily and annual yield and if you have configured it accordingly, you also have sensors available for the Home Assistant Energy Dashboard.

The final result can look like this:

![checkwatt main](/images/ha_main.png)

# Expert Section
If you think that some of the attributes provided should be sensors, please consider to use [Templates](https://www.home-assistant.io/docs/configuration/templating/) before you register it as an [issue](https://github.com/faanskit/ha-checkwatt/issues). If it can be done via a Template Sensor, it will most likely be rejected.

## Use templates
This is an example of a Template based Sensor that pulls tomorrows planned daily yield from the attribute of the Checkwatt Daily Yield sensor.

It goes without saying, but this should be put in your `configuration.yaml`:
```yaml
template:
  - sensor:
      - name: "Checkwatt Tomorrow Yield"
        unique_id: checkwatt_tomorrow_yield
        state: "{{ state_attr('sensor.skarfva_checkwatt_daily_yield', 'tomorrow_gross_income')}}"
        unit_of_measurement: "SEK"
        device_class: "monetary"
        state_class: total
```
The result will look something like this:

![template based sensor](/images/expert_sensor.png)


## Use developer tools
The names of the attributes can be found in the Home Assistant Developer Tools section in your Home Assistant environment under the **STATES** sheet:

![home assistant developer tools](/images/dev_tools_states.png)

# Acknowledgements
This integration was loosely based on the [ha-esolar](https://github.com/faanskit/ha-esolar) integration.
It was developed by [@faanskit](https://github.com/faanskit) with support from:

- [@flopp999](https://github.com/flopp999)
- [@angoyd](https://github.com/angoyd)
- [@mattiasclaesson](https://github.com/mattiasclaesson)

This integration could not have been made without the excellent work done by the Home Assistant team.

If you like what have been done here and want to help I would recommend that you firstly look into supporting Home Assistant.

You can do this by purchasing some swag from their [store](https://home-assistant-store.creator-spring.com/) or paying for a Nabu Casa subscription. None of this could happen without them.

# Licenses
The integration is provided as-is without any warranties and published under [The MIT License](https://opensource.org/license/mit/).