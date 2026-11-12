"""Async Home Assistant <-> Sinum virtual-device bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from random import randint
from secrets import choice
from string import ascii_lowercase, digits
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .api import SinumApiError, SinumHomeAssistantClient, SinumHomeAssistantError
from .const import (
    CONF_BRIDGE_ENABLED,
    CONF_BRIDGE_LABEL,
    CONF_BRIDGE_ROOM_ID,
    DEFAULT_BRIDGE_LABEL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STREAM_RECONNECT = 5
RECENT_SECONDS = 15
RECONCILE_SECONDS = 60
MAPPING_FILE = "sinum_bridge/mapping.json"
STORE_VERSION = 1


@dataclass(slots=True)
class BridgeOptions:
    """Resolved bridge options."""

    enabled: bool
    label: str
    room_id: int


def _hex_to_rgb(value: str) -> list[int]:
    value = value.lstrip("#")
    return [int(value[index : index + 2], 16) for index in (0, 2, 4)]


def _sensor_text_layout(
    element: str, text: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    element_uuid = str(uuid.uuid4())
    row_uuid = str(uuid.uuid4())
    cell_uuid = str(uuid.uuid4())
    layout = {
        "type": "text",
        "name": element,
        "uuid": element_uuid,
        "enabled": True,
        "visibility": "visible",
        "value": text,
        "text_id": 0,
        "icon": "",
        "font_weight": "normal",
        "font_size": "large",
        "on_change": "onSensorTextChange",
    }
    widget = {
        "version": 2,
        "content": [
            {
                "id": row_uuid,
                "type": "row",
                "cells": [
                    {
                        "id": cell_uuid,
                        "type": "row",
                        "orientation": "row",
                        "vertical_alignment": "center",
                        "horizontal_alignment": "center",
                        "elements": [
                            {"uuid": element_uuid, "variant": "text-default"}
                        ],
                    }
                ],
            }
        ],
    }
    return layout, widget


def _relay_switch_layout(
    element: str, value: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    element_uuid = str(uuid.uuid4())
    row_uuid = str(uuid.uuid4())
    cell_uuid = str(uuid.uuid4())
    layout = {
        "type": "switcher",
        "name": element,
        "uuid": element_uuid,
        "enabled": True,
        "visibility": "visible",
        "value": bool(value),
        "on_change": "onRelaySwitchChange",
    }
    widget = {
        "version": 2,
        "content": [
            {
                "id": row_uuid,
                "type": "row",
                "cells": [
                    {
                        "id": cell_uuid,
                        "type": "row",
                        "orientation": "row",
                        "vertical_alignment": "center",
                        "horizontal_alignment": "center",
                        "elements": [
                            {"uuid": element_uuid, "variant": "switch-default"}
                        ],
                    }
                ],
            }
        ],
    }
    return layout, widget


def _sensor_text(entry: dict[str, Any], value: Any) -> str:
    scale = float(entry.get("scale") or 1)
    number = float(value) / scale
    unit = str(entry.get("unit") or "").strip()
    return f"{number:.1f} {unit}".strip()


def _two_state_text(entry: dict[str, Any], value: Any) -> str:
    if value:
        return str(entry.get("text_true") or "Otwarte")
    return str(entry.get("text_false") or "Zamknięte")


def _ha_light_values(state: State) -> dict[str, Any]:
    attrs = state.attributes
    brightness = attrs.get("brightness")
    rgb = attrs.get("rgb_color")
    color = None
    if isinstance(rgb, list) and len(rgb) == 3:
        color = "#{:02x}{:02x}{:02x}".format(*[int(value) for value in rgb])
    return {
        "state": state.state == "on",
        "brightness": round(brightness * 100 / 255)
        if isinstance(brightness, (int, float))
        else None,
        "color_mode": attrs.get("color_mode"),
        "temperature": attrs.get("color_temp_kelvin"),
        "color": color,
    }


def _sinum_color_mode(value: Any) -> Any:
    return "color_temp" if value == "temperature" else value


def _sinum_light_values(device: dict[str, Any]) -> dict[str, Any] | None:
    for element in device.get("elements") or []:
        if element.get("name") == "light":
            return {
                "state": bool(element.get("state")),
                "brightness": element.get("brightness"),
                "color_mode": _sinum_color_mode(element.get("color_mode")),
                "temperature": element.get("temperature"),
                "color": element.get("color"),
            }
    return None


def _ha_ac_values(state: State) -> dict[str, Any]:
    attrs = state.attributes
    mode = str(state.state or "off")
    return {
        "state": mode != "off",
        "hvac_mode": mode,
        "temperature": attrs.get("temperature"),
        "current_temperature": attrs.get("current_temperature"),
    }


def _ac_mode_to_sinum(mode: str) -> str:
    return {
        "off": "off",
        "auto": "automatic",
        "cool": "cooling",
        "heat": "heating",
        "fan_only": "fan",
        "dry": "drying",
    }.get(mode, "off")


def _ac_mode_to_ha(mode: str) -> str:
    return {
        "off": "off",
        "automatic": "auto",
        "cooling": "cool",
        "heating": "heat",
        "fan": "fan_only",
        "drying": "dry",
    }.get(mode, "off")


def _sinum_ac_values(module: dict[str, Any]) -> dict[str, Any]:
    mode = str(module.get("mode") or "off")
    target = module.get("target_temperature")
    room = module.get("room_temperature")
    return {
        "state": mode != "off",
        "hvac_mode": _ac_mode_to_ha(mode),
        "temperature": round(float(target) / 10, 1)
        if isinstance(target, (int, float))
        else None,
        "current_temperature": round(float(room) / 10, 1)
        if isinstance(room, (int, float))
        else None,
    }


def _value_for(entry: dict[str, Any], state: State) -> Any | None:
    raw = state.state
    if raw in (None, "unavailable", "unknown"):
        return None
    variant = entry["variant"]
    if variant in ("relay", "two_state_input_sensor"):
        value = raw in ("on", "open", "True", "true", True)
        if entry.get("invert"):
            value = not value
        return value
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if entry.get("scale"):
        return int(round(number * float(entry["scale"])))
    if variant == "battery":
        return max(0, min(100, int(round(number))))
    return round(number, 3)


def _payload_for(entry: dict[str, Any], value: Any) -> dict[str, Any] | None:
    variant = entry["variant"]
    field = entry["field"]
    if variant == "analog_input":
        return {"unit": entry.get("unit", ""), "value": value}
    return {field: value}


def _mapping_payload(entry: dict[str, Any], value: Any) -> dict[str, Any]:
    payload = _payload_for(entry, value)
    return payload or {}


class SinumBridge:
    """Bridge selected Home Assistant entities to Sinum virtual devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SinumHomeAssistantClient,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.options = BridgeOptions(
            enabled=bool(entry.options.get(CONF_BRIDGE_ENABLED, True)),
            label=str(
                entry.options.get(CONF_BRIDGE_LABEL, DEFAULT_BRIDGE_LABEL)
            ).strip()
            or DEFAULT_BRIDGE_LABEL,
            room_id=int(entry.options.get(CONF_BRIDGE_ROOM_ID, 0) or 0),
        )
        self._store = Store(
            hass, STORE_VERSION, f"{DOMAIN}.bridge"
        )
        self._mapping_file = Path(hass.config.path(MAPPING_FILE))
        self._mapping: dict[str, dict[str, Any]] = {}
        self._by_id: dict[int, tuple[str, dict[str, Any]]] = {}
        self._mapping_mtime = 0.0
        self._last_map = 0.0
        self._ha_last: dict[str, Any] = {}
        self._sinum_last: dict[str, Any] = {}
        self._recent: dict[str, tuple[Any, float]] = {}
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._unsub_state = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._lock = asyncio.Lock()

    async def async_start(self) -> None:
        """Load mapping and start event processing."""
        await self._async_load_mapping()
        if not self._mapping:
            await self._async_map_entities()
            await self._async_load_mapping()
        _LOGGER.debug("Sinum bridge mapping loaded: %s", len(self._mapping))
        if not self._mapping:
            _LOGGER.warning(
                "Sinum bridge is enabled but mapping is empty; "
                "waiting for the mapper"
            )
        self._subscribe_ha_states()
        self._tasks.append(
            self.hass.async_create_task(
                self._async_sinum_stream(), "sinum bridge event stream"
            )
        )
        self._tasks.append(
            self.hass.async_create_task(
                self._async_reconcile_loop(), "sinum bridge reconcile"
            )
        )
        self._tasks.append(
            self.hass.async_create_task(
                self._async_initial_sync(), "sinum bridge initial sync"
            )
        )
        _LOGGER.info(
            "Sinum bridge started for %s mapped entities (label=%s, room=%s)",
            len(self._mapping),
            self.options.label,
            self.options.room_id or "existing",
        )

    async def async_stop(self) -> None:
        """Stop bridge tasks."""
        self._stop.set()
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
            self._ws = None
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    @property
    def mapping_count(self) -> int:
        """Return the number of mapped HA entities."""
        return len(self._mapping)

    async def _async_load_mapping(self) -> None:
        data = await self._store.async_load()
        mapping: dict[str, Any] = {}
        if isinstance(data, dict):
            raw = data.get("mapping")
            if isinstance(raw, dict):
                mapping = raw
        if not mapping and self._mapping_file.exists():
            try:
                raw = await self._async_read_mapping_file()
                if isinstance(raw, dict):
                    mapping = raw
                    await self._store.async_save({"mapping": mapping})
                    _LOGGER.info(
                        "Imported bridge mapping from %s", self._mapping_file
                    )
            except (OSError, json.JSONDecodeError) as err:
                _LOGGER.warning("Cannot import bridge mapping: %s", err)
        self._set_mapping(mapping)
        try:
            self._mapping_mtime = (
                await self.hass.async_add_executor_job(
                    self._mapping_file.stat
                )
            ).st_mtime
        except OSError:
            self._mapping_mtime = 0.0

    def _set_mapping(self, mapping: dict[str, Any]) -> None:
        self._mapping = {
            str(entity_id): dict(entry)
            for entity_id, entry in mapping.items()
            if isinstance(entry, dict) and entry.get("id") is not None
        }
        self._by_id = {}
        for entity_id, entry in self._mapping.items():
            try:
                self._by_id[int(entry["id"])] = (entity_id, entry)
            except (KeyError, TypeError, ValueError):
                continue

    def _subscribe_ha_states(self) -> None:
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if not self._mapping:
            return
        self._unsub_state = async_track_state_change_event(
            self.hass,
            list(self._mapping),
            self._handle_ha_state_event,
        )

    @callback
    def _handle_ha_state_event(self, event: Event[Any]) -> None:
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if not entity_id or not isinstance(new_state, State):
            return
        if entity_id not in self._mapping or self._is_recent(entity_id):
            return
        self.hass.async_create_task(
            self._async_apply_ha_state(entity_id, new_state),
            f"sinum bridge HA {entity_id}",
        )

    def _is_recent(self, entity_id: str) -> bool:
        item = self._recent.get(entity_id)
        return bool(
            item and time.monotonic() - item[1] < RECENT_SECONDS
        )

    def _mark_recent(self, entity_id: str, value: Any) -> None:
        self._recent[entity_id] = (value, time.monotonic())

    async def _async_initial_sync(self) -> None:
        try:
            await self._async_initial_sync_inner()
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Sinum bridge initial sync failed: %s", err)

    async def _async_initial_sync_inner(self) -> None:
        for entity_id, entry in list(self._mapping.items()):
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown"):
                continue
            variant = entry.get("variant")
            if variant in ("relay", "light", "ac_module"):
                self._ha_last[entity_id] = self._desired(
                    variant, entry, state
                )
                continue
            try:
                await self._async_apply_ha_state(entity_id, state)
            except SinumHomeAssistantError as err:
                _LOGGER.debug(
                    "Sinum bridge initial sync failed for %s: %s",
                    entity_id,
                    err,
                )

    def _desired(
        self, variant: str, entry: dict[str, Any], state: State
    ) -> Any:
        if variant == "light":
            return _ha_light_values(state)
        if variant == "ac_module":
            return _ha_ac_values(state)
        return _value_for(entry, state)

    async def _async_apply_ha_state(
        self, entity_id: str, state: State
    ) -> None:
        entry = self._mapping.get(entity_id)
        if not entry or state.state in ("unavailable", "unknown"):
            return
        async with self._lock:
            entry = self._mapping.get(entity_id)
            if not entry or self._is_recent(entity_id):
                return
            variant = str(entry.get("variant"))
            device_id = int(entry["id"])
            if variant == "ac_module":
                desired = _ha_ac_values(state)
                if self._ha_last.get(entity_id) == desired:
                    return
                self._ha_last[entity_id] = desired
                try:
                    await self._async_apply_ac_module(device_id, desired)
                except SinumHomeAssistantError as err:
                    _LOGGER.warning(
                        "Sinum bridge AC update failed for %s: %s",
                        entity_id,
                        err,
                    )
                return
            if variant == "light":
                desired = _ha_light_values(state)
                old = self._ha_last.get(entity_id)
                if old == desired:
                    return
                self._ha_last[entity_id] = desired
                try:
                    await self._async_apply_light(
                        device_id, entry, desired, old
                    )
                except SinumHomeAssistantError as err:
                    _LOGGER.warning(
                        "Sinum bridge light update failed for %s: %s",
                        entity_id,
                        err,
                    )
                return
            value = _value_for(entry, state)
            if value is None or self._ha_last.get(entity_id) == value:
                return
            self._ha_last[entity_id] = value
            try:
                await self._async_apply_value(device_id, entry, value)
            except SinumHomeAssistantError as err:
                _LOGGER.warning(
                    "Sinum bridge update failed for %s: %s", entity_id, err
                )

    async def _async_apply_value(
        self, device_id: int, entry: dict[str, Any], value: Any
    ) -> None:
        variant = str(entry.get("variant"))
        payload = _mapping_payload(entry, value)
        if not payload and variant != "two_state_input_sensor":
            return
        await self._async_patch_virtual(device_id, payload)
        if variant == "relay":
            await self._async_set_relay_switch(
                device_id, "relay_switch", bool(value)
            )
        elif variant == "two_state_input_sensor":
            await self._async_set_sensor_text(
                device_id, "contact_state", _two_state_text(entry, value)
            )
        elif variant in ("temperature_sensor", "humidity_sensor"):
            await self._async_set_sensor_text(
                device_id, str(entry["field"]), _sensor_text(entry, value)
            )

    async def _async_apply_light(
        self,
        device_id: int,
        entry: dict[str, Any],
        desired: dict[str, Any],
        old: Any,
    ) -> None:
        element = str(entry.get("element", "light"))
        old_dict = old if isinstance(old, dict) else None
        if old_dict is None or old_dict.get("state") != desired["state"]:
            await self._async_element(
                device_id,
                element,
                "set_state",
                {"set_state": desired["state"]},
            )
        if not desired["state"]:
            return
        if desired["brightness"] is not None and (
            old_dict is None
            or old_dict.get("brightness") != desired["brightness"]
        ):
            await self._async_element(
                device_id,
                element,
                "set_brightness",
                {"set_brightness": max(1, min(100, desired["brightness"]))},
            )
        if (
            desired.get("color_mode") in ("color_temp", "temperature")
            and desired.get("temperature") is not None
            and (
                old_dict is None
                or old_dict.get("temperature") != desired["temperature"]
            )
        ):
            await self._async_element(
                device_id,
                element,
                "set_temperature",
                {"set_temperature": desired["temperature"]},
            )
        elif (
            desired.get("color_mode") in ("rgb", "xy")
            and desired.get("color") is not None
            and (
                old_dict is None
                or old_dict.get("color") != desired["color"]
            )
        ):
            await self._async_element(
                device_id,
                element,
                "set_color",
                {"set_color": desired["color"]},
            )

    async def _async_apply_ac_module(
        self, module_id: int, desired: dict[str, Any]
    ) -> None:
        module = await self._async_get_module(module_id)
        patch: dict[str, Any] = {}
        mode = _ac_mode_to_sinum(str(desired["hvac_mode"]))
        if module.get("mode") != mode:
            patch["mode"] = mode
        if desired.get("temperature") is not None:
            raw = int(round(float(desired["temperature"]) * 10))
            if module.get("target_temperature") != raw:
                patch["target_temperature"] = raw
        if patch:
            await self.client.async_patch(
                f"devices/custom-device-module/{module_id}", patch
            )

    async def _async_patch_virtual(
        self, device_id: int, payload: dict[str, Any]
    ) -> None:
        await self.client.async_patch(
            f"devices/virtual/{device_id}", {"variant_device": payload}
        )

    async def _async_element(
        self,
        device_id: int,
        element: str,
        command: str,
        payload: dict[str, Any],
    ) -> None:
        await self.client.async_post(
            f"devices/virtual/{device_id}/element/{element}/command/{command}",
            payload,
        )

    async def _async_get_virtual(self) -> dict[int, dict[str, Any]]:
        data = await self.client.async_get("devices/virtual")
        value = data.get("data", []) if isinstance(data, dict) else []
        result: dict[int, dict[str, Any]] = {}
        if not isinstance(value, list):
            return result
        for item in value:
            try:
                result[int(item["id"])] = item
            except (KeyError, TypeError, ValueError):
                continue
        return result

    async def _async_get_module(self, module_id: int) -> dict[str, Any]:
        data = await self.client.async_get(
            f"devices/custom-device-module/{module_id}"
        )
        value = data.get("data", {}) if isinstance(data, dict) else {}
        return value if isinstance(value, dict) else {}

    async def _async_set_sensor_text(
        self, device_id: int, element: str, text: str
    ) -> None:
        try:
            await self._async_element(
                device_id, element, "set_value", {"set_value": text}
            )
            return
        except SinumApiError as err:
            if "HTTP 404" not in str(err):
                raise
        layout, widget = _sensor_text_layout(element, text)
        await self.client.async_patch(
            f"devices/virtual/{device_id}",
            {"elements": [layout], "widget": widget},
        )
        await self._async_element(
            device_id, element, "set_value", {"set_value": text}
        )

    async def _async_set_relay_switch(
        self, device_id: int, element: str, value: bool
    ) -> None:
        try:
            await self._async_element(
                device_id, element, "set_value", {"set_value": bool(value)}
            )
            return
        except SinumApiError as err:
            if "HTTP 404" not in str(err):
                raise
        layout, widget = _relay_switch_layout(element, bool(value))
        await self.client.async_patch(
            f"devices/virtual/{device_id}",
            {"elements": [layout], "widget": widget},
        )
        await self._async_element(
            device_id, element, "set_value", {"set_value": bool(value)}
        )

    async def _async_reconcile_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._async_reconcile()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sinum bridge reconcile failed: %s", err)
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=RECONCILE_SECONDS
                )
            except TimeoutError:
                continue

    async def _async_reconcile(self) -> None:
        if time.monotonic() - self._last_map >= 60:
            self._last_map = time.monotonic()
            await self._async_map_entities()
            if not self._mapping:
                await self._async_load_mapping()
        await self._async_reload_mapping_if_needed()
        virtual = await self._async_get_virtual()
        for entity_id, entry in list(self._mapping.items()):
            device_id = int(entry["id"])
            device = virtual.get(device_id)
            if not device:
                continue
            variant = entry.get("variant")
            async with self._lock:
                if self._is_recent(entity_id):
                    continue
                if variant == "relay":
                    current = False
                    for element in device.get("elements") or []:
                        if element.get("name") == "relay_switch":
                            current = bool(element.get("value"))
                            break
                    else:
                        current = bool(
                            (device.get("variant_device") or {}).get("state")
                        )
                    if entity_id not in self._sinum_last:
                        self._sinum_last[entity_id] = current
                        continue
                    if self._sinum_last.get(entity_id) == current:
                        continue
                    self._sinum_last[entity_id] = current
                    await self._async_call_ha(
                        entity_id, "turn_on" if current else "turn_off"
                    )
                elif variant == "light":
                    current = _sinum_light_values(device)
                    if current is None:
                        continue
                    if entity_id not in self._sinum_last:
                        self._sinum_last[entity_id] = current
                        continue
                    if self._sinum_last.get(entity_id) == current:
                        continue
                    self._sinum_last[entity_id] = current
                    self._mark_recent(entity_id, current)
                    await self._async_apply_light_to_ha(entity_id, current)
        for entity_id, entry in list(self._mapping.items()):
            if entry.get("variant") != "ac_module":
                continue
            module = await self._async_get_module(int(entry["id"]))
            current = _sinum_ac_values(module)
            if entity_id not in self._sinum_last:
                self._sinum_last[entity_id] = current
                continue
            if self._sinum_last.get(entity_id) == current:
                continue
            self._sinum_last[entity_id] = current
            self._mark_recent(entity_id, current)
            await self._async_apply_ac_to_ha(entity_id, current)

    def _create_payload(
        self,
        variant: str,
        field: str,
        name: str,
        state: State,
        scale: Any,
        unit: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "custom_device",
            "variant": variant,
            "name": name,
            "integration_uid": "z2m-bridge",
            "integration_model": "Sinum Z2M bridge",
            "integration_version": "1.0",
        }
        if variant == "light":
            values = _ha_light_values(state)
            element_uuid = str(uuid.uuid4())
            row_uuid = str(uuid.uuid4())
            cell_uuid = str(uuid.uuid4())
            payload["elements"] = [
                {
                    "type": "color_picker",
                    "name": "light",
                    "uuid": element_uuid,
                    "enabled": True,
                    "visibility": "visible",
                    "state": values["state"],
                    "brightness": values["brightness"] or 0,
                    "color": values["color"] or "#ffffff",
                    "color_mode": "temperature"
                    if values.get("color_mode") in ("color_temp", "temperature")
                    else values.get("color_mode") or "temperature",
                    "temperature": values.get("temperature") or 3000,
                    "available_color_modes": ["temperature", "rgb"],
                    "on_state_change": "onLightState",
                    "on_brightness_change": "onLightBrightness",
                    "on_color_change": "onLightColor",
                }
            ]
            payload["widget"] = {
                "version": 2,
                "content": [
                    {
                        "id": row_uuid,
                        "type": "row",
                        "cells": [
                            {
                                "id": cell_uuid,
                                "type": "row",
                                "orientation": "row",
                                "vertical_alignment": "center",
                                "horizontal_alignment": "center",
                                "elements": [
                                    {
                                        "uuid": element_uuid,
                                        "variant": "color-picker-both",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            payload["lua"] = (
                'function CustomDevice:onInit(reason)\n'
                '  self:setValue("status", "online")\n'
                'end\n'
                'function CustomDevice:onLightState(newValue, element)\n'
                '  self:setValue("status", "online")\n'
                '  statistics:addPoint("state", newValue and 1 or 0, unit.bool_unit)\n'
                'end\n'
                'function CustomDevice:onLightBrightness(newValue, element)\n'
                '  statistics:addPoint("brightness", newValue, unit.percent)\n'
                'end\n'
            )
            return payload
        initial = self._initial_value(variant, field, state, scale, unit)
        payload["variant_device"] = initial
        if variant in ("temperature_sensor", "humidity_sensor"):
            text = self._format_sensor_text(
                initial.get(field), scale, unit
            )
            layout, widget = _sensor_text_layout(field, text)
            payload["elements"] = [layout]
            payload["widget"] = widget
            stats_unit = (
                "unit.celsius_x10"
                if variant == "temperature_sensor"
                else "unit.relative_humidity_x10"
            )
            payload["lua"] = self._sensor_stats_lua(field, stats_unit)
        elif variant == "relay":
            layout, widget = _relay_switch_layout(
                "relay_switch", bool(initial.get(field))
            )
            payload["elements"] = [layout]
            payload["widget"] = widget
        elif variant == "two_state_input_sensor":
            text = "Otwarte" if initial.get(field) else "Zamknięte"
            layout, widget = _sensor_text_layout("contact_state", text)
            payload["elements"] = [layout]
            payload["widget"] = widget
        return payload

    def _initial_value(
        self,
        variant: str,
        field: str,
        state: State,
        scale: Any,
        unit: Any,
    ) -> dict[str, Any]:
        raw = state.state
        if raw in (None, "unavailable", "unknown"):
            if variant in ("relay", "two_state_input_sensor"):
                return {"state": False}
            if variant == "analog_input":
                return {"unit": unit or "", "value": 0}
            return {field: 0}
        if variant in ("relay", "two_state_input_sensor"):
            return {field: raw in ("on", "open", "True", "true", True)}
        number = float(raw)
        if scale:
            return {field: int(round(number * float(scale)))}
        if variant == "battery":
            return {field: max(0, min(100, int(round(number))))}
        if variant == "analog_input":
            return {"unit": unit or "", "value": round(number, 3)}
        return {field: round(number, 3)}

    def _format_sensor_text(
        self, value: Any, scale: Any, unit: Any
    ) -> str:
        number = float(value or 0) / float(scale or 1)
        return f"{number:.1f} {str(unit or '').strip()}".strip()

    def _sensor_stats_lua(self, field: str, unit_name: str) -> str:
        return (
            'function CustomDevice:onInit(reason)\n'
            '  self:setValue("status", "online")\n'
            'end\n'
            'function CustomDevice:onEvent(event)\n'
            '  self:setValue("status", "online")\n'
            f'  if self:changedVariantDeviceValue("{field}") then\n'
            f'    local v = self:getVariantDeviceValue("{field}")\n'
            '    if v ~= nil then\n'
            f'      statistics:addPoint("{field}", v, {unit_name})\n'
            '    end\n'
            '  end\n'
            'end\n'
        )

    async def _async_read_mapping_file(self) -> Any:
        return await self.hass.async_add_executor_job(
            lambda: json.loads(self._mapping_file.read_text())
        )

    async def _async_write_mapping_file(
        self, mapping: dict[str, Any]
    ) -> None:
        def _write() -> None:
            self._mapping_file.parent.mkdir(
                parents=True, exist_ok=True
            )
            self._mapping_file.write_text(
                json.dumps(mapping, ensure_ascii=False, indent=1)
            )

        await self.hass.async_add_executor_job(_write)

    async def _async_map_entities(self) -> None:
        """Create missing Sinum devices for entities selected by label."""
        if not self.options.enabled:
            return
        labels = lr.async_get(self.hass)
        selected_labels = set()
        for name in (self.options.label, "sinum"):
            entry = labels.async_get_label_by_name(name)
            if entry is not None:
                selected_labels.add(entry.label_id)
        if not selected_labels:
            _LOGGER.debug(
                "Sinum bridge label %s (or legacy sinum) not found",
                self.options.label,
            )
            return
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        entities = list(entity_registry.entities.values())
        devices = {}
        for entity in entities:
            if not entity.device_id or entity.device_id in devices:
                continue
            device = device_registry.async_get(entity.device_id)
            if device is not None:
                devices[entity.device_id] = device
        mapped_devices = {
            device_id
            for device_id, device in devices.items()
            if selected_labels.intersection(device.labels or [])
        }
        if not mapped_devices:
            return
        mapping = dict(self._mapping)
        created = 0
        for entity in entities:
            if entity.device_id not in mapped_devices:
                continue
            eid = entity.entity_id
            if (
                eid in mapping
                or entity.disabled_by is not None
                or entity.hidden_by is not None
            ):
                continue
            state = self.hass.states.get(eid)
            if state is None:
                continue
            attrs = state.attributes
            domain = eid.split(".", 1)[0]
            device_class = attrs.get("device_class")
            unit = attrs.get("unit_of_measurement")
            if (
                domain in ("switch", "light")
                and entity.entity_category is not None
            ):
                continue
            if (
                domain == "binary_sensor"
                and entity.entity_category is not None
            ):
                continue
            variant = field = None
            scale = None
            if domain == "light":
                variant, field = "light", "state"
            elif domain == "switch":
                variant, field = "relay", "state"
            elif domain == "binary_sensor" and device_class in (
                "door",
                "window",
                "motion",
                "presence",
                "opening",
                "moisture",
                "smoke",
                "gas",
                "safety",
                "tamper",
            ):
                variant, field = "two_state_input_sensor", "state"
            elif domain == "sensor":
                if unit == "°C":
                    variant, field, scale = "temperature_sensor", "temperature", 10
                elif unit == "%" and device_class == "humidity":
                    variant, field, scale = "humidity_sensor", "humidity", 10
                elif unit == "W":
                    variant, field, scale = "energy_meter", "total_active_power", 1000
                elif unit == "kWh":
                    variant, field, scale = "energy_meter", "energy_sum_total", 1000
                elif unit == "%":
                    variant = "battery" if device_class == "battery" else "analog_input"
                    field = "soc" if device_class == "battery" else "value"
                elif unit in (
                    "lx",
                    "hPa",
                    "V",
                    "A",
                    "mV",
                    "s",
                    "minutes",
                ) or device_class in (
                    "illuminance",
                    "pressure",
                    "voltage",
                    "current",
                ):
                    variant, field = "analog_input", "value"
            if not variant:
                continue
            device = devices[entity.device_id]
            devname = str(
                device.name_by_user or device.name or "Z2M"
            ).strip()
            orig = str(
                entity.original_name or eid.split(".", 1)[1]
            ).strip()
            name = ("HA " + devname + " " + orig).strip()[:64].rstrip()
            payload = self._create_payload(
                variant, field, name, state, scale, unit
            )
            try:
                response = await self.client.async_post(
                    "devices/virtual", payload
                )
            except SinumHomeAssistantError as err:
                _LOGGER.warning(
                    "Cannot create Sinum bridge device %s: %s", eid, err
                )
                continue
            data = response.get("data", {}) if isinstance(response, dict) else {}
            try:
                device_id = int(data["id"])
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning(
                    "Sinum bridge create returned no id for %s", eid
                )
                continue
            if self.options.room_id > 0:
                try:
                    await self.client.async_post(
                        f"rooms/{self.options.room_id}/add-devices",
                        {"devices": [{"class": "virtual", "id": device_id}]},
                    )
                except SinumHomeAssistantError as err:
                    _LOGGER.warning(
                        "Cannot add Sinum bridge device %s to room %s: %s",
                        eid,
                        self.options.room_id,
                        err,
                    )
            mapping[eid] = {
                "id": device_id,
                "variant": variant,
                "field": field,
                "scale": scale,
                "unit": unit or "",
                "name": name,
            }
            if variant == "light":
                mapping[eid]["element"] = "light"
            await self._store.async_save({"mapping": mapping})
            await self._async_write_mapping_file(mapping)
            self._mapping = mapping
            self._set_mapping(mapping)
            created += 1
        if created:
            self._subscribe_ha_states()
            _LOGGER.info(
                "Sinum bridge mapped %s new entities (total %s)",
                created,
                len(self._mapping),
            )

    async def _async_reload_mapping_if_needed(self) -> None:
        try:
            mtime = (
                await self.hass.async_add_executor_job(
                    self._mapping_file.stat
                )
            ).st_mtime
        except OSError:
            return
        if mtime == self._mapping_mtime:
            return
        self._mapping_mtime = mtime
        try:
            mapping = await self._async_read_mapping_file()
        except (OSError, json.JSONDecodeError) as err:
            _LOGGER.warning("Cannot reload bridge mapping: %s", err)
            return
        if not isinstance(mapping, dict):
            return
        async with self._lock:
            self._set_mapping(mapping)
            self._subscribe_ha_states()
        await self._store.async_save({"mapping": mapping})
        _LOGGER.info(
            "Sinum bridge mapping reloaded (%s entities)", len(self._mapping)
        )

    async def _async_call_ha(
        self, entity_id: str, service: str, data: dict[str, Any] | None = None
    ) -> None:
        domain = entity_id.split(".", 1)[0]
        await self.hass.services.async_call(
            domain,
            service,
            {**(data or {}), "entity_id": entity_id},
            blocking=False,
        )

    async def _async_apply_light_to_ha(
        self, entity_id: str, current: dict[str, Any]
    ) -> None:
        data: dict[str, Any] = {}
        if current["state"]:
            if current.get("brightness") is not None:
                data["brightness_pct"] = current["brightness"]
            if current.get("color_mode") in (
                "color_temp",
                "temperature",
            ) and current.get("temperature"):
                data["color_temp_kelvin"] = current["temperature"]
            elif current.get("color_mode") == "rgb" and current.get("color"):
                data["rgb_color"] = _hex_to_rgb(current["color"])
            service = "turn_on"
        else:
            service = "turn_off"
        await self._async_call_ha(entity_id, service, data)

    async def _async_apply_ac_to_ha(
        self, entity_id: str, current: dict[str, Any]
    ) -> None:
        if not current["state"]:
            await self._async_call_ha(entity_id, "turn_off")
            return
        if current.get("hvac_mode"):
            await self._async_call_ha(
                entity_id,
                "set_hvac_mode",
                {"hvac_mode": current["hvac_mode"]},
            )
        if current.get("temperature") is not None:
            await self._async_call_ha(
                entity_id,
                "set_temperature",
                {"temperature": float(current["temperature"])},
            )

    async def _async_sinum_stream(self) -> None:
        while not self._stop.is_set():
            try:
                await self._async_sinum_stream_once()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sinum bridge event stream error: %s", err)
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=STREAM_RECONNECT
                )
            except TimeoutError:
                continue

    async def _async_sinum_stream_once(self) -> None:
        token = await self.client.async_ensure_token()
        server = f"{randint(0, 999):03d}"
        session_id = "".join(choice(ascii_lowercase + digits) for _ in range(8))
        url = (
            "wss://backend.prd.sinum24.com/proxy/gs-guide-websocket/"
            f"{server}/{session_id}/websocket?"
            f"deviceId={self.client.device_id}&access_token={token}"
        )
        async with async_get_clientsession(self.hass).ws_connect(
            url,
            headers={"Origin": "https://sinum.tech"},
            timeout=30,
            heartbeat=None,
        ) as ws:
            self._ws = ws
            await ws.send_str(
                json.dumps(
                    [
                        "CONNECT\naccept-version:1.2,1.1,1.0\n"
                        "heart-beat:10000,5000\n\n\u0000"
                    ]
                )
            )
            await ws.send_str(
                json.dumps(
                    [
                        "SUBSCRIBE\nid:sub-0\ndestination:/topic/"
                        + self.client.device_id
                        + "\n\n\u0000"
                    ]
                )
            )
            _LOGGER.info("Sinum bridge event stream connected")
            last_heartbeat = time.monotonic()
            while not self._stop.is_set():
                if time.monotonic() - last_heartbeat > 8:
                    await ws.send_str(json.dumps(["\n"]))
                    last_heartbeat = time.monotonic()
                try:
                    message = await asyncio.wait_for(
                        ws.receive(), timeout=1
                    )
                except TimeoutError:
                    continue
                if message.type in (
                    aiohttp.WSMsgType.TEXT,
                    aiohttp.WSMsgType.BINARY,
                ):
                    raw = message.data
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", "replace")
                    self._parse_stomp(str(raw))
                elif message.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break
        self._ws = None

    def _parse_stomp(self, raw: str) -> None:
        if not raw.startswith("a"):
            return
        try:
            frames = json.loads(raw[1:])
        except json.JSONDecodeError:
            return
        if not isinstance(frames, list):
            return
        for frame in frames:
            if not isinstance(frame, str) or not frame.startswith("MESSAGE"):
                continue
            try:
                _, body = frame.split("\n\n", 1)
                events = json.loads(body.rstrip("\x00"))
            except (ValueError, json.JSONDecodeError):
                continue
            if not isinstance(events, list):
                continue
            for event in events:
                if not isinstance(event, dict):
                    continue
                self.hass.async_create_task(
                    self._async_handle_sinum_event(event),
                    "sinum bridge event",
                )

    async def _async_handle_sinum_event(
        self, event: dict[str, Any]
    ) -> None:
        data = event.get("data") or {}
        if not isinstance(data, dict):
            return
        event_type = data.get("type")
        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            return
        try:
            device_id = (
                int(payload["device_id"])
                if "device_id" in payload
                else int(payload["id"])
            )
        except (KeyError, TypeError, ValueError):
            return
        if event_type == "device_state_changed":
            entry = next(
                (
                    item
                    for item in self._mapping.values()
                    if item.get("class") == "custom_device_module"
                    and int(item.get("id", 0)) == device_id
                ),
                None,
            )
            if entry is not None:
                entity_id = next(
                    (
                        eid
                        for eid, item in self._mapping.items()
                        if item is entry
                    ),
                    None,
                )
                if entity_id is not None:
                    await self._async_handle_ac_event(
                        device_id, entity_id
                    )
            return
        if event_type != "custom_device_element_state_changed":
            return
        found = self._by_id.get(device_id)
        if not found or self._is_recent(found[0]):
            return
        entity_id, entry = found
        variant = entry.get("variant")
        _LOGGER.debug("Sinum bridge event %s: %s", entity_id, variant)
        if variant == "relay" and payload.get("name") == "relay_switch":
            current = bool(payload.get("value"))
            if self._sinum_last.get(entity_id) == current:
                return
            self._mark_recent(entity_id, current)
            self._sinum_last[entity_id] = current
            await self._async_call_ha(
                entity_id, "turn_on" if current else "turn_off"
            )
            try:
                await self._async_patch_virtual(device_id, {"state": current})
            except SinumHomeAssistantError as err:
                _LOGGER.debug(
                    "Sinum bridge relay state sync failed for %s: %s",
                    entity_id,
                    err,
                )
        elif variant == "light" and payload.get("name") == "light":
            try:
                device = await self._async_get_virtual()
            except SinumHomeAssistantError as err:
                _LOGGER.warning(
                    "Sinum bridge light event fetch failed: %s", err
                )
                return
            current = _sinum_light_values(device.get(device_id, {}))
            if current is None or self._sinum_last.get(entity_id) == current:
                return
            self._mark_recent(entity_id, current)
            self._sinum_last[entity_id] = current
            await self._async_apply_light_to_ha(entity_id, current)
        elif variant == "ac_module" and payload.get("name") in (
            "power",
            "target",
            "mode",
            "room_temp",
        ):
            await self._async_handle_ac_event(device_id, entity_id)

    async def _async_handle_ac_event(
        self, module_id: int, entity_id: str
    ) -> None:
        if self._is_recent(entity_id):
            return
        try:
            module = await self._async_get_module(module_id)
        except SinumHomeAssistantError as err:
            _LOGGER.warning("Sinum bridge AC event fetch failed: %s", err)
            return
        current = _sinum_ac_values(module)
        if self._sinum_last.get(entity_id) == current:
            return
        self._mark_recent(entity_id, current)
        self._sinum_last[entity_id] = current
        await self._async_apply_ac_to_ha(entity_id, current)
