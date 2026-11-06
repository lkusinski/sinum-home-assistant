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

## Additional WTP devices

Read-only sensor and binary entities are prepared for Sinum device types that are
not part of the current installation:

- pressure, CO2, IAQ, PM1/PM2.5/PM4/PM10 and illuminance sensors;
- smoke, flood, motion and two-state input sensors;
- radiator actuator opening and valve temperature;
- throttle opening, impulses and flow;
- energy meter current, voltage, power and energy;
- IR heater temperatures and PWM duty;
- blind controller opening positions;
- device state/action diagnostics.

Controls are only exposed where the cloud API has a verified command path. Other
device types remain read-only diagnostics until they can be validated.

## Other buses

SBus, SLink, LoRa, Modbus, alarm system, custom device modules, video, SMesh and
TECH devices are represented as generic devices. When present they receive
connectivity, problem, firmware and common diagnostic entities, plus the same
sensor/binary mapping by device type where available.

## Schedules

One device and two entities per active thermal schedule:

- current target temperature;
- `Aktywny` binary sensor for the current weekday/time window.

The fallback temperature, associated devices, modes and intervals are available
as attributes of the target-temperature sensor.
Schedules are read-only in Home Assistant; edit them in the Sinum app.

## Areas and devices

- Room areas are created or matched by name.
- Controllers, sensors, regulators, relays and system modules are assigned to
  their Sinum room.
- Multi-room controllers remain without a single area when their children belong
  to different rooms.
- Device hierarchy follows the Sinum parent/child relationships.
