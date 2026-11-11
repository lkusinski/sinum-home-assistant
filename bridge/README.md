# Z2M → Sinum bridge

Bridge between Home Assistant Zigbee2MQTT devices and Sinum virtual custom
devices in the private test room **LAB Lukasz**.

## Direction

- **Z2M / HA → Sinum**: every 30 s the worker mirrors selected states.
- **Sinum → Z2M** (relay/light on-off): optional write-back. It is enabled with
  `WRITE_BACK=1`; set `WRITE_BACK=0` for a strictly one-way mirror.
- The bridge does **not modify production Home Assistant**. It only uses the B7
  Home Assistant REST API and the MQTT-backed Z2M entities already present there.

## Files

- `mapping.json` — HA entity → Sinum virtual device mapping.
- `z2m_to_sinum.py` — state worker.
- `map_z2m.py` — creates missing devices from B7 devices labelled `sinum`.
- `sinum-z2m.service.example` — systemd unit.

## Run

```bash
export B7_TOKEN='<long-lived token>'
export SINUM_EMAIL='...'
export SINUM_PASSWORD='...'
export SINUM_DEVICE_ID='...'
export SINUM_ROOM_ID=11
export STATE_FILE=/var/lib/sinum-z2m/state.json
export SINUM_STATE_FILE=/var/lib/sinum-z2m/sinum_state.json
python3 z2m_to_sinum.py --once
python3 z2m_to_sinum.py --interval 30
```

Set `WRITE_BACK=0` to disable Sinum → HA commands.

## Mapping policy

The current test mapping uses 91 functional endpoints: relays (including lights
on/off), two-state contacts, temperature/humidity, analog values, energy and
battery. Sinum has no virtual `light` or `cover` variant; brightness/color and
covers are not mirrored.

Groups, the Z2M bridge and the repeater are not mapped. Diagnostics such as
linkquality, last_seen and config switches are skipped.

## Safety

- Secrets belong in an environment file with mode 600; never commit them.
- Write-back can physically change Z2M devices. Test only with devices you own.
- Sinum side is limited to the test room **LAB Lukasz**.
