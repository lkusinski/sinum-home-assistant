"""Sinum Home Assistant integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SinumAuthError, SinumHomeAssistantClient, SinumHomeAssistantError
from .const import CONF_DEVICE_ID, CONF_EMAIL, CONF_REFRESH_TOKEN, PLATFORMS
from .coordinator import SinumHomeAssistantCoordinator
from .entity import (
    async_assign_areas,
    async_ensure_device_hierarchy,
    async_remove_stale_relay_switches,
    async_remove_system_module_entities,
    async_remove_weather_entities,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sinum Home Assistant from a config entry."""

    async def _store_refresh_token(token: str) -> None:
        if entry.data.get(CONF_REFRESH_TOKEN) == token:
            return
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_REFRESH_TOKEN: token},
        )

    client = SinumHomeAssistantClient(
        async_get_clientsession(hass),
        email=entry.data[CONF_EMAIL],
        device_id=entry.data[CONF_DEVICE_ID],
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        token_update=_store_refresh_token,
    )

    try:
        await client.async_ensure_token()
    except SinumAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SinumHomeAssistantError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = SinumHomeAssistantCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    async_ensure_device_hierarchy(
        hass, entry, coordinator.data, coordinator.enable_system_modules
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_remove_stale_relay_switches(hass, entry, coordinator.data)
    if not coordinator.enable_system_modules:
        async_remove_system_module_entities(hass, entry)
    if not coordinator.enable_weather:
        async_remove_weather_entities(hass, entry)
    await async_assign_areas(hass, entry, coordinator.data)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Sinum Home Assistant config entry."""

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data = None
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: SinumHomeAssistantCoordinator | None = entry.runtime_data
    if coordinator is not None and dict(entry.options) != coordinator.options:
        await hass.config_entries.async_reload(entry.entry_id)
