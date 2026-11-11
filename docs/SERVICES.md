# Services

## `sinum_home_assistant.set_virtual_temperature`

Writes a temperature value to a Sinum virtual **temperature sensor** created as
a custom virtual device.

This is useful when a temperature source lives in Home Assistant (Zigbee, Tuya,
ESPHome, input number, template sensor) and should also be visible in Sinum.

### Data

| Field | Required | Description |
|---|---|---|
| `device_id` | yes | Numeric ID of the Sinum virtual custom device (`temperature_sensor`). |
| `temperature` | yes | Temperature in °C. The integration converts it to Sinum's ×10 format. |

### Example

```yaml
action: sinum_home_assistant.set_virtual_temperature
data:
  device_id: 9
  temperature: 23.4
```

### Home Assistant input number example

```yaml
input_number:
  sinum_ha_salon_temperature:
    name: Sinum HA Salon – temperatura
    min: 5
    max: 35
    step: 0.1
    unit_of_measurement: °C

automation:
  - alias: Sinum HA Salon – push temperature
    triggers:
      - trigger: state
        entity_id: input_number.sinum_ha_salon_temperature
    actions:
      - action: sinum_home_assistant.set_virtual_temperature
        data:
          device_id: 9
          temperature: "{{ states('input_number.sinum_ha_salon_temperature') | float }}"
```

For a real Zigbee/Tuya/ESPHome sensor, replace the trigger and template with that
entity. The Sinum device must already exist as a virtual custom device with
`variant: temperature_sensor`; the integration exposes its current value as a
temperature sensor in Home Assistant.
