#!/usr/bin/env python3
"""Push Sinum custom-device element changes to Home Assistant immediately.

The periodic `z2m_to_sinum.py` worker remains the reconciliation loop. This
worker subscribes to the Sinum STOMP topic and reacts to user changes (relay
switch, light state/brightness/color) without waiting for the polling cycle.
"""

from __future__ import annotations

import json
import os
import random
import string
import threading
import time
from pathlib import Path
from typing import Any, Callable

import requests
import websocket

import z2m_to_sinum as z

STOP = threading.Event()
STATE_LOCK = threading.Lock()
SINUM = z.SinumClient()
SINUM_HA = z.SinumClient()
HA_WS_URL = os.environ.get("HA_WS_URL", "ws://192.168.1.204/api/websocket")
RECENT: dict[str, tuple[Any, float]] = {}
SUPPRESS: dict[str, float] = {}


def _load_mapping() -> tuple[dict[str, dict[str, Any]], dict[int, tuple[str, dict[str, Any]]]]:
    mapping: dict[str, dict[str, Any]] = json.loads(z.MAPPING_FILE.read_text())
    by_id: dict[int, tuple[str, dict[str, Any]]] = {}
    for entity_id, entry in mapping.items():
        by_id[int(entry["id"])] = (entity_id, entry)
    return mapping, by_id


MAPPING, BY_ID = _load_mapping()
LAST_REFRESH = [0.0]


def _update_state(entity_id: str, value: Any, sinum_value: Any) -> None:
    with STATE_LOCK:
        ha_state = z.read_json(z.STATE_FILE)
        sinum_state = z.read_json(z.SINUM_STATE_FILE)
        ha_state[entity_id] = value
        sinum_state[entity_id] = sinum_value
        z.write_json(z.STATE_FILE, ha_state)
        z.write_json(z.SINUM_STATE_FILE, sinum_state)


def _ha_light_call(entity_id: str, current: dict[str, Any]) -> None:
    data: dict[str, Any] = {"entity_id": entity_id}
    if current["state"]:
        if current.get("brightness") is not None:
            data["brightness_pct"] = current["brightness"]
        if current.get("color_mode") in ("color_temp", "temperature") and current.get(
            "temperature"
        ):
            data["color_temp_kelvin"] = current["temperature"]
        elif current.get("color_mode") == "rgb" and current.get("color"):
            data["rgb_color"] = z._hex_to_rgb(current["color"])
        service = "turn_on"
    else:
        service = "turn_off"
    z._ha_call("light", service, data)


def _refresh_integration() -> None:
    if time.time() - LAST_REFRESH[0] < 0.5:
        return
    LAST_REFRESH[0] = time.time()
    try:
        z._ha_call("sinum_home_assistant", "refresh", {})
    except Exception as err:  # noqa: BLE001
        print(f"ERROR refresh integration: {err}", flush=True)


def handle_event(event: dict[str, Any]) -> None:
    data = event.get("data") or {}
    if not isinstance(data, dict):
        return
    event_type = data.get("type")
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        return
    try:
        device_id = int(payload["device_id"]) if "device_id" in payload else int(payload.get("id"))
    except (KeyError, TypeError, ValueError):
        return
    if event_type == "device_state_changed":
        if payload.get("class") == "virtual" and device_id not in BY_ID:
            _refresh_integration()
        return
    if event_type != "custom_device_element_state_changed":
        return
    found = BY_ID.get(device_id)
    if not found:
        _refresh_integration()
        return
    entity_id, entry = found
    if _is_suppressed(entity_id):
        return
    variant = entry.get("variant")
    if variant == "ac":
        if payload.get("name") not in ("power", "target", "mode", "room_temp"):
            return
        try:
            device = SINUM.get_device(device_id)
        except Exception as err:  # noqa: BLE001
            print(f"ERROR event AC {entity_id}: {err}", flush=True)
            return
        current = z.sinum_ac_values(device)
        previous = z.read_json(z.SINUM_STATE_FILE).get(entity_id)
        if previous == current:
            return
        _update_one(entity_id, current, current)
        try:
            z._ha_call(
                "input_boolean",
                "turn_on" if current["state"] else "turn_off",
                {"entity_id": "input_boolean.sinum_lab_ac_power"},
            )
            z._ha_call(
                "input_select",
                "select_option",
                {
                    "entity_id": "input_select.sinum_lab_ac_mode",
                    "option": current["hvac_mode"],
                },
            )
            if current["temperature"] is not None:
                z._ha_call(
                    "input_number",
                    "set_value",
                    {
                        "entity_id": "input_number.sinum_lab_ac_target",
                        "value": float(current["temperature"]),
                    },
                )
            if current["current_temperature"] is not None:
                z._ha_call(
                    "input_number",
                    "set_value",
                    {
                        "entity_id": "input_number.sinum_lab_ac_room_temp",
                        "value": float(current["current_temperature"]),
                    },
                )
        except Exception as err:  # noqa: BLE001
            print(f"ERROR event AC→HA {entity_id}: {err}", flush=True)
            return
        print(f"EVENT SINUM→HA AC {entity_id}: {current}", flush=True)
        return
    if variant == "relay" and payload.get("name") == "relay_switch":
        current = bool(payload.get("value"))
        previous = z.read_json(z.SINUM_STATE_FILE).get(entity_id)
        if previous is current:
            return
        domain = entity_id.split(".", 1)[0]
        action = "turn_on" if current else "turn_off"
        _mark_recent(entity_id, current)
        try:
            z._ha_call(domain, action, {"entity_id": entity_id})
            SINUM.patch(device_id, {"state": current})
        except Exception as err:  # noqa: BLE001
            print(f"ERROR event {entity_id} {action}: {err}", flush=True)
            return
        _update_state(entity_id, current, current)
        print(f"EVENT SINUM→HA {entity_id}: {action}", flush=True)
        return
    if variant == "light" and payload.get("name") == "light":
        try:
            device = SINUM.get_device(device_id)
        except Exception as err:  # noqa: BLE001
            print(f"ERROR event light {entity_id}: {err}", flush=True)
            return
        current = z.sinum_light_values(device)
        if current is None:
            return
        if z.read_json(z.SINUM_STATE_FILE).get(entity_id) == current:
            return
        _mark_recent(entity_id, current)
        try:
            _ha_light_call(entity_id, current)
        except Exception as err:  # noqa: BLE001
            print(f"ERROR event light {entity_id}: {err}", flush=True)
            return
        _update_state(entity_id, current, current)
        print(f"EVENT SINUM→HA {entity_id}: {current}", flush=True)


def _update_one(entity_id: str, value: Any, sinum_value: Any) -> None:
    with STATE_LOCK:
        ha_state = z.read_json(z.STATE_FILE)
        sinum_state = z.read_json(z.SINUM_STATE_FILE)
        ha_state[entity_id] = value
        sinum_state[entity_id] = sinum_value
        z.write_json(z.STATE_FILE, ha_state)
        z.write_json(z.SINUM_STATE_FILE, sinum_state)


def _mark_recent(entity_id: str, value: Any) -> None:
    with STATE_LOCK:
        RECENT[entity_id] = (value, time.time())


def _is_recent(entity_id: str, value: Any) -> bool:
    with STATE_LOCK:
        entry = RECENT.get(entity_id)
    return bool(entry and entry[0] == value and time.time() - entry[1] < 15)


def _suppress(entity_id: str) -> None:
    with STATE_LOCK:
        SUPPRESS[entity_id] = time.time()


def _is_suppressed(entity_id: str) -> bool:
    with STATE_LOCK:
        stamp = SUPPRESS.get(entity_id, 0.0)
    return time.time() - stamp < 3.0


def apply_ha_state(entity_id: str, new_state: dict[str, Any] | None) -> None:
    if not new_state:
        return
    entry = MAPPING.get(entity_id)
    if not entry:
        return
    if _is_suppressed(entity_id):
        return
    variant = entry.get("variant")
    if variant == "ac":
        desired = z.ha_ac_values(new_state)
        old = z.read_json(z.STATE_FILE).get(entity_id)
        if old == desired or _is_recent(entity_id, desired):
            _update_one(entity_id, desired, desired)
            return
        _update_one(entity_id, desired, desired)
        try:
            z.apply_ha_ac(SINUM_HA, entry, new_state, old)
        except Exception as err:  # noqa: BLE001
            print(f"ERROR HA→Sinum AC {entity_id}: {err}", flush=True)
            return
        print(f"EVENT HA→SINUM AC {entity_id}: {desired}", flush=True)
        return
    if variant == "light":
        desired = z.ha_light_values(new_state)
        old = z.read_json(z.STATE_FILE).get(entity_id)
        if not isinstance(old, dict):
            old = None
        if old == desired or _is_recent(entity_id, desired):
            _update_one(entity_id, desired, desired)
            return
        _update_one(entity_id, desired, desired)
        try:
            z._sync_light_from_ha(SINUM_HA, entry, desired, old)
        except Exception as err:  # noqa: BLE001
            print(f"ERROR HA→Sinum light {entity_id}: {err}", flush=True)
            return
        print(f"EVENT HA→SINUM {entity_id}: {desired}", flush=True)
        return
    value = z.value_for(entry, new_state)
    if value is None:
        return
    old = z.read_json(z.STATE_FILE).get(entity_id)
    if old == value or _is_recent(entity_id, value):
        _update_one(entity_id, value, value)
        return
    payload = z.payload_for(entry, value)
    if payload is None:
        return
    _suppress(entity_id)
    try:
        device_id = int(entry["id"])
        SINUM_HA.patch(device_id, payload)
        if variant == "relay":
            SINUM_HA.set_relay_switch(device_id, "relay_switch", bool(value))
        elif variant == "two_state_input_sensor":
            SINUM_HA.set_sensor_text(
                device_id, "contact_state", z.two_state_text(entry, value)
            )
        elif variant in ("temperature_sensor", "humidity_sensor"):
            SINUM_HA.set_sensor_text(
                device_id, entry["field"], z.sensor_text(entry, value)
            )
    except Exception as err:  # noqa: BLE001
        print(f"ERROR HA→Sinum {entity_id}: {err}", flush=True)
        return
    _update_one(entity_id, value, value)
    print(f"EVENT HA→SINUM {entity_id}: {value}", flush=True)


class HAStream:
    def run(self) -> None:
        while not STOP.is_set():
            try:
                ws = websocket.create_connection(HA_WS_URL, timeout=60)
                ws.recv()
                ws.send(json.dumps({"type": "auth", "access_token": z.HA_TOKEN}))
                ws.recv()
                ws.send(
                    json.dumps(
                        {
                            "id": 1,
                            "type": "subscribe_events",
                            "event_type": "state_changed",
                        }
                    )
                )
                print("HA event stream connected", flush=True)
                while not STOP.is_set():
                    try:
                        message = json.loads(ws.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                    if message.get("type") != "event":
                        continue
                    event = message.get("event") or {}
                    data = event.get("data") or {}
                    apply_ha_state(data.get("entity_id"), data.get("new_state"))
            except Exception as err:  # noqa: BLE001
                print(f"HA event stream error: {err}", flush=True)
                time.sleep(5)


class SinumStream:
    def __init__(self, on_event: Callable[[dict[str, Any]], None]) -> None:
        self.on_event = on_event
        self.session = requests.Session()
        self.ws: websocket.WebSocket | None = None

    def _token(self) -> str:
        response = self.session.post(
            z.SINUM_BASE + "/authentication/oauth/token",
            data={
                "grant_type": "password",
                "username": z.SINUM_EMAIL,
                "password": z.SINUM_PASSWORD,
                "device_info": "Home Assistant / Sinum events",
                "os_info": "Linux",
            },
            headers={
                "Authorization": "Basic " + z.SINUM_BASIC,
                "Accept": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _connect(self) -> None:
        token = self._token()
        server = f"{random.randint(0, 999):03d}"
        session = "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(8)
        )
        url = (
            f"wss://backend.prd.sinum24.com/proxy/gs-guide-websocket/"
            f"{server}/{session}/websocket?deviceId={z.SINUM_DEVICE}&access_token={token}"
        )
        self.ws = websocket.create_connection(
            url, header=["Origin: https://sinum.tech"], timeout=20
        )
        self.ws.settimeout(5)
        self.ws.recv()
        self.ws.send(
            json.dumps(
                ["CONNECT\naccept-version:1.2,1.1,1.0\nheart-beat:10000,5000\n\n\u0000"]
            )
        )
        self.ws.recv()
        self.ws.send(
            json.dumps(
                [
                    "SUBSCRIBE\nid:sub-0\ndestination:/topic/"
                    + z.SINUM_DEVICE
                    + "\n\n\u0000"
                ]
            )
        )
        print("Sinum event stream connected", flush=True)

    def run(self) -> None:
        while not STOP.is_set():
            try:
                self._connect()
                last_send = time.time()
                while not STOP.is_set():
                    if time.time() - last_send > 9:
                        self.ws.send(json.dumps(["\n"]))  # type: ignore[union-attr]
                        last_send = time.time()
                    try:
                        raw = self.ws.recv()  # type: ignore[union-attr]
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", "replace")
                    if raw.startswith("a"):
                        try:
                            frames = json.loads(raw[1:])
                        except json.JSONDecodeError:
                            continue
                        for frame in frames:
                            if not isinstance(frame, str) or not frame.startswith(
                                "MESSAGE"
                            ):
                                continue
                            try:
                                _, body = frame.split("\n\n", 1)
                                events = json.loads(body.rstrip("\x00"))
                            except (ValueError, json.JSONDecodeError):
                                continue
                            for event in events:
                                try:
                                    self.on_event(event)
                                except Exception as err:  # noqa: BLE001
                                    print(f"ERROR event handler: {err}", flush=True)
                    elif raw.startswith("c"):
                        break
            except Exception as err:  # noqa: BLE001
                print(f"Sinum event stream error: {err}", flush=True)
                time.sleep(5)
            finally:
                try:
                    if self.ws:
                        self.ws.close()
                except Exception:  # noqa: BLE001
                    pass


def main() -> None:
    if not z.SINUM_EMAIL or not z.SINUM_PASSWORD or not z.SINUM_DEVICE:
        raise SystemExit("Set SINUM_EMAIL, SINUM_PASSWORD and SINUM_DEVICE_ID")
    threading.Thread(target=HAStream().run, daemon=True).start()
    stream = SinumStream(handle_event)
    try:
        stream.run()
    except KeyboardInterrupt:
        STOP.set()


if __name__ == "__main__":
    main()
