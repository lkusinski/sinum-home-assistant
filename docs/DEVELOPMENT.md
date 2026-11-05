# Development

## Layout

```
custom_components/sinum_home_assistant/
  __init__.py          config entry setup and unload
  api.py               async cloud client and OAuth refresh
  config_flow.py       config, reauth and options flows
  const.py             constants and platform list
  coordinator.py       polling coordinator
  data.py              normalized snapshot and room mapping
  entity.py            device info and base entities
  sensor.py            sensors
  binary_sensor.py     binary sensors
  climate.py           thermostats and regulators
  switch.py            relays
  update.py            firmware update entities
  weather.py           weather entity and forecast
  manifest.json
  strings.json
  translations/
  brand/
```

## Local checks

```bash
python3 -m compileall custom_components/sinum_home_assistant
ruff check custom_components/sinum_home_assistant
```

## Test in Home Assistant

1. Copy the integration to `config/custom_components/`.
2. Restart Home Assistant.
3. Add the integration and verify entities.
4. Reload the config entry after code changes.

## API notes

The integration uses the Sinum cloud proxy API and OAuth refresh tokens. A full
update cycle requests:

- `info` (cached for five minutes);
- `rooms`;
- `parent-devices`;
- `devices`;
- `weather` (optional).

Commands use `PATCH devices/{class}/{id}`.

## Contributing

- Keep the integration free of installation-specific IDs and credentials.
- Update this documentation when user-facing behavior changes.
- Run compile and lint checks before opening a pull request.
