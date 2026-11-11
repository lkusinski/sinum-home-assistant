# Z2M → Sinum bridge

One-way, read-only bridge: Home Assistant Z2M states → Sinum virtual custom devices.

- Source: B7 Home Assistant REST API (MQTT-discovered Z2M entities).
- Target: Sinum cloud API, room **LAB Lukasz**.
- The bridge **never writes to production Home Assistant**.
- Selection is prepared in B7 by device label `sinum` (mapping file is generated from those devices).
- `mapping.json` is generated from HA entities and Sinum virtual device IDs.

## Run

```bash
export B7_TOKEN='<long-lived token>'
export SINUM_EMAIL='...'
export SINUM_PASSWORD='...'
export SINUM_DEVICE_ID='...'
python3 z2m_to_sinum.py --once
python3 z2m_to_sinum.py --interval 30
```

A systemd unit should keep the token and Sinum credentials in an env file with
mode 600; do not commit them.

## Current limitations

- Lights are relay on/off; Sinum has no virtual `light` variant.
- Action buttons and Z2M groups are not mirrored.
- Continuous back-channel (Sinum → Z2M) is not implemented.
