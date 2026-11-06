"""Shared entity and device helpers for Sinum Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SinumHomeAssistantCoordinator
from .data import SinumHomeAssistantData, is_managed_relay


def _room(data: SinumHomeAssistantData, device: dict[str, Any]) -> str | None:
    return data.room_name(device.get("room_id"))


def hub_device_info(entry_id: str, data: SinumHomeAssistantData) -> DeviceInfo:
    info = data.info
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_hub")},
        name="Sinum Home Assistant",
        manufacturer=MANUFACTURER,
        model=str(info.get("device_type") or MODEL),
        sw_version=str(info.get("version") or ""),
        serial_number=str(info.get("uid") or ""),
        configuration_url="https://sinum.tech/",
    )


def weather_device_info(entry_id: str, data: SinumHomeAssistantData) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_weather")},
        name="Sinum Weather",
        manufacturer=MANUFACTURER,
        model="Weather",
        via_device_id=data.hub_device_id,
    )


def parent_device_info(
    entry_id: str, parent: dict[str, Any], data: SinumHomeAssistantData
) -> DeviceInfo:
    parent_id = int(parent["id"])
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_wtp_parent_{parent_id}")},
        name=str(parent.get("name") or f"WTP {parent_id}").strip(),
        manufacturer=MANUFACTURER,
        model=str(parent.get("model") or "WTP"),
        sw_version=str(parent.get("version") or ""),
        suggested_area=data.area_names.get(f"wtp_parent_{parent_id}"),
        via_device_id=data.hub_device_id,
    )


def system_module_device_info(
    entry_id: str, device: dict[str, Any], data: SinumHomeAssistantData
) -> DeviceInfo:
    device_id = int(device["id"])
    software = str(device.get("software_version") or "")
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_system_module_{device_id}")},
        name=str(device.get("name") or f"System module {device_id}").strip(),
        manufacturer=MANUFACTURER,
        model=software.split(" v")[0] if software else "System module",
        sw_version=software,
        serial_number=str(device.get("uuid") or ""),
        suggested_area=_room(data, device),
        via_device_id=data.system_parent_ids.get(
            int(device.get("parent_id") or 0), data.hub_device_id
        ),
    )


def wtp_device_info(
    entry_id: str,
    device: dict[str, Any],
    parent: dict[str, Any] | None,
    data: SinumHomeAssistantData,
) -> DeviceInfo:
    device_id = int(device["id"])
    software = str(device.get("software_version") or "")
    name = str(device.get("name") or f"WTP {device_id}").strip()
    room = _room(data, device)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_wtp_{device_id}")},
        name=name,
        manufacturer=MANUFACTURER,
        model=software.split(" v")[0] if software else "WTP",
        sw_version=software,
        serial_number=str(device.get("address") or ""),
        suggested_area=room,
    )
    if parent is not None:
        device_info["via_device_id"] = data.wtp_parent_ids.get(
            int(parent["id"])
        )
    return device_info


def virtual_device_info(
    entry_id: str, device: dict[str, Any], data: SinumHomeAssistantData
) -> DeviceInfo:
    device_id = int(device["id"])
    room = _room(data, device)
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_virtual_{device_id}")},
        name=str(device.get("name") or f"Thermostat {device_id}").strip(),
        manufacturer=MANUFACTURER,
        model="Virtual Thermostat",
        suggested_area=room,
        via_device_id=data.hub_device_id,
    )


class SinumHomeAssistantEntity(CoordinatorEntity[SinumHomeAssistantCoordinator]):
    """Base entity for the cloud hub and weather devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: DeviceInfo,
        unique_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{unique_key}"
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class SinumDeviceEntity(SinumHomeAssistantEntity):
    """Base entity bound to one cloud device."""

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: DeviceInfo,
        unique_key: str,
        device_id: int,
        store: str,
    ) -> None:
        super().__init__(coordinator, device_info, unique_key)
        self._device_id = device_id
        self._store = store

    def _device(self) -> dict[str, Any]:
        store = getattr(self.coordinator.data, self._store, {})
        return store.get(self._device_id, {})

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self._device().get("status") == "online"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self._device()
        room = self.coordinator.data.room_name(device.get("room_id"))
        attrs: dict[str, Any] = {
            "sinum_id": self._device_id,
            "sinum_class": device.get("class"),
            "sinum_type": device.get("type"),
        }
        if room:
            attrs["room"] = room
        if device.get("signal") is not None:
            attrs["signal"] = device.get("signal")
        if device.get("battery") is not None:
            attrs["battery"] = device.get("battery")
        if device.get("software_version"):
            attrs["software_version"] = device.get("software_version")
        if device.get("messages"):
            attrs["messages"] = device.get("messages")
        if device.get("has_messages") is not None:
            attrs["has_messages"] = device.get("has_messages")
        return attrs


def async_ensure_device_hierarchy(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: SinumHomeAssistantData,
    include_system_modules: bool = True,
) -> None:
    """Create hub and parent devices before child entities are added."""

    devices = dr.async_get(hass)
    info = data.info
    hub = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_hub")},
        name="Sinum Home Assistant",
        manufacturer=MANUFACTURER,
        model=str(info.get("device_type") or MODEL),
        sw_version=str(info.get("version") or ""),
        serial_number=str(info.get("uid") or ""),
        configuration_url="https://sinum.tech/",
    )
    data.hub_device_id = hub.id

    for parent_id, parent in data.parents_wtp.items():
        parent_device = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_wtp_parent_{parent_id}")},
            name=str(parent.get("name") or f"WTP {parent_id}").strip(),
            manufacturer=MANUFACTURER,
            model=str(parent.get("model") or "WTP"),
            sw_version=str(parent.get("version") or ""),
            suggested_area=data.area_names.get(f"wtp_parent_{parent_id}"),
            via_device_id=hub.id,
        )
        data.wtp_parent_ids[parent_id] = parent_device.id

    if not include_system_modules:
        return

    for parent_id, parent in data.parents_system_module.items():
        parent_device = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={
                (DOMAIN, f"{entry.entry_id}_system_parent_{parent_id}")
            },
            name=str(parent.get("name") or f"System module {parent_id}").strip(),
            manufacturer=MANUFACTURER,
            model=str(parent.get("model") or "System module"),
            sw_version=str(parent.get("version") or ""),
            via_device_id=hub.id,
        )
        data.system_parent_ids[parent_id] = parent_device.id


def _async_remove_entities_by_prefix(
    hass: HomeAssistant, entry: ConfigEntry, prefix: str
) -> None:
    registry = er.async_get(hass)
    for entity in list(registry.entities.values()):
        if (
            entity.config_entry_id == entry.entry_id
            and entity.unique_id.startswith(prefix)
        ):
            registry.async_remove(entity.entity_id)


def async_remove_system_module_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove system-module entities when the option is disabled."""

    _async_remove_entities_by_prefix(
        hass, entry, f"{entry.entry_id}_system_module_"
    )


def async_remove_weather_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove weather entities when the option is disabled."""

    _async_remove_entities_by_prefix(hass, entry, f"{entry.entry_id}_weather")


def async_remove_stale_relay_switches(
    hass: HomeAssistant, entry: ConfigEntry, data: SinumHomeAssistantData
) -> None:
    """Remove old switch entities for relays now managed by a thermostat."""

    registry = er.async_get(hass)
    for device_id, device in data.wtp.items():
        if device.get("type") != "relay":
            continue
        if not is_managed_relay(device):
            continue
        unique_id = f"{entry.entry_id}_wtp_{device_id}_switch"
        entity_id = registry.async_get_entity_id("switch", DOMAIN, unique_id)
        if entity_id is not None:
            registry.async_remove(entity_id)


async def async_assign_areas(
    hass: HomeAssistant, entry: ConfigEntry, data: SinumHomeAssistantData
) -> None:
    """Assign new devices to existing or newly created areas."""

    areas = ar.async_get(hass)
    devices = dr.async_get(hass)

    for key, area_name in data.area_names.items():
        area = areas.async_get_area_by_name(area_name)
        if area is None:
            area = areas.async_create(area_name)
        device = devices.async_get_device_by_identifier(
            (DOMAIN, f"{entry.entry_id}_{key}"), entry.entry_id
        )
        if device is not None and device.area_id is None:
            devices.async_update_device(device.id, area_id=area.id)
