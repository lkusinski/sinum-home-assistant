# Project state and refactor plan

Last updated: 2026-11-12 (Europe/Warsaw)

This document is the hand-off snapshot for the current work. It separates the
Home Assistant integration from the experimental Z2M/HA bridge and records the
planned refactor. No credentials belong in this file.

## Components

### Home Assistant integration

- Domain: `sinum_home_assistant`
- Manifest version: `1.1.10`
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

### Z2M/HA bridge (experimental, currently LAB)

- Source: `bridge/`
- Direction: **HA/Z2M → Sinum**, with optional **Sinum → HA** write-back.
- `map_z2m.py` — creates missing virtual devices for B7 devices selected by a
  label.
- `z2m_to_sinum.py` — full reconciliation (currently 300 s) and initial
  migration.
- `event_worker.py` — push:
  - HA WebSocket `state_changed` → Sinum PATCH,
  - Sinum STOMP/SockJS `/topic/<deviceId>` → HA service call,
  - echo suppression and short burst protection.
- `mapping.json` — HA entity ↔ Sinum object mapping; 97 entries in the current
  LAB deployment.
- Systemd examples:
  - `sinum-z2m.service.example` (reconciliation),
  - `sinum-z2m-events.service.example` (push).

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
- **CT310:** `192.168.1.123`, runs the two bridge services. Secrets live in
  `/home/dev/.config/sinum-z2m.env` (600).

## Current LAB rooms and ownership

- **LAB Lukasz (11):** mostly diagnostic analog/energy/battery devices and the
  unavailable `HA · Nad wejściem`.
- **LAB Działające (12):** working lights, contacts and relays.
- **LAB Wirtualne (13):** 32 Lua modules and local fake helpers.
- Every bridge-created virtual device is marked with
  `integration_uid: z2m-bridge`; the integration ignores those devices.

## Current bridge behavior

- Selection is currently hard-coded to the HA label `sinum` (legacy LAB
  choice) and to LAB room IDs.
- HA→Sinum is event-driven; 300 s reconciliation is only a fallback.
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

The external systemd bridge is a prototype. The preferred target is to make the
bridge an optional part of the integration (one config entry), so the options
flow is authoritative and there is no separate configuration file to keep in
sync. If the bridge remains external, it must read its configuration from an
explicit shared source; duplicating options in two UIs is not acceptable.

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
- `map_z2m.py` reads that diagnostic sensor and falls back to the legacy
  `sinum` label and `SINUM_BRIDGE_LABEL` env for compatibility.
- The external worker still needs restarting after a label/room option change;
  the next phase is to move it into the integration lifecycle.
- Introduce a shared bridge config model:
  - label name (default `sinumbridge`, legacy `sinum` accepted),
  - target room fallback,
  - send/receive direction,
  - exclusions.
- Replace hard-coded `sinum`/LAB IDs in `map_z2m.py` and deployment examples.
- Keep a compatibility mode for the current LAB so existing mappings continue
  to work until migration is complete.

### Phase 2 — integration-owned bridge

- Move bridge selection and lifecycle into the integration options flow.
- Persist bridge-owned virtual device IDs and ownership markers.
- Keep an explicit “bridge owns these devices” filter so integration does not
  import them.
- Add migration from the external service (read `mapping.json`, mark devices,
  then disable the external service).

### Phase 3 — module and protocol expansion

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
