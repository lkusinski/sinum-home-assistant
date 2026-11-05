# Installation

## Requirements

- Home Assistant **2026.11** or newer.
- A working Sinum installation with cloud access.
- The Sinum account that owns the hub.
- The hub cloud device ID (`uid`).

## HACS

1. Open **HACS → Integrations**.
2. Open the three-dot menu and select **Custom repositories**.
3. Enter `https://github.com/lkusinski/sinum-home-assistant` and choose
   **Integration**.
4. Search for **Sinum Home Assistant** and install it.
5. Restart Home Assistant.
6. Open **Settings → Devices & Services → Add Integration** and choose
   **Sinum Home Assistant**.

## Manual

1. Copy the `custom_components/sinum_home_assistant` directory into
   `config/custom_components/`.
2. Restart Home Assistant.
3. Add the integration from **Settings → Devices & Services**.

## First setup

1. Enter the Sinum account e-mail and password.
2. Enter the cloud device ID.
3. Wait for the first poll to finish.

The integration creates a hub device, room areas, parent controllers and all
supported entities. A typical installation takes less than a minute.

## Updating

- HACS: install the new release and restart Home Assistant.
- Manual: replace the integration directory and restart Home Assistant.

The config entry and entity history are preserved across updates.
