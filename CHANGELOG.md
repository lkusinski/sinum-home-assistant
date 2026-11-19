# Changelog

All notable changes to this project will be documented in this file.

## 1.6.0 — 2026-11-19

- Add a Sinum maintenance sensor. The coordinator reads
  `/maintenance-manager/status` and exposes a `binary_sensor` (`Prace
  serwisowe`) that is on for `SCHEDULED`/`UNDERWAY`, with status, start, end
  and message attributes.
- Add a `heat_pump` bridge variant for custom device modules. A HA climate
  entity is mirrored to a Sinum heat-pump module (`enabled`, target
  temperature) with echo suppression and reconciliation; Sinum changes call
  `climate.set_hvac_mode`/`set_temperature` back on HA.
- Read-only module update status is kept out of automatic updates; module
  update endpoints are documented for a later explicit action.

## 1.5.3 — 2026-11-19

- Synchronize air-conditioner fan speed between the HA climate entity and the
  Sinum AC module. `auto`/`silent`/`full` are mapped to the module's
  `automatic`/`low`/`high` fan set.

## 1.5.2 — 2026-11-19

- Stop blocking new Sinum user commands with the 15 s recent-event window.
  HA→Sinum echo suppression stays in place, while relay, light and AC use a
  short per-device echo window. Turning a relay off shortly after turning it
  on from Sinum is no longer ignored.

## 1.5.1 — 2026-11-19

- Follow Sinum room changes in Home Assistant: when a device moves between
  Sinum rooms, its HA area is updated even if it already had an area. Manual
  HA-only areas are preserved (only areas matching Sinum room names are
  overwritten).
- Look up devices by their Sinum identifier without requiring the device to be
  linked in the config-entry column; the integration-created devices are
  otherwise found by the stable `sinum_home_assistant` identifier.
- This makes moving the LAB AC and heat-pump modules from LAB Wirtualne to
  LAB Lukasz visible in the HA area assignment, without recreating entities.

## 1.5.0 — 2026-11-18

- Expose Sinum `air_conditioner` custom device modules as Home Assistant
  `climate` entities: hvac modes (off/auto/cool/heat/fan/dry), target
  temperature, fan modes, current temperature when the module reports it, and
  hvac action.
- Expose `heat_pump` modules read-only: target indoor temperature, thermal
  demand, target temperature mode, enabled and electric-heater binary sensors.
  No heat-pump commands are sent.
- The LAB AC module is now controlled natively; remove it from the bridge
  mapping to avoid two controllers for the same module.

## 1.4.2 — 2026-11-18

- Remove stale Home Assistant devices left behind for bridge-owned or legacy
  virtual Sinum devices. Devices without entities that are not part of the
  current filtered virtual set are deleted from the device registry on setup.
- Move dimmer/RGB light entities onto the shared `custom_device_module_*`
  device, so each module has one HA device instead of one for the light and a
  second for diagnostics. The old `custom_module_*` light devices are removed
  when empty.

## 1.4.1 — 2026-11-18

- Repair mojibake in the bridge mapping (names, units and texts). Values such
  as `ÃÂ°C` now become `°C`, `GaraÃÂ¼` becomes `Garaż`, and mixed strings with
  already-correct Polish characters are handled by repairing only the Latin-1
  runs.
- Refresh Sinum virtual device names from the current HA friendly name on each
  reconcile. Renamed devices (for example the old `Łukasz PIR` now exposed as
  `Salon PIR`) update automatically without recreating the mapping.
- Resync temperature/humidity/contact text immediately after a unit or text
  repair, so the Sinum UI stops showing stale `Â°C` values.

## 1.4.0 — 2026-11-18

- Add custom device module support. Sinum Lua modules are now exposed in Home
  Assistant: relay modules as switches, dimmer/RGB modules as lights, and
  temperature/humidity/battery/analog/energy/water/gas/heat meter modules as
  sensors. Opening, motion, flood, smoke and two-state modules become binary
  sensors.
- Add a native `light` platform for dimmer and RGB custom modules.
- Modules whose parent custom device is bridge-owned
  (`integration_uid: z2m-bridge`) are skipped to avoid control loops. The
  parent room is inherited when the module has no room of its own.
- Add custom-module counts and types to diagnostics.

## 1.3.2 — 2026-11-17

- Propagate Home Assistant availability to Sinum. Bridge-created custom
  devices expose a `set_availability` Lua command; an `unavailable` or
  `unknown` HA entity sets the Sinum device status to `offline`, and a
  recovered entity sets it back to `online`.
- Sinum actions for an unavailable mapped entity are ignored, so pressing a
  powered-off Zigbee light or gate button no longer calls HA.
- New devices include the availability handler in their Lua. Existing devices
  get it lazily the first time their HA state becomes unavailable, without
  touching persistent plugs or lights that are online.

## 1.3.1 — 2026-11-17

- Serialize every Sinum cloud request per config entry. The coordinator, the
  bridge and entity actions share one client, and the cloud allows only one
  request in flight per device id. Concurrent polling produced repeated
  `HTTP 429: Device ... already has a request in flight` and dropped updates.
- Retry `HTTP 429` and transient `5xx` responses with exponential backoff;
  retry `401` once after a forced token refresh.
- Run the bridge event stream, reconciliation and initial sync as Home
  Assistant background tasks, so they no longer trigger "Setup timed out for
  bootstrap" warnings.
- Mark the coordinator area listener as a Home Assistant callback to keep
  task creation on the event loop.

## 1.3.0 — 2026-11-17

- Add a `momentary` bridge variant for garage gates and fences. Sinum shows a
  native `button` element (`pulse_button`) plus a `text` element
  (`contact_state`) instead of a raw relay switch. Pressing the button calls
  the configured HA action (`script.*`, `input_button.*`, `cover.*`),
  never the physical relay directly.
- Watch the mapped contact sensor (with optional `state_invert`) and show
  open/closed state in Sinum. Entries without a sensor show `Brak czujnika`.
- Add a 3 s watchdog that forces the underlying HA switch off if a pulse
  remains on, plus a 1 s debounce against duplicate button events.
- Persistent devices (plugs, chargers, lights) remain `relay` and keep the
  1.2.4 echo suppression.

## 1.2.4 — 2026-11-17

- Suppress stale Sinum relay echoes after a Home Assistant → Sinum relay
  write (3 s window). Momentary garage/gate relays were being retriggered by an
  asynchronous echo of the previous ON, which arrived after HA had already
  returned the relay to OFF. This caused an unintended second impulse.

## 1.2.3 — 2026-11-13

- Document camera verification for B7 (`camera.kamera_230_prod`): snapshot
  640×360, HEVC RTSP 2560×1920/15 fps, and a successful 5-second HA recording.
- Document that the Sinum cloud has no visible video devices and the local API
  video endpoints are unreachable from the current network.
- Correct the local API reachability notes.

## 1.2.2 — 2026-11-12

- Add config-entry diagnostics with redacted credentials, coordinator counts,
  bridge status and mapping count.
- Fix the Home Assistant stop listener to run as an async callback, avoiding
  cross-thread task creation and shutdown warnings.
- Add local Sinum API research (`docs/API-LOCAL.md`) and source review notes
  (`docs/SOURCES.md`), including the official API/OpenAPI and MCP resources.
- No change to cloud behaviour; local transport remains a documented roadmap
  until a reachable hub can be validated.

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
