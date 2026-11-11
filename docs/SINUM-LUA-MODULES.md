# Sinum Lua custom-device modules

Sources checked 2026-11-11:

- <https://apidocs.sinum.tech/> — local Sinum API 1.25.1
- <https://luadocs.sinum.tech/> — Lua reference PDF
- Sinum changelog / TECH integration pages

## What they are

A virtual custom device can create real Sinum device modules from Lua:

```lua
function CustomDevice:onInit(reason)
  if reason == "add" or reason == "import" then
    self:addModules({
      {type = "relay", uuid = "relay-1", name = "Relay"},
      {type = "air_conditioner", uuid = "ac-1", name = "AC", data = {
        available_modes = {"off", "automatic", "cooling", "heating", "fan", "drying"}
      }}
    })
  end
end
```

Modules come from the `custom_device_module` class, have their own IDs and are
accessed through:

- `GET/PATCH/DELETE /proxy/devices/custom-device-module/{id}`
- `POST /proxy/devices/custom-device-module/{id}/command/{command}`

Writable properties can also be changed directly with `PATCH` (tested:
`target_temperature`, `mode`, `state`, `target_level`). This is useful for a
bridge, but it may bypass the module command callback; use commands when the
remote device must receive the action.

The Lua docs list modules such as: air conditioner, air quality, analog input,
analog output, battery, blind controller, button, car charger, CO2, dimmer,
domestic hot water, energy meter, flood, gas/heat/water meter, heat pump,
humidity, IAQ, inverter, light/motion/opening/pressure sensors, radiator
actuator, relay, RGB controller, smoke, temperature regulator/sensor,
two-state input and valve.

`POST /devices/virtual` still accepts only the classic virtual types and custom
variants. `air_conditioner` is **not** a valid virtual type/variant; the proper
path is a custom device with an `air_conditioner` module.

## Test bench

Created in Sinum room **LAB Wirtualne** (13):

| Device | Modules |
|---|---|
| 144 `TEST · Klima Moduł AC` | air conditioner (module 1) |
| 145 `TEST · Moduły Lua` | relay, dimmer, RGB, two-state, temperature, humidity, battery, energy meter, water meter (2–10) |
| 146 `TEST · Moduły Sensory` | air quality, analog input, analog output, CO2, IAQ, light, motion, opening, pressure, flood, smoke (11–21) |
| 147 `TEST · Moduły Wykonawcze` | blind controller, button, car charger, DHW, gas meter, heat meter, heat pump, inverter, radiator actuator, temperature regulator, valve (22–32) |

All 32 modules can be created through Lua `onInit` without hardware.

## Tested commands

- **AC:** `set_target_temperature`, `set_mode`, `set_fan_speed`; modes
  `off/automatic/cooling/heating/fan/drying`.
- **Relay:** `turn_on`, `turn_off`, `toggle`.
- **Dimmer:** `turn_on`, `turn_off`, `set_level` (`[level, transition]`).
- **RGB:** `turn_on`, `turn_off`, `toggle`, `set_color`
  (`["#rrggbb", transition]`), `set_temperature` (`[kelvin, transition]`).
- **Button:** `emit` with an action object.
- **Car charger:** `start_charge`, `stop_charge` (accepted; charge power may
  remain 0 until the module callback updates it).
- **Radiator actuator:** `open`.
- **Valve:** `set_target_temperature`, `set_enabled`, `set_work_mode`
  (`heating`/`cooling`); `set_hysteresis` needs a non-empty value according to
  the API validation, still to be verified with a populated module.
- **Smoke:** `reset`; `test` should also be checked on a stable connection.
- **Blind controller:** `stop` (304 when idle); calibration and movement
  commands depend on module labels/associations.

## Constraints and next work

- `turn_on` can return `304` when the module is already in the requested state.
- DHW target-temperature mode requires an associated heating curve.
- Battery charge/discharge requires the `battery_charge_support` label.
- Some module commands are not listed in the OpenAPI `DeviceCommand.*OneOf`
  (relay/dimmer), but the runtime endpoint accepts them.
- The bridge currently maps only `custom_device` virtual devices. The next
  step is an explicit `custom_device_module` mapping path so AC, valves and
  meters can be exposed to Home Assistant without the generic element
  workaround.
