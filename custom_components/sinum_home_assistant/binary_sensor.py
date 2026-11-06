"""Binary sensor platform for Sinum Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SinumHomeAssistantCoordinator
from .data import is_managed_relay
from .entity import (
    SinumDeviceEntity,
    parent_device_info,
    system_module_device_info,
    virtual_device_info,
    wtp_device_info,
)

PARALLEL_UPDATES = 0

ONLINE = "Online"
OPENING = "Otwarcie"
TARGET_REACHED = "Osiągnięto temperaturę"
WINDOW_OPEN = "Okno otwarte"
HEATING = "Grzanie"
COOLING = "Chłodzenie"
LIGHT = "Światło"
ERROR = "Błąd"
WARNING = "Ostrzeżenie"
RELAY_STATE = "Stan przekaźnika"


class SinumDeviceBinarySensor(SinumDeviceEntity, BinarySensorEntity):
    """Binary sensor bound to a cloud device."""

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        device_id: int,
        store: str,
        name: str,
        value_fn: Callable[[dict[str, Any]], bool | None],
        *,
        device_class: BinarySensorDeviceClass | None = None,
        icon: str | None = None,
        entity_category: EntityCategory | None = None,
        use_device_status: bool = True,
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, store
        )
        self._attr_name = name
        self._value_fn = value_fn
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_entity_category = entity_category
        self._use_device_status = use_device_status

    @property
    def available(self) -> bool:
        if not self._use_device_status:
            return self.coordinator.last_update_success
        return super().available

    @property
    def is_on(self) -> bool | None:
        return self._value_fn(self._device())


class SinumRoomBinarySensor(SinumDeviceEntity, BinarySensorEntity):
    """Room flag exposed on the room thermostat device."""

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        device_id: int,
        room_id: int,
        key: str,
        name: str,
        *,
        device_class: BinarySensorDeviceClass | None = None,
        icon: str | None = None,
        entity_category: EntityCategory | None = None,
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, "virtual"
        )
        self._room_id = room_id
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_entity_category = entity_category

    @property
    def is_on(self) -> bool | None:
        room = self.coordinator.data.rooms.get(self._room_id)
        if room is None:
            return None
        return bool(room.get(self._key))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SinumHomeAssistantCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[BinarySensorEntity] = []

    for device_id, device in data.wtp.items():
        parent = data.parents_wtp.get(device.get("parent_id"))
        info = wtp_device_info(entry.entry_id, device, parent, data)
        device_type = device.get("type")
        if device_type == "opening_sensor":
            entities.append(
                SinumDeviceBinarySensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_opening",
                    device_id,
                    "wtp",
                    OPENING,
                    lambda d: bool(d.get("open")),
                    device_class=BinarySensorDeviceClass.WINDOW,
                )
            )
        elif device_type == "temperature_regulator":
            entities.append(
                SinumDeviceBinarySensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_target_reached",
                    device_id,
                    "wtp",
                    TARGET_REACHED,
                    lambda d: d.get("target_temperature_reached"),
                    icon="mdi:thermometer-check",
                )
            )
        elif device_type == "relay" and is_managed_relay(device):
            entities.append(
                SinumDeviceBinarySensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_relay_state",
                    device_id,
                    "wtp",
                    RELAY_STATE,
                    lambda d: d.get("state") is True,
                    device_class=BinarySensorDeviceClass.POWER,
                    icon="mdi:electric-switch",
                )
            )

    for parent_id, parent in data.parents_wtp.items():
        info = parent_device_info(entry.entry_id, parent, data)
        entities.append(
            SinumDeviceBinarySensor(
                coordinator,
                info,
                f"wtp_parent_{parent_id}_online",
                parent_id,
                "parents_wtp",
                ONLINE,
                lambda d: d.get("status") == "online",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
                use_device_status=False,
            )
        )

    for device_id, device in data.virtual.items():
        info = virtual_device_info(entry.entry_id, device, data)
        room_id = device.get("room_id")
        entities.append(
            SinumDeviceBinarySensor(
                coordinator,
                info,
                f"virtual_{device_id}_window",
                device_id,
                "virtual",
                WINDOW_OPEN,
                lambda d: bool(d.get("is_window_open")),
                device_class=BinarySensorDeviceClass.WINDOW,
            )
        )
        if isinstance(room_id, int):
            entities.extend(
                [
                    SinumRoomBinarySensor(
                        coordinator,
                        info,
                        f"virtual_{device_id}_heating",
                        device_id,
                        room_id,
                        "is_heating",
                        HEATING,
                        device_class=BinarySensorDeviceClass.HEAT,
                    ),
                    SinumRoomBinarySensor(
                        coordinator,
                        info,
                        f"virtual_{device_id}_cooling",
                        device_id,
                        room_id,
                        "is_cooling",
                        COOLING,
                        device_class=BinarySensorDeviceClass.COLD,
                    ),
                    SinumRoomBinarySensor(
                        coordinator,
                        info,
                        f"virtual_{device_id}_light",
                        device_id,
                        room_id,
                        "is_light_on",
                        LIGHT,
                        device_class=BinarySensorDeviceClass.LIGHT,
                    ),
                    SinumRoomBinarySensor(
                        coordinator,
                        info,
                        f"virtual_{device_id}_error",
                        device_id,
                        room_id,
                        "has_error",
                        ERROR,
                        device_class=BinarySensorDeviceClass.PROBLEM,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    SinumRoomBinarySensor(
                        coordinator,
                        info,
                        f"virtual_{device_id}_warning",
                        device_id,
                        room_id,
                        "has_warning",
                        WARNING,
                        device_class=BinarySensorDeviceClass.PROBLEM,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                ]
            )

    if coordinator.enable_system_modules:
        for device_id, device in data.system_modules.items():
            info = system_module_device_info(entry.entry_id, device, data)
            entities.append(
                SinumDeviceBinarySensor(
                    coordinator,
                    info,
                    f"system_module_{device_id}_online",
                    device_id,
                    "system_modules",
                    ONLINE,
                    lambda d: d.get("status") == "online",
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    use_device_status=False,
                )
            )

    async_add_entities(entities)
