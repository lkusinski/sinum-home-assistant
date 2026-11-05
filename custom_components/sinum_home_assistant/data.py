"""Normalized data model for the Sinum Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import TEMP_SCALE


def _index(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for item in items:
        try:
            result[int(item["id"])] = item
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _scaled(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value) * TEMP_SCALE, 1)
    return None


@dataclass(slots=True)
class SinumHomeAssistantData:
    """Snapshot of the Sinum cloud state."""

    info: dict[str, Any] = field(default_factory=dict)
    rooms: dict[int, dict[str, Any]] = field(default_factory=dict)
    parents_wtp: dict[int, dict[str, Any]] = field(default_factory=dict)
    parents_system_module: dict[int, dict[str, Any]] = field(default_factory=dict)
    wtp: dict[int, dict[str, Any]] = field(default_factory=dict)
    virtual: dict[int, dict[str, Any]] = field(default_factory=dict)
    system_modules: dict[int, dict[str, Any]] = field(default_factory=dict)
    weather: dict[str, Any] | None = None
    room_names: dict[int, str] = field(default_factory=dict)
    hub_device_id: str | None = None
    wtp_parent_ids: dict[int, str] = field(default_factory=dict)
    system_parent_ids: dict[int, str] = field(default_factory=dict)
    virtual_by_room: dict[int, dict[str, Any]] = field(default_factory=dict)
    regulator_temperature: dict[int, float | None] = field(default_factory=dict)
    area_names: dict[str, str] = field(default_factory=dict)

    def room_name(self, room_id: Any) -> str | None:
        try:
            return self.room_names.get(int(room_id))
        except (TypeError, ValueError):
            return None

    def current_temperature(self, device: dict[str, Any]) -> float | None:
        raw = device.get("temperature")
        scaled = _scaled(raw)
        if scaled is not None:
            return scaled
        try:
            return self.regulator_temperature.get(int(device["id"]))
        except (KeyError, TypeError, ValueError):
            return None

    def device_online(self, device: dict[str, Any]) -> bool:
        return device.get("status") == "online"

    def has_problem(self, device: dict[str, Any]) -> bool:
        if device.get("messages"):
            return True
        return bool(device.get("has_messages"))


def build_data(
    *,
    info: dict[str, Any],
    rooms: list[dict[str, Any]],
    parents: dict[str, list[dict[str, Any]]],
    devices: dict[str, list[dict[str, Any]]],
    weather: dict[str, Any] | None,
) -> SinumHomeAssistantData:
    data = SinumHomeAssistantData(info=info, weather=weather)

    data.rooms = _index(rooms)
    data.room_names = {
        room_id: str(room.get("name") or f"Room {room_id}").strip()
        for room_id, room in data.rooms.items()
    }

    data.parents_wtp = _index(parents.get("wtp", []))
    data.parents_system_module = _index(parents.get("system_module", []))
    data.wtp = _index(devices.get("wtp", []))
    data.virtual = _index(devices.get("virtual", []))
    data.system_modules = _index(devices.get("system_module", []))

    for device in data.virtual.values():
        room_id = device.get("room_id")
        if isinstance(room_id, int) and room_id not in data.virtual_by_room:
            data.virtual_by_room[room_id] = device

    for device_id, device in data.wtp.items():
        if device.get("type") != "temperature_regulator":
            continue
        temperature: float | None = None
        room_id = device.get("room_id")
        virtual = (
            data.virtual_by_room.get(room_id)
            if isinstance(room_id, int)
            else None
        )
        if virtual is not None:
            temperature = _scaled(virtual.get("temperature"))
        if temperature is None:
            association = (
                (device.get("associations") or {})
                .get("room_temperature_sensor", {})
            )
            sensor = data.wtp.get(association.get("id"))
            if sensor is not None:
                temperature = _scaled(sensor.get("temperature"))
        data.regulator_temperature[device_id] = temperature

    parent_rooms: dict[int, set[int]] = {}
    for device in data.wtp.values():
        parent_id = device.get("parent_id")
        room_id = device.get("room_id")
        if isinstance(parent_id, int) and isinstance(room_id, int):
            parent_rooms.setdefault(parent_id, set()).add(room_id)

    for parent_id, room_ids in parent_rooms.items():
        if len(room_ids) != 1:
            continue
        name = data.room_name(next(iter(room_ids)))
        if name:
            data.area_names[f"wtp_parent_{parent_id}"] = name

    for device_id, device in data.wtp.items():
        name = data.room_name(device.get("room_id"))
        if name:
            data.area_names[f"wtp_{device_id}"] = name
    for device_id, device in data.virtual.items():
        name = data.room_name(device.get("room_id"))
        if name:
            data.area_names[f"virtual_{device_id}"] = name
    for device_id, device in data.system_modules.items():
        name = data.room_name(device.get("room_id"))
        if name:
            data.area_names[f"system_module_{device_id}"] = name

    return data
