# Changelog

All notable changes to this project will be documented in this file.

## 1.2.1 — 2026-11-12

- Cancel bridge tasks cleanly on Home Assistant shutdown to avoid delayed
  shutdown warnings.
- Persist mapping reloads back into HA storage, so a changed mapping file is not
  lost after restart.
- Skip disabled and hidden entities in the internal mapper.
- Sync the Sinum relay state after a Sinum-originated HA command.
- Accept binary WebSocket frames from the Sinum event stream.
- Tidy the bridge payload helper name and update the repository description.

## 1.2.0 — 2026-11-12

- Move the HA/Z2M bridge into the integration lifecycle as native async code.
- Add an internal label/room mapper and bridge event processing; existing
  external systemd workers are no longer required for normal operation.
- Keep the existing `bridge/mapping.json` mapping as an import source for the
  first start; mappings are then persisted in HA storage.
- Support the same LAB variants: relays, lights (`color_picker`), contacts,
  temperature/humidity, analog values, energy, battery and the AC module.
- Add bridge start/stop handling on config-entry unload and options reload.

## 1.1.11 — 2026-11-12

- Add integration options for the optional HA/Z2M bridge: enable, selection
  label (`sinumbridge` by default, legacy `sinum` accepted), and target Sinum
  room.
- Publish a diagnostic bridge configuration sensor consumed by the external
  bridge mapper.
- Document config schema and the project refactor state.

## 1.1.10 — 2026-11-11

- Add `sinum_home_assistant.refresh` service to force an immediate coordinator
  refresh. The Z2M event worker calls it on non-bridge virtual device changes,
  so virtual thermostats and other native Sinum devices update in HA without
  waiting for the 30 s poll.

## 1.1.9 — 2026-11-11

- Ignore virtual custom devices marked with `integration_uid: z2m-bridge` so the
  Z2M bridge test/lab devices are not imported back into Home Assistant.
- Prevent duplicate entities and feedback loops between the integration and the
  bridge-owned Sinum devices.

## 1.1.8 — 2026-11-11

- Do not create generic online/problem entities for virtual custom devices.
- Remove stale virtual connectivity entities during setup.
- Support full light control in the separate Z2M bridge via color_picker
  elements (on/off, brightness, RGB, color temperature).

## 1.1.7 — 2026-11-11

- Add `services.yaml` for `set_virtual_temperature` so hassfest accepts the
  integration and Home Assistant loads the service description.

## 1.1.6 — 2026-11-11

- Support virtual custom `temperature_sensor` devices created in Sinum.
- Add `sinum_home_assistant.set_virtual_temperature` service for pushing values
  from Home Assistant into a Sinum virtual temperature sensor.
- Keep dynamically created virtual sensors available even when Sinum reports
  their status as `unknown`.
- Document service and automation examples.

## 1.1.5 — 2026-11-10

- Reassign areas after newly discovered devices appear, not only during the
  initial setup. This fixes missing area assignment for devices added later.
- Keeps new child sensors attached to their Sinum room after automatic reload.

## 1.1.4 — 2026-11-09

- Expose relay diagnostics on climate entities: relay IDs, current states and
  seconds since last change as attributes.
- Expose relay last-change age and Sinum labels on free relay switches.
- This makes managed relay behavior observable without adding extra entities.

## 1.1.3 — 2026-11-08

- Retry transient cloud/DNS failures before marking the coordinator update failed.
- Reduces availability gaps caused by short Sinum cloud or resolver outages.

## 1.1.2 — 2026-11-06

- Remove redundant relay-state entities for thermostat-managed relays.
- Remove duplicated per-child radio signal/battery entities; parent signal and
  battery are available as attributes on the parent connectivity entity.
- Remove duplicated virtual thermostat temperature/humidity entities.
- Remove empty system-module network entities for fields not reported by hardware.
- Keep schedule fallback and associated-device details as attributes instead of
  separate entities.
- Entity count reduced from 278 to 182 without losing control or measurement data.

## 1.1.1 — 2026-11-06

- Automatically reload the config entry when new devices, parents or schedules appear.
- Keep entity creation up to date without a manual restart after extending the Sinum system.

## 1.1.0 — 2026-11-06

- Thermal schedule entities: current/fallback target, associated devices and activity.
- Schedules option and dedicated coordinator polling.
- Pressure, CO2, IAQ, particulate matter, illuminance, smoke, flood, motion,
  two-state input, radiator actuator, throttle, energy meter, IR heater and
  blind controller support for WTP devices.
- Generic read-only support for remaining Sinum buses and parent devices.
- Automatic cleanup of optional schedule/weather/system-module entities.

## 1.0.5 — 2026-11-06

- Polish-first README and repository description.
- New brand icon combining the Sinum house with Home Assistant network nodes.
- Refreshed logo, banner and dashboard preview.

## 1.0.4 — 2026-11-06

- Expose thermostat-managed relays as read-only state sensors instead of switches.
- Remove stale entities when weather or system modules are disabled.
- Remove legacy managed-relay switch entities during upgrade.
- Detect managed relays from both labels and virtual supervisors.

## 1.0.3 — 2026-11-06

- Use day/night-aware conditions in hourly forecasts.
- Keep controller and module connectivity sensors available while offline.
- Preserve a valid zero solar irradiance value.
- Avoid string `"None"` for missing sunrise/sunset attributes.
- Strip trailing whitespace from generated device names.
- Do not create system-module parent devices when that option is disabled.
- Clarify that firmware installation is performed in the Sinum app.

## 1.0.2 — 2026-11-06

- Clarify the copyright and trademark notice.

## 1.0.1 — 2026-11-06

- Use the product name for newly created config entries.
- Add lint validation to CI.

## 1.0.0 — 2026-11-05

First public release.

- Native Home Assistant integration for Sinum cloud accounts.
- Climate entities for thermostats and WTP temperature regulators.
- Weather entity with hourly and daily forecasts.
- Relay switches and firmware update entities.
- Room-to-area mapping and parent/child device hierarchy.
- Config flow, reauthentication and options flow.
- Diagnostics for battery, signal, network and system modules.
