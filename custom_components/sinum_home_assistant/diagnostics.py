"""Diagnostics support for the Sinum Home Assistant integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_DEVICE_ID, CONF_EMAIL, CONF_REFRESH_TOKEN

TO_REDACT = {
    CONF_EMAIL,
    CONF_DEVICE_ID,
    CONF_REFRESH_TOKEN,
    "password",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return safe diagnostics for a Sinum config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    bridge = getattr(coordinator, "bridge", None)
    bridge_info: dict[str, Any] = {"enabled": bridge is not None}
    if bridge is not None:
        bridge_info.update(
            {
                "mapping_count": bridge.mapping_count,
                "label": bridge.options.label,
                "room_id": bridge.options.room_id,
            }
        )

    device_counts = {
        group: len(items)
        for group, items in data.device_groups.items()
    }
    parent_counts = {
        group: len(items)
        for group, items in data.parent_groups.items()
    }
    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
            "rooms": len(data.rooms),
            "device_counts": device_counts,
            "parent_counts": parent_counts,
            "schedules": len(data.schedules),
            "weather": data.weather is not None,
        },
        "bridge": bridge_info,
    }
