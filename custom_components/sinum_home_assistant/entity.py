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


def schedule_device_info(
    entry_id: str, schedule: dict[str, Any], data: SinumHomeAssistantData
) -> DeviceInfo:
    schedule_id = int(schedule["id"])
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_schedule_{schedule_id}")},
        name=f"Harmonogram: {str(schedule.get('name') or schedule_id).strip()}",
        manufacturer=MANUFACTURER,
        model="Harmonogram",
        via_device_id=data.hub_device_id,
    )


def generic_device_info(
    entry_id: str,
    group: str,
    device: dict[str, Any],
    data: SinumHomeAssistantData,
) -> DeviceInfo:
    device_id = int(device["id"])
    software = str(device.get("software_version") or "")
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{group}_{device_id}")},
        name=str(device.get("name") or f"{group} {device_id}").strip(),
        manufacturer=MANUFACTURER,
        model=software.split(" v")[0] if software else group.upper(),
        sw_version=software,
        serial_number=str(device.get("address") or device.get("uuid") or ""),
        suggested_area=_room(data, device),
    )
    parent_id = device.get("parent_id")
    if isinstance(parent_id, int):
        via = data.parent_ids.get(group, {}).get(parent_id)
        if via is not None:
            device_info["via_device_id"] = via
    return device_info


def generic_parent_device_info(
    entry_id: str,
    group: str,
    parent: dict[str, Any],
    data: SinumHomeAssistantData,
) -> DeviceInfo:
    parent_id = int(parent["id"])
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{group}_parent_{parent_id}")},
        name=str(parent.get("name") or f"{group} {parent_id}").strip(),
        manufacturer=MANUFACTURER,
        model=str(parent.get("model") or group.upper()),
        sw_version=str(parent.get("version") or ""),
        serial_number=str(parent.get("address") or parent.get("uuid") or ""),
        suggested_area=data.area_names.get(f"{group}_parent_{parent_id}"),
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
        if self._store.startswith("parents:"):
            group = self._store.split(":", 1)[1]
            store = self.coordinator.data.parent_groups.get(group, {})
        else:
            store = self.coordinator.data.device_groups.get(self._store)
            if store is None:
                store = getattr(self.coordinator.data, self._store, {})
        return store.get(self._device_id, {})

    @property
    def available(self) -> bool:
        device = self._device()
        if not self.coordinator.last_update_success:
            return False
        if device.get("status") == "online":
            return True
        return (
            self._store == "virtual"
            and device.get("type") == "custom_device"
            and device.get("variant") == "temperature_sensor"
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

    for group, parents in data.parent_groups.items():
        if group in ("wtp", "system_module"):
            continue
        parent_ids = data.parent_ids.setdefault(group, {})
        for parent_id, parent in parents.items():
            parent_device = devices.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={
                    (DOMAIN, f"{entry.entry_id}_{group}_parent_{parent_id}")
                },
                name=str(parent.get("name") or f"{group} {parent_id}").strip(),
                manufacturer=MANUFACTURER,
                model=str(parent.get("model") or group.upper()),
                sw_version=str(parent.get("version") or ""),
                serial_number=str(
                    parent.get("address") or parent.get("uuid") or ""
                ),
                suggested_area=data.area_names.get(
                    f"{group}_parent_{parent_id}"
                ),
                via_device_id=hub.id,
            )
            parent_ids[parent_id] = parent_device.id

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


def async_remove_schedule_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove schedule entities when the option is disabled."""

    _async_remove_entities_by_prefix(
        hass, entry, f"{entry.entry_id}_schedule_"
    )


def async_remove_deprecated_entities(
    hass: HomeAssistant, entry: ConfigEntry, data: SinumHomeAssistantData
) -> None:
    """Remove entities now represented on their parent or as attributes."""

    obsolete: set[str] = set()
    for device_id in data.wtp:
        obsolete.add(f"{entry.entry_id}_wtp_{device_id}_signal")
        obsolete.add(f"{entry.entry_id}_wtp_{device_id}_battery")
    for parent_id in data.parents_wtp:
        obsolete.add(f"{entry.entry_id}_wtp_parent_{parent_id}_signal")
        obsolete.add(f"{entry.entry_id}_wtp_parent_{parent_id}_battery")
    for device_id, device in data.virtual.items():
        obsolete.add(f"{entry.entry_id}_virtual_{device_id}_online")
        obsolete.add(f"{entry.entry_id}_virtual_{device_id}_problem")
        if device.get("type") != "thermostat":
            continue
        obsolete.add(f"{entry.entry_id}_virtual_{device_id}_temperature")
        obsolete.add(f"{entry.entry_id}_virtual_{device_id}_humidity")
    for schedule_id in data.schedules:
        obsolete.add(f"{entry.entry_id}_schedule_{schedule_id}_fallback")
        obsolete.add(f"{entry.entry_id}_schedule_{schedule_id}_devices")
    for device_id, device in data.wtp.items():
        if device.get("type") == "relay" and is_managed_relay(device):
            obsolete.add(f"{entry.entry_id}_wtp_{device_id}_relay_state")
    for device_id, device in data.system_modules.items():
        if device.get("network_signal") is None:
            obsolete.add(f"{entry.entry_id}_system_module_{device_id}_signal")
        if device.get("network_channel") is None:
            obsolete.add(f"{entry.entry_id}_system_module_{device_id}_channel")
        if device.get("network_name") is None:
            obsolete.add(f"{entry.entry_id}_system_module_{device_id}_network")
        if not device.get("ip") or device.get("ip") == "127.0.0.1":
            obsolete.add(f"{entry.entry_id}_system_module_{device_id}_ip")

    registry = er.async_get(hass)
    for entity in list(registry.entities.values()):
        if (
            entity.config_entry_id == entry.entry_id
            and entity.unique_id in obsolete
        ):
            registry.async_remove(entity.entity_id)


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
