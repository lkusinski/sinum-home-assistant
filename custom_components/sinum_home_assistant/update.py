"""Firmware update platform for Sinum Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SinumHomeAssistantCoordinator
from .entity import (
    SinumDeviceEntity,
    parent_device_info,
    system_module_device_info,
)

PARALLEL_UPDATES = 0

UPDATING_STATUSES = {
    "updating",
    "update_in_progress",
    "installing",
    "in_progress",
}


class SinumFirmwareUpdate(SinumDeviceEntity, UpdateEntity):
    """Firmware update entity for a WTP parent or system module."""

    _attr_name = None

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        device_id: int,
        store: str,
        details_store: str | None = None,
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, store
        )
        self._details_store = details_store

    def _device(self) -> dict[str, Any]:
        device = dict(super()._device())
        if self._details_store is not None:
            details = getattr(
                self.coordinator.data, self._details_store, {}
            ).get(self._device_id, {})
            if details:
                device.setdefault(
                    "update_details", details.get("update_details")
                )
                device["version"] = (
                    details.get("version")
                    or device.get("software_version")
                )
                device["software_status"] = details.get(
                    "software_status", device.get("software_status")
                )
        return device

    def _details(self) -> dict[str, Any]:
        details = self._device().get("update_details")
        return details if isinstance(details, dict) else {}

    @property
    def installed_version(self) -> str | None:
        version = self._device().get("version")
        if version:
            return str(version)
        software = self._device().get("software_version")
        return str(software) if software else None

    @property
    def latest_version(self) -> str | None:
        installed = self.installed_version
        available = self._details().get("available_version")
        if available and str(available) != installed:
            return str(available)
        return installed

    @property
    def in_progress(self) -> bool | int:
        device = self._device()
        if device.get("software_status") not in UPDATING_STATUSES:
            return False
        progress = self._details().get("progress")
        if isinstance(progress, int):
            return max(progress, 1)
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes)
        device = self._device()
        attrs.update(
            {
                "software_status": device.get("software_status"),
                "update_details": self._details(),
                "model": device.get("model")
                or device.get("software_version"),
            }
        )
        return attrs

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        raise HomeAssistantError(
            "Firmware updates must be started in the Sinum app"
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SinumHomeAssistantCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[UpdateEntity] = []

    for parent_id, parent in data.parents_wtp.items():
        entities.append(
            SinumFirmwareUpdate(
                coordinator,
                parent_device_info(entry.entry_id, parent, data),
                f"wtp_parent_{parent_id}_update",
                parent_id,
                "parents_wtp",
            )
        )

    if coordinator.enable_system_modules:
        for device_id, device in data.system_modules.items():
            entities.append(
                SinumFirmwareUpdate(
                    coordinator,
                    system_module_device_info(entry.entry_id, device, data),
                    f"system_module_{device_id}_update",
                    device_id,
                    "system_modules",
                    "parents_system_module",
                )
            )

    async_add_entities(entities)
