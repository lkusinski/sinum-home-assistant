#!/usr/bin/env python3
"""Read-only Zigbee2MQTT values mirrored from Home Assistant to Sinum.

The script polls Home Assistant entities already discovered from MQTT and
updates pre-created Sinum virtual custom devices. It never modifies the
production Home Assistant configuration. Relay/light write-back is optional.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests

HA_URL = os.environ.get("B7_URL", "http://192.168.1.204")
HA_TOKEN = os.environ.get("B7_TOKEN", "")
SINUM_EMAIL = os.environ.get("SINUM_EMAIL", "")
SINUM_PASSWORD = os.environ.get("SINUM_PASSWORD", "")
SINUM_DEVICE = os.environ.get("SINUM_DEVICE_ID", "")
SINUM_BASE = "https://backend.prd.sinum24.com"
SINUM_BASIC = "ZWhvbWU6dG9wX3NlY3JldA=="
MAPPING_FILE = Path(
    os.environ.get("MAPPING_FILE", Path(__file__).with_name("mapping.json"))
)
STATE_FILE = Path(os.environ.get("STATE_FILE", "/tmp/opencode/z2m_sinum_state.json"))
SINUM_STATE_FILE = Path(
    os.environ.get("SINUM_STATE_FILE", "/tmp/opencode/z2m_sinum_sinum_state.json")
)
WRITE_BACK = os.environ.get("WRITE_BACK", "1") not in ("0", "false", "False")

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: Any) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(path)


class SinumClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.token = ""
        self.expires = 0.0
        self.headers = {
            "X-Device-ID": SINUM_DEVICE,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def ensure_token(self) -> None:
        if self.token and time.time() < self.expires:
            return
        response = self.session.post(
            SINUM_BASE + "/authentication/oauth/token",
            data={
                "grant_type": "password",
                "username": SINUM_EMAIL,
                "password": SINUM_PASSWORD,
                "device_info": "Home Assistant / Sinum Z2M bridge",
                "os_info": "Linux",
            },
            headers={
                "Authorization": "Basic " + SINUM_BASIC,
                "Accept": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        self.expires = time.time() + int(data.get("expires_in", 599)) - 45

    def virtual_devices(self) -> dict[int, dict[str, Any]]:
        self.ensure_token()
        response = self.session.get(
            SINUM_BASE + "/proxy/devices/virtual",
            headers={**self.headers, "Authorization": "Bearer " + self.token},
            timeout=30,
        )
        response.raise_for_status()
        return {int(item["id"]): item for item in response.json().get("data", [])}

    def patch_device(self, device_id: int, payload: dict[str, Any]) -> None:
        self.ensure_token()
        response = self.session.patch(
            f"{SINUM_BASE}/proxy/devices/virtual/{device_id}",
            headers={**self.headers, "Authorization": "Bearer " + self.token},
            json=payload,
            timeout=30,
        )
        if response.status_code not in (200, 204, 304):
            raise RuntimeError(
                f"Sinum PATCH {device_id} HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

    def patch(self, device_id: int, payload: dict[str, Any]) -> None:
        self.patch_device(device_id, {"variant_device": payload})

    def set_sensor_text(
        self, device_id: int, element: str, text: str
    ) -> None:
        try:
            self.element(device_id, element, "set_value", {"set_value": text})
            return
        except RuntimeError as err:
            if "HTTP 404" not in str(err):
                raise
        layout, widget = sensor_text_layout(element, text)
        self.patch_device(device_id, {"elements": [layout], "widget": widget})
        self.element(device_id, element, "set_value", {"set_value": text})

    def get_device(self, device_id: int) -> dict[str, Any]:
        self.ensure_token()
        response = self.session.get(
            f"{SINUM_BASE}/proxy/devices/virtual/{device_id}",
            headers={**self.headers, "Authorization": "Bearer " + self.token},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["data"]

    def set_relay_switch(self, device_id: int, element: str, value: bool) -> None:
        try:
            self.element(device_id, element, "set_value", {"set_value": bool(value)})
            return
        except RuntimeError as err:
            if "HTTP 404" not in str(err):
                raise
        layout, widget = relay_switch_layout(element, bool(value))
        self.patch_device(device_id, {"elements": [layout], "widget": widget})
        self.element(device_id, element, "set_value", {"set_value": bool(value)})

    def element(
        self, device_id: int, element: str, command: str, payload: dict[str, Any]
    ) -> None:
        self.ensure_token()
        response = self.session.post(
            f"{SINUM_BASE}/proxy/devices/virtual/{device_id}/element/"
            f"{element}/command/{command}",
            headers={**self.headers, "Authorization": "Bearer " + self.token},
            json=payload,
            timeout=30,
        )
        if response.status_code not in (200, 204, 304):
            raise RuntimeError(
                f"Sinum {command} {device_id} HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )


def ha_states() -> dict[str, dict[str, Any]]:
    response = requests.get(
        HA_URL + "/api/states",
        headers={"Authorization": "Bearer " + HA_TOKEN},
        timeout=30,
    )
    response.raise_for_status()
    return {item["entity_id"]: item for item in response.json()}


def _hex_to_rgb(value: str) -> list[int]:
    value = value.lstrip("#")
    return [int(value[index : index + 2], 16) for index in (0, 2, 4)]


def sensor_text_layout(element: str, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
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


def relay_switch_layout(element: str, value: bool) -> tuple[dict[str, Any], dict[str, Any]]:
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


def sensor_text(entry: dict[str, Any], value: Any) -> str:
    scale = float(entry.get("scale") or 1)
    number = float(value) / scale
    unit = str(entry.get("unit") or "").strip()
    return f"{number:.1f} {unit}".strip()


def ha_light_values(state: dict[str, Any]) -> dict[str, Any]:
    attrs = state.get("attributes") or {}
    brightness = attrs.get("brightness")
    rgb = attrs.get("rgb_color")
    color = None
    if isinstance(rgb, list) and len(rgb) == 3:
        color = "#{:02x}{:02x}{:02x}".format(*[int(value) for value in rgb])
    return {
        "state": state.get("state") == "on",
        "brightness": round(brightness * 100 / 255)
        if isinstance(brightness, (int, float))
        else None,
        "color_mode": attrs.get("color_mode"),
        "temperature": attrs.get("color_temp_kelvin"),
        "color": color,
    }


def sinum_light_values(device: dict[str, Any]) -> dict[str, Any] | None:
    for element in device.get("elements") or []:
        if element.get("name") == "light":
            return {
                "state": bool(element.get("state")),
                "brightness": element.get("brightness"),
                "color_mode": element.get("color_mode"),
                "temperature": element.get("temperature"),
                "color": element.get("color"),
            }
    return None


def ha_ac_values(state: dict[str, Any]) -> dict[str, Any]:
    attrs = state.get("attributes") or {}
    mode = str(state.get("state") or "off")
    return {
        "state": mode != "off",
        "hvac_mode": mode,
        "temperature": attrs.get("temperature"),
        "current_temperature": attrs.get("current_temperature"),
    }


def _ac_mode_to_sinum(mode: str) -> str:
    return "fan" if mode == "fan_only" else mode


def _ac_mode_to_ha(mode: str) -> str:
    return "fan_only" if mode == "fan" else mode


def sinum_ac_values(device: dict[str, Any]) -> dict[str, Any]:
    elements = {e.get("name"): e for e in device.get("elements") or []}
    mode = str(elements.get("mode", {}).get("value") or "off")
    room = elements.get("room_temp", {}).get("value")
    current: float | None = None
    if room is not None:
        try:
            current = float(str(room).replace("°C", "").strip())
        except ValueError:
            current = None
    power = bool(elements.get("power", {}).get("value"))
    return {
        "state": power,
        "hvac_mode": _ac_mode_to_ha(mode) if power else "off",
        "temperature": elements.get("target", {}).get("value"),
        "current_temperature": current,
    }


def apply_ha_ac(
    sinum: "SinumClient", entry: dict[str, Any], state: dict[str, Any], old: Any
) -> dict[str, Any]:
    desired = ha_ac_values(state)
    device = sinum.get_device(int(entry["id"]))
    elements = {e.get("name"): e for e in device.get("elements") or []}
    power = elements.get("power", {}).get("value")
    target = elements.get("target", {}).get("value")
    mode = elements.get("mode", {}).get("value")
    room = elements.get("room_temp", {}).get("value")
    if power != desired["state"]:
        sinum.element(
            int(entry["id"]), "power", "set_value", {"set_value": desired["state"]}
        )
    if desired["temperature"] is not None and target != desired["temperature"]:
        sinum.element(
            int(entry["id"]),
            "target",
            "set_value",
            {"set_value": float(desired["temperature"])},
        )
    desired_mode = _ac_mode_to_sinum(str(desired["hvac_mode"]))
    if desired_mode in ("auto", "cool", "heat", "fan", "dry") and mode != desired_mode:
        sinum.element(
            int(entry["id"]), "mode", "set_value", {"set_value": desired_mode}
        )
    current = desired["current_temperature"]
    if current is not None:
        text = f"{float(current):.1f} °C"
        if room != text:
            sinum.element(
                int(entry["id"]), "room_temp", "set_value", {"set_value": text}
            )
    return desired


def sinum_relay_values(device: dict[str, Any]) -> bool:
    for element in device.get("elements") or []:
        if element.get("name") == "relay_switch":
            return bool(element.get("value"))
    return bool((device.get("variant_device") or {}).get("state"))


def value_for(entry: dict[str, Any], state: dict[str, Any]) -> Any | None:
    raw = state.get("state")
    if raw in (None, "unavailable", "unknown"):
        return None
    variant = entry["variant"]
    if variant in ("relay", "two_state_input_sensor"):
        return raw in ("on", "open", "True", "true", True)
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if entry.get("scale"):
        return int(round(number * float(entry["scale"])))
    if variant == "battery":
        return max(0, min(100, int(round(number))))
    return round(number, 3)


def payload_for(entry: dict[str, Any], value: Any) -> dict[str, Any] | None:
    variant = entry["variant"]
    field = entry["field"]
    if variant == "analog_input":
        return {"unit": entry.get("unit", ""), "value": value}
    return {field: value}


def _ha_call(domain: str, service: str, data: dict[str, Any]) -> None:
    response = requests.post(
        HA_URL + f"/api/services/{domain}/{service}",
        headers={"Authorization": "Bearer " + HA_TOKEN},
        json=data,
        timeout=30,
    )
    response.raise_for_status()


def _sync_light_from_ha(
    sinum: SinumClient, entry: dict[str, Any], desired: dict[str, Any], old: Any
) -> None:
    element = entry.get("element", "light")
    device_id = int(entry["id"])
    if old is None or old.get("state") != desired["state"]:
        sinum.element(device_id, element, "set_state", {"set_state": desired["state"]})
    if not desired["state"]:
        return
    if desired["brightness"] is not None and (
        old is None or old.get("brightness") != desired["brightness"]
    ):
        sinum.element(
            device_id,
            element,
            "set_brightness",
            {"set_brightness": max(1, min(100, desired["brightness"]))},
        )
    if (
        desired.get("color_mode") == "color_temp"
        and desired.get("temperature") is not None
        and (old is None or old.get("temperature") != desired["temperature"])
    ):
        sinum.element(
            device_id,
            element,
            "set_temperature",
            {"set_temperature": desired["temperature"]},
        )
    elif (
        desired.get("color_mode") in ("rgb", "xy")
        and desired.get("color") is not None
        and (old is None or old.get("color") != desired["color"])
    ):
        sinum.element(
            device_id,
            element,
            "set_color",
            {"set_color": desired["color"]},
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if not HA_TOKEN or not SINUM_EMAIL or not SINUM_PASSWORD or not SINUM_DEVICE:
        raise SystemExit(
            "Set B7_TOKEN, SINUM_EMAIL, SINUM_PASSWORD and SINUM_DEVICE_ID"
        )

    mapping: dict[str, dict[str, Any]] = json.loads(MAPPING_FILE.read_text())
    sinum = SinumClient()
    while True:
        previous: dict[str, Any] = read_json(STATE_FILE)
        sinum_previous: dict[str, Any] = read_json(SINUM_STATE_FILE)
        skip_ha: set[str] = set()
        if WRITE_BACK:
            try:
                virtual = sinum.virtual_devices()
            except Exception as err:  # noqa: BLE001
                print(f"ERROR reading Sinum virtual devices: {err}", flush=True)
                virtual = {}
            for entity_id, entry in mapping.items():
                device = virtual.get(int(entry["id"]))
                if not device:
                    continue
                if entry["variant"] == "relay":
                    current = sinum_relay_values(device)
                    if entity_id not in sinum_previous:
                        sinum_previous[entity_id] = current
                        continue
                    if current == sinum_previous[entity_id]:
                        continue
                    domain = entity_id.split(".", 1)[0]
                    if domain not in ("switch", "light", "input_boolean"):
                        sinum_previous[entity_id] = current
                        continue
                    action = "turn_on" if current else "turn_off"
                    try:
                        _ha_call(domain, action, {"entity_id": entity_id})
                        print(f"SINUM→HA {entity_id}: {action}", flush=True)
                    except Exception as err:  # noqa: BLE001
                        print(f"ERROR {entity_id} {action}: {err}", flush=True)
                    try:
                        sinum.patch(int(entry["id"]), {"state": current})
                    except Exception as err:  # noqa: BLE001
                        print(f"ERROR {entity_id} relay state: {err}", flush=True)
                    sinum_previous[entity_id] = current
                    skip_ha.add(entity_id)
                elif entry["variant"] == "light":
                    current = sinum_light_values(device)
                    if current is None:
                        continue
                    if not isinstance(sinum_previous.get(entity_id), dict):
                        sinum_previous[entity_id] = current
                        continue
                    if current == sinum_previous[entity_id]:
                        continue
                    data: dict[str, Any] = {"entity_id": entity_id}
                    if current["state"]:
                        if current.get("brightness") is not None:
                            data["brightness_pct"] = current["brightness"]
                        if current.get("color_mode") == "color_temp" and current.get(
                            "temperature"
                        ):
                            data["color_temp_kelvin"] = current["temperature"]
                        elif current.get("color_mode") == "rgb" and current.get(
                            "color"
                        ):
                            data["rgb_color"] = _hex_to_rgb(current["color"])
                        service = "turn_on"
                    else:
                        service = "turn_off"
                    try:
                        _ha_call("light", service, data)
                        print(f"SINUM→HA {entity_id}: {service}", flush=True)
                    except Exception as err:  # noqa: BLE001
                        print(f"ERROR {entity_id} {service}: {err}", flush=True)
                    sinum_previous[entity_id] = current
                    skip_ha.add(entity_id)
            write_json(SINUM_STATE_FILE, sinum_previous)

        states = ha_states()
        updates = 0
        for entity_id, entry in mapping.items():
            if entity_id in skip_ha:
                continue
            state = states.get(entity_id)
            if state is None or state.get("state") in ("unavailable", "unknown"):
                continue
            if entry["variant"] == "ac":
                desired = ha_ac_values(state)
                old_value = previous.get(entity_id)
                if old_value == desired:
                    continue
                try:
                    apply_ha_ac(sinum, entry, state, old_value)
                except Exception as err:  # noqa: BLE001
                    print(f"ERROR {entity_id}: {err}", flush=True)
                    continue
                previous[entity_id] = desired
                sinum_previous[entity_id] = desired
                updates += 1
                print(f"PATCH {entry['name']}: {desired}", flush=True)
                continue
            if entry["variant"] == "light":
                desired = ha_light_values(state)
                old_value = previous.get(entity_id)
                if not isinstance(old_value, dict):
                    old_value = None
                if old_value == desired:
                    continue
                try:
                    _sync_light_from_ha(sinum, entry, desired, old_value)
                except Exception as err:  # noqa: BLE001
                    print(f"ERROR {entity_id}: {err}", flush=True)
                    continue
                previous[entity_id] = desired
                sinum_previous[entity_id] = desired
                updates += 1
                print(f"PATCH {entry['name']}: {desired}", flush=True)
                continue
            value = value_for(entry, state)
            if value is None:
                continue
            if not args.once and previous.get(entity_id) == value:
                continue
            payload = payload_for(entry, value)
            if payload is None:
                continue
            try:
                device_id = int(entry["id"])
                sinum.patch(device_id, payload)
                if entry["variant"] in ("temperature_sensor", "humidity_sensor"):
                    sinum.set_sensor_text(
                        device_id, entry["field"], sensor_text(entry, value)
                    )
                elif entry["variant"] == "relay":
                    sinum.set_relay_switch(device_id, "relay_switch", bool(value))
                elif entry["variant"] == "two_state_input_sensor":
                    sinum.set_sensor_text(
                        device_id,
                        "contact_state",
                        "Otwarte" if value else "Zamknięte",
                    )
            except Exception as err:  # noqa: BLE001
                print(f"ERROR {entity_id}: {err}", flush=True)
                continue
            previous[entity_id] = value
            if entry["variant"] == "relay":
                sinum_previous[entity_id] = bool(value)
            updates += 1
            print(f"PATCH {entry['name']}: {value}", flush=True)
        write_json(STATE_FILE, previous)
        if WRITE_BACK:
            write_json(SINUM_STATE_FILE, sinum_previous)
        print(f"cycle done: {updates} updates", flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
