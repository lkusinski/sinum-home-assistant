# Project state and refactor plan

Last updated: 2026-11-12 17:40 CET (Europe/Warsaw)

This document is the hand-off snapshot for the current work. It separates the
Home Assistant integration from the experimental Z2M/HA bridge and records the
planned refactor. No credentials belong in this file.

## Components

### Home Assistant integration

- Domain: `sinum_home_assistant`
- Manifest version: `1.2.0`
- Source: `custom_components/sinum_home_assistant/`
- Direction: **Sinum → Home Assistant** (cloud polling, one coordinator).
- Main building blocks:
  - `api.py` — Sinum cloud client and OAuth refresh.
  - `coordinator.py` — 15–300 s polling (default 30 s).
  - `data.py` — normalized Sinum device groups; filters `integration_uid:
    z2m-bridge` so bridge-owned virtual devices do not come back to HA.
  - `climate.py`, `sensor.py`, `binary_sensor.py`, `switch.py`,
    `update.py`, `weather.py` — entity platforms.
  - `services.py` — `set_virtual_temperature`, `refresh`.
  - `entity.py` — device hierarchy, area assignment, cleanup.
  - `bridge.py` — native async bridge: mapper, HA event bus, Sinum REST and
    STOMP/SockJS stream, echo suppression, reconciliation.
- Direction: **Sinum → Home Assistant** (polling) and optional bidirectional
  **HA/Z2M ↔ Sinum** bridge.

### Z2M/HA bridge (integration-owned)

- Runtime source: `custom_components/sinum_home_assistant/bridge.py`.
- Direction: **HA/Z2M → Sinum** and **Sinum → HA**.
- Mapper uses the configured HA label (default `sinumbridge`, legacy `sinum`)
  and optional Sinum room. Mapping is persisted in HA storage; the first start
  imports `bridge/mapping.json` if present.
- Legacy/reference only: `bridge/map_z2m.py`, `bridge/z2m_to_sinum.py`,
  `bridge/event_worker.py`, systemd examples. They are no longer required.
- `bridge/mapping.json` remains the current LAB mapping snapshot (97 entries).

### Sinum-side test assets

- `docs/SINUM-LUA-MODULES.md` documents custom-device modules, property
  behavior and commands.
- The LAB bench contains:
  - native virtual thermostat, gate, wicket, integrators, heat-pump manager,
  - 32 Lua custom-device modules (AC, relay, dimmer, RGB, sensors, meters,
    valve, radiator actuator, etc.),
  - all 11 custom-device UI element types.

## Current runtime topology

- **B7 HA:** `http://192.168.1.204` (`homeassistant-2`), destination HA.
  It has the Generic Camera `camera.kamera_230_prod` using production Frigate
  snapshot/HTTP and RTSP.
- **Production HA Wiśniowa 9:** source of read-only Z2M/MQTT data; not modified
  by this project.
- **Sinum:** cloud API `https://backend.prd.sinum24.com`; local API is not
  reachable from CT310 at the moment.
- **CT310:** `192.168.1.123`, legacy bridge host. The systemd services are
  stopped/disabled after the integration-owned bridge went live; secrets remain
  in `/home/dev/.config/sinum-z2m.env` (600) as reference.

## Current LAB rooms and ownership

- **LAB Lukasz (11):** mostly diagnostic analog/energy/battery devices and the
  unavailable `HA · Nad wejściem`.
- **LAB Działające (12):** working lights, contacts and relays.
- **LAB Wirtualne (13):** 32 Lua modules and local fake helpers.
- Every bridge-created virtual device is marked with
  `integration_uid: z2m-bridge`; the integration ignores those devices.

## Current bridge behavior

- Selection uses the integration option label (currently `sinumbridge`), with
  legacy `sinum` accepted for existing LAB devices.
- HA→Sinum is event-driven; reconciliation runs every 60 s as a fallback.
- Sinum→HA handles:
  - relays (`relay_switch`),
  - lights (`color_picker`; RGB/color-temperature normalization),
  - the AC `custom_device_module` module in LAB Wirtualne (module 1),
  - custom module state changes through a short suppression window.
- Stats:
  - custom devices do not store statistics by default,
  - LAB temp/humidity sensors have Lua `statistics:addPoint`,
  - LAB lights have state/brightness points, contacts have state points,
  - gate-managed relay 121 does not produce a relay point,
  - charts still require a statistics query in the Sinum UI.

## Target product direction

The LAB rooms are a test environment, not a product limitation. The target is a
general, configurable bridge.

### Configuration target

An integration options flow should expose:

1. **Expose to Sinum** — enabled/disabled.
2. **Selection label** — default **`sinumbridge`** (HA device/entity label),
   with optional legacy `sinum` compatibility.
3. **Direction** — HA→Sinum or bidirectional.
4. **Target Sinum room** — optional, otherwise derive from the HA area.
5. **Excluded domains/entities** — diagnostics, hidden/disabled entities.

The bridge should select devices by label, not by hard-coded rooms. The label
must be applied only to the devices/entities the user wants in Sinum.

### Architecture target

The external systemd bridge was a prototype. It is now implemented as an
optional part of the integration (one config entry), so the options flow is
authoritative and mapping/config are owned by Home Assistant. The scripts in
`bridge/` remain only as a reference implementation.

## Refactor phases

### Phase 0 — CI and documentation (done)

- HACS job skipped for private repositories; hassfest and lint remain active.
- README/bridge docs updated to present LAB as a test deployment.
- Project state and target plan recorded here.

### Phase 1 — configurable selection (implemented, live in B7)

- Integration options now expose `bridge_enabled`, `bridge_label` (default
  `sinumbridge`), and `bridge_room_id`.
- The integration publishes a diagnostic
  `sensor.sinum_home_assistant_bridge_configuration` with
  `sinum_bridge_config: true`, `enabled`, `label`, and `room_id`.
- The legacy `map_z2m.py` read that diagnostic sensor and fell back to the
  legacy `sinum` label for compatibility; the internal mapper now reads the
  options directly.
- Phase 2 moved label/room changes into the integration lifecycle.
- Introduce a shared bridge config model:
  - label name (default `sinumbridge`, legacy `sinum` accepted),
  - target room fallback,
  - send/receive direction,
  - exclusions.
- Replace hard-coded `sinum`/LAB IDs in `map_z2m.py` and deployment examples.
- Keep a compatibility mode for the current LAB so existing mappings continue
  to work until migration is complete.

### Phase 2 — integration-owned bridge (done)

- Integration options and diagnostic config sensor are implemented.
- The bridge event loop is native async code in `bridge.py`: HA state events,
  Sinum STOMP/SockJS events, REST commands and reconciliation all run in the
  Home Assistant event loop.
- Existing 97 mappings were imported from `mapping.json` into HA storage.
- Bridge start/stop is tied to config-entry setup/unload and options reload.
- External systemd services are no longer required for normal operation.
- Remaining hardening: tests for selection/mapping and long-run reconnect
  scenarios; optional bridge service for manual remap.

### Phase 3 — module and protocol expansion (next)

- Generalize `custom_device_module` beyond the AC module: modules, sensors,
  meters, valves.
- Decide whether to use the official Sinum MQTT/Lua path or cloud REST/WS.
- Add marketplace-ready export/import tests.

### Phase 4 — tests and release

- Add unit tests for selection, mapping and echo suppression.
- Add a repeatable LAB smoke test (API + Playwright + physical verification).
- Release integration and bridge separately or document a combined release.

## Safety rules

- Do not touch Sinum devices outside LAB until the target selection is
  configured.
- Write-back can physically operate a colleague’s hardware. Test only with
  explicit approval and restore state afterwards.
- Never commit secrets, tokens, private IP credentials or mapping data that
  identifies a private installation without review.
- Keep `DOSTEPY.md` and the bridge env file at mode 600 and outside git.
