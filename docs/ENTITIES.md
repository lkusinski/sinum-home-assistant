# Entity reference

Entity names and IDs are generated from the Sinum room, device and property
names. Exact counts depend on the installation.

## Climate

One entity per room thermostat and per WTP temperature regulator.

Supported features:

- target temperature;
- target temperature step of 0.5 °C;
- HVAC modes reported by the device (heat, cool, auto, off);
- current temperature;
- HVAC action derived from the device state or target-reached flag.

## Weather

One weather entity for the hub location.

- current condition, temperature, humidity, pressure and cloud coverage;
- hourly forecast;
- daily forecast including low/high temperature, UV index and wind.

Weather sensors are also created for temperature, humidity, pressure, wind,
UV index, solar irradiance, cloud coverage and apparent temperature.

## Sensors

Examples:

- room temperature and humidity;
- battery level;
- signal strength;
- firmware version;
- IP address, network name, channel and latency;
- hub uptime and API version;
- system-module diagnostics.

Sensors whose network information is not reported by the device remain
`unknown`; this is normal.

## Binary sensors

- window contact state;
- heating and cooling state;
- target temperature reached;
- warning and error flags;
- virtual thermostat light/window inputs.

## Switches

One switch per free relay output. The state follows the Sinum cloud and commands
are sent directly to the cloud.

Relays managed by a Sinum virtual thermostat are **read-only** in Home Assistant.
They are exposed as `Stan przekaźnika` binary sensors because the cloud rejects
direct relay commands for those outputs.

## Update

Firmware update entities are created for the hub, parent controllers, extenders,
transceivers and supported devices. The update entity shows the installed and
latest version reported by the cloud.

> Firmware installation is performed in the Sinum app. Home Assistant reports
> available versions and progress, but does not start the update itself.

## Areas and devices

- Room areas are created or matched by name.
- Controllers, sensors, regulators, relays and system modules are assigned to
  their Sinum room.
- Multi-room controllers remain without a single area when their children belong
  to different rooms.
- Device hierarchy follows the Sinum parent/child relationships.
