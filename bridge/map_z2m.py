#!/usr/bin/env python3
"""Create Sinum virtual endpoints for B7 devices labelled `sinum`.

Read-only source: B7 Home Assistant / MQTT-discovered Zigbee2MQTT entities.
Target: Sinum virtual custom devices in the room set by SINUM_ROOM_ID.
The worker (`z2m_to_sinum.py`) handles ongoing value changes.
"""

from __future__ import annotations

import collections
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests
import websocket

HA_URL = os.environ.get("B7_URL", "http://192.168.1.204")
HA_TOKEN = os.environ.get("B7_TOKEN", "")
SINUM_EMAIL = os.environ.get("SINUM_EMAIL", "")
SINUM_PASSWORD = os.environ.get("SINUM_PASSWORD", "")
SINUM_DEVICE = os.environ.get("SINUM_DEVICE_ID", "")
SINUM_ROOM = int(os.environ.get("SINUM_ROOM_ID", "11"))
SINUM_BRIDGE_LABEL = os.environ.get("SINUM_BRIDGE_LABEL", "sinumbridge")
LABEL_FALLBACKS = {SINUM_BRIDGE_LABEL, "sinum"}
SINUM_BASE = "https://backend.prd.sinum24.com"
MAPPING_FILE = Path(
    os.environ.get("MAPPING_FILE", Path(__file__).with_name("mapping.json"))
)


def ha_registry() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ws = websocket.create_connection(
        HA_URL.replace("http://", "ws://") + "/api/websocket", timeout=60
    )
    ws.recv()
    ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
    ws.recv()
    ids = [1]

    def cmd(typ: str) -> list[dict[str, Any]]:
        i = ids[0]
        ids[0] += 1
        ws.send(json.dumps({"id": i, "type": typ}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == i:
                return msg["result"]

    devices = cmd("config/device_registry/list")
    entities = cmd("config/entity_registry/list")
    ws.close()
    return devices, entities


class Sinum:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.token = ""
        self.expires = 0.0
        self.headers = {
            "X-Device-ID": SINUM_DEVICE,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def ensure(self) -> None:
        if self.token and time.time() < self.expires:
            return
        response = self.session.post(
            SINUM_BASE + "/authentication/oauth/token",
            data={
                "grant_type": "password",
                "username": SINUM_EMAIL,
                "password": SINUM_PASSWORD,
                "device_info": "Home Assistant / Sinum Z2M mapper",
                "os_info": "Linux",
            },
            headers={
                "Authorization": "Basic ZWhvbWU6dG9wX3NlY3JldA==",
                "Accept": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        self.expires = time.time() + int(data.get("expires_in", 599)) - 45

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        self.ensure()
        return self.session.request(
            method,
            SINUM_BASE + "/proxy/" + path,
            headers={**self.headers, "Authorization": "Bearer " + self.token},
            timeout=30,
            **kwargs,
        )


def main() -> None:
    if not HA_TOKEN or not SINUM_EMAIL or not SINUM_PASSWORD or not SINUM_DEVICE:
        raise SystemExit(
            "Set B7_TOKEN, SINUM_EMAIL, SINUM_PASSWORD and SINUM_DEVICE_ID"
        )

    devices, entities = ha_registry()
    states = {
        item["entity_id"]: item
        for item in requests.get(
            HA_URL + "/api/states",
            headers={"Authorization": "Bearer " + HA_TOKEN},
            timeout=30,
        ).json()
    }
    bridge_cfg: dict[str, Any] = {}
    for state in states.values():
        attrs = state.get("attributes") or {}
        if attrs.get("sinum_bridge_config"):
            bridge_cfg = attrs
            break
    if not bridge_cfg.get("enabled", True):
        print("Bridge disabled in integration options; nothing to map")
        return
    bridge_label = str(
        bridge_cfg.get("label") or SINUM_BRIDGE_LABEL
    )
    room_id = int(bridge_cfg.get("room_id") or SINUM_ROOM)
    label_fallbacks = {bridge_label, "sinum"}

    # label id for bridge selection
    ws = websocket.create_connection(
        HA_URL.replace("http://", "ws://") + "/api/websocket", timeout=60
    )
    ws.recv()
    ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
    ws.recv()
    ws.send(json.dumps({"id": 999, "type": "config/label_registry/list"}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 999:
            labels = msg["result"]
            break
    ws.close()
    label_ids = {
        x["label_id"] for x in labels if x["name"] in label_fallbacks
    }
    if not label_ids:
        raise SystemExit(
            f"B7 label '{bridge_label}' (or legacy 'sinum') does not exist"
        )
    zdev = {
        d["id"]: d
        for d in devices
        if label_ids.intersection(d.get("labels") or [])
    }

    mapping: dict[str, dict[str, Any]] = {}
    if MAPPING_FILE.exists():
        mapping = json.loads(MAPPING_FILE.read_text())
    sinum = Sinum()
    created = skipped = 0
    for entity in entities:
        if entity.get("device_id") not in zdev:
            continue
        eid = entity["entity_id"]
        state = states.get(eid, {})
        attrs = state.get("attributes", {})
        domain = eid.split(".", 1)[0]
        device_class = attrs.get("device_class")
        unit = attrs.get("unit_of_measurement")
        category = entity.get("entity_category")
        if domain in ("switch", "light") and category is not None:
            continue
        if domain == "binary_sensor" and category is not None:
            continue
        variant = field = None
        scale = None
        if domain in ("switch", "light"):
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
            ) or device_class in ("illuminance", "pressure", "voltage", "current"):
                variant, field = "analog_input", "value"
        if not variant:
            continue
        if eid in mapping:
            skipped += 1
            continue
        device = zdev[entity["device_id"]]
        devname = str(device.get("name_by_user") or device.get("name") or "Z2M").strip()
        orig = str(entity.get("original_name") or eid.split(".", 1)[1]).strip()
        name = ("HA " + devname + " " + orig).strip()
        if len(name) > 64:
            name = name[:64].rstrip()
        initial = _initial_value(variant, field, state, scale, unit)
        payload = {
            "type": "custom_device",
            "variant": variant,
            "name": name,
            "variant_device": initial,
        }
        if variant in ("temperature_sensor", "humidity_sensor"):
            text = _format_sensor_text(initial.get(field), scale, unit)
            layout, widget = sensor_text_layout(field, text)
            payload["elements"] = [layout]
            payload["widget"] = widget
            stats_unit = (
                "unit.celsius_x10"
                if variant == "temperature_sensor"
                else "unit.relative_humidity_x10"
            )
            payload["lua"] = _sensor_stats_lua(field, stats_unit)
        elif variant == "relay":
            layout, widget = relay_switch_layout("relay_switch", bool(initial.get(field)))
            payload["elements"] = [layout]
            payload["widget"] = widget
        elif variant == "two_state_input_sensor":
            text = "Otwarte" if initial.get(field) else "Zamknięte"
            layout, widget = sensor_text_layout("contact_state", text)
            payload["elements"] = [layout]
            payload["widget"] = widget
        response = sinum.request("POST", "devices/virtual", json=payload)
        if not response.ok:
            print("CREATE FAIL", eid, response.status_code, response.text[:160])
            continue
        data = response.json()["data"]
        sinum.request(
            "POST",
            f"rooms/{room_id}/add-devices",
            json={"devices": [{"class": "virtual", "id": data["id"]}]},
        )
        mapping[eid] = {
            "id": data["id"],
            "variant": variant,
            "field": field,
            "scale": scale,
            "unit": unit or "",
            "name": name,
        }
        MAPPING_FILE.write_text(json.dumps(mapping, ensure_ascii=False, indent=1))
        created += 1
        time.sleep(0.03)
    print("created", created, "existing", skipped, "total", len(mapping))
    print(collections.Counter(v["variant"] for v in mapping.values()))


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


def _format_sensor_text(value: Any, scale: Any, unit: Any) -> str:
    number = float(value or 0) / float(scale or 1)
    return f"{number:.1f} {str(unit or '').strip()}".strip()


def _sensor_stats_lua(field: str, unit_name: str) -> str:
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


def _initial_value(
    variant: str, field: str, state: dict[str, Any], scale: Any, unit: Any
) -> dict[str, Any]:
    raw = state.get("state")
    if raw in (None, "unavailable", "unknown"):
        return (
            {
                "state": False,
            }
            if variant in ("relay", "two_state_input_sensor")
            else (
                {"unit": unit or "", "value": 0}
                if variant == "analog_input"
                else {field: 0}
            )
        )
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


if __name__ == "__main__":
    main()
