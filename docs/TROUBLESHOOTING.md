# Troubleshooting

## Cannot add the integration

### Invalid e-mail or password

Check the credentials in the Sinum app. If the account uses a different login
method, use those credentials.

### Invalid cloud device ID

The cloud device ID is the hub `uid`. Copy it from the Sinum app or the hub
settings. Trailing spaces are removed automatically.

### Cannot connect

- Verify that Home Assistant has internet access.
- Check that `backend.prd.sinum24.com` is reachable.
- Retry after a minute; the cloud may be temporarily unavailable.

## Entities are unavailable

- Check the integration status on **Settings → Devices & Services**.
- Open the integration and select **Reload**.
- Check **Settings → System → Logs** for `sinum_home_assistant` errors.

A whole-hub failure usually means the cloud login or refresh token has expired.
Home Assistant will show a reauthentication prompt.

## Some sensors show `unknown`

Empty network fields (SSID, channel, signal) are normal for devices that do not
report Wi-Fi/Ethernet details. They are not errors.

## Weather is missing

- Confirm that **Enable weather** is on in the integration options.
- Reload the config entry.
- Some accounts or hubs do not expose weather data.

## Firmware update is not shown

The integration uses the cloud `update_details` field. If the cloud does not
report an available version, no update entity state change is possible.

## Entity IDs changed

Entity IDs depend on room and device names in Sinum. Renaming a room or device
in Sinum can change the generated entity ID on the next setup. Rename entities
in Home Assistant if you need stable IDs for dashboards and automations.

## Debug logging

```yaml
logger:
  default: warning
  logs:
    custom_components.sinum_home_assistant: debug
```

Restart Home Assistant or reload the integration, reproduce the problem, then
download the log from **Settings → System → Logs**.
