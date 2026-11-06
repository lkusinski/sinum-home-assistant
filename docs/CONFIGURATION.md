# Configuration

Configuration is done entirely in the Home Assistant UI.

## Credentials

| Field | Description |
|---|---|
| E-mail | Sinum account e-mail. |
| Password | Sinum account password. Used only for login and reauthentication. |
| Cloud device ID | Hub `uid` from the Sinum app or hub settings. |

The password is not stored. A refresh token is saved in the config entry and
renewed automatically. Access tokens are kept in memory only.

## Options

Open **Settings → Devices & Services → Sinum Home Assistant → Configure**.

| Option | Default | Range | Notes |
|---|---:|---:|---|
| Polling interval | 30 s | 15–300 s | One full cloud update cycle. |
| Enable weather | on | — | Adds the weather entity and forecast. |
| Enable system modules | on | — | Adds extenders, transceivers and their diagnostics. |

Changing options reloads the config entry. Disabling weather or system modules
removes their entities from the registry; enabling them again recreates the
entities with the same unique IDs. Entity history is preserved.

## Reauthentication

If the refresh token becomes invalid, Home Assistant shows a repair action.
Enter the password again; the integration obtains a new refresh token.

## Multiple hubs

Each Sinum hub is a separate config entry. The cloud device ID is used as the
unique identifier, so adding the same hub twice is blocked.

## Removing

Remove the integration from **Settings → Devices & Services**. This deletes the
config entry, devices and entities created by the integration. Areas and their
other entities are not removed.
