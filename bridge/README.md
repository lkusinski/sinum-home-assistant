# Z2M → Sinum bridge

Bridge between Home Assistant Zigbee2MQTT devices and Sinum virtual devices.
The current test deployment targets **LAB Lukasz** (11), **LAB Działające**
(12) and **LAB Wirtualne** (13); the target product uses an explicit HA label
(proposed: **`sinumbridge`**) instead of hard-coded LAB rooms.

## Direction

- **Z2M / HA → Sinum**: `event_worker.py` subscribes to Home Assistant
  `state_changed` over WebSocket and pushes changes immediately; the periodic
  `z2m_to_sinum.py` run is now a 300 s reconciliation fallback.
- **Sinum → Z2M** (relay/light on-off, light brightness/color/temperature):
  `event_worker.py` subscribes to the Sinum STOMP/SockJS topic
  `/topic/<deviceId>` and reacts to user changes in under a second. Optional
  write-back is controlled by `WRITE_BACK=1`; set `WRITE_BACK=0` for a
  strictly one-way mirror.
- The bridge does **not modify production Home Assistant**. It only uses the B7
  Home Assistant REST API and the MQTT-backed Z2M entities already present there.

## Files

- `mapping.json` — HA entity → Sinum virtual device mapping.
- `z2m_to_sinum.py` — periodic reconciliation/state worker.
- `event_worker.py` — WebSocket/STOMP push worker (HA ↔ Sinum events).
- `map_z2m.py` — creates missing devices from B7 devices labelled `sinum`.
- `sinum-z2m.service.example` — systemd unit for the periodic worker.
- `sinum-z2m-events.service.example` — systemd unit for the push worker.
- `sinum-z2m-map.service.example` + `.timer.example` — label/room mapper
  reconciliation every minute.

## Run

```bash
export B7_TOKEN='<long-lived token>'
export SINUM_EMAIL='...'
export SINUM_PASSWORD='...'
export SINUM_DEVICE_ID='...'
export SINUM_ROOM_ID=11
export SINUM_BRIDGE_LABEL=sinumbridge
export STATE_FILE=/var/lib/sinum-z2m/state.json
export SINUM_STATE_FILE=/var/lib/sinum-z2m/sinum_state.json
python3 z2m_to_sinum.py --once
python3 z2m_to_sinum.py --interval 300
python3 event_worker.py
# optional timer: map_z2m.py every minute
```

Set `WRITE_BACK=0` to disable Sinum → HA commands.

## Mapping policy

Selection is label-based. `SINUM_BRIDGE_LABEL` defaults to the target label
`sinumbridge`; the legacy LAB label `sinum` is still accepted for compatibility.
All bridge-created devices carry `integration_uid: z2m-bridge` so the
integration can skip them and avoid feedback loops. The current test mapping
uses 97 mapping entries: relays, two-state
contacts, temperature/humidity, lights, analog values, energy and battery. All LAB lights use `generic` custom devices with a `color_picker` element, so
on/off, brightness, RGB and color temperature work in both directions. Temperature and
humidity sensors get a `text` element (`21.1 °C` / `52.6 %`) because Sinum does
not render the custom sensor variant value on its own; the stock value stays in
`variant_device` for other consumers. New temp/humidity sensors also receive Lua
code that sets `status=online` and calls `statistics:addPoint`, because Sinum
does not store custom-device statistics by default. Relays get a `switcher` element
(`relay_switch`) and contacts get a text element (`contact_state`,
`Otwarte`/`Zamknięte`). A mapping entry can set `"invert": true` plus
`text_true`/`text_false`; this is required for a native Sinum `gate`
`close_status_sensor`, which treats `true` as **closed** (HA door contacts
usually use `on` = open). Covers are not mirrored. The active AC mapping uses `variant: ac_module` / `class:
custom_device_module` (module 1) and maps HA climate mode/target to the real
Sinum air-conditioner module; the old generic AC (141) is only a bench.

The garage gate `switch.garaz_agrestowa` is a pulse-style output: each `turn_on`
pulse toggles open/close, while `turn_off` only releases the relay. The bridge
mirrors the Sinum switch element to HA; closing the gate therefore needs a
second pulse, not just switching the element off.

## Virtual test bench

A fake B7-local helper set and matching Sinum room **LAB Wirtualne** (13) let us
exercise gates, lamps, contacts and sensors without touching real hardware:
`input_boolean.sinum_lab_brama`, `input_boolean.sinum_lab_brama_kontaktron`,
`input_boolean.sinum_lab_lampa` + `light.sinum_lab_lampa`,
`input_number.sinum_lab_temperatura` and
`input_number.sinum_lab_wilgotnosc`. The mapping file contains the matching
entries. This bench is used for latency and echo-suppression tests. Fake
devices stay local to B7; nothing is published to the production MQTT discovery
prefix.

Groups, the Z2M bridge and the repeater are not mapped. Diagnostics such as
linkquality, last_seen and config switches are skipped.

## Safety

- Secrets belong in an environment file with mode 600; never commit them.
- Write-back can physically change Z2M devices. Test only with devices you own.
- The current test deployment is limited to **LAB Lukasz**, **LAB Działające**
  and **LAB Wirtualne**; devices outside those rooms are not touched until the
  label/room mapping is configured.
