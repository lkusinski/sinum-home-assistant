#!/usr/bin/env python3
"""Read-only Zigbee2MQTT values mirrored from Home Assistant to Sinum.

The script polls Home Assistant entities (already discovered via MQTT) and
updates pre-created Sinum virtual custom devices. It never writes to the
production Home Assistant.
"""

from __future__ import annotations

import argparse
import json
import os
import time
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
MAPPING_FILE = Path(os.environ.get("MAPPING_FILE", Path(__file__).with_name("mapping.json")))
STATE_FILE = Path(os.environ.get("STATE_FILE", "/tmp/opencode/z2m_sinum_state.json"))


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
            headers={"Authorization": "Basic " + SINUM_BASIC, "Accept": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        self.expires = time.time() + int(data.get("expires_in", 599)) - 45

    def patch(self, device_id: int, payload: dict[str, Any]) -> None:
        self.ensure_token()
        response = self.session.patch(
            f"{SINUM_BASE}/proxy/devices/virtual/{device_id}",
            headers={**self.headers, "Authorization": "Bearer " + self.token},
            json={"variant_device": payload},
            timeout=30,
        )
        if response.status_code not in (200, 204, 304):
            raise RuntimeError(f"Sinum PATCH {device_id} HTTP {response.status_code}: {response.text[:200]}")


def ha_states() -> dict[str, dict[str, Any]]:
    response = requests.get(
        HA_URL + "/api/states",
        headers={"Authorization": "Bearer " + HA_TOKEN},
        timeout=30,
    )
    response.raise_for_status()
    return {item["entity_id"]: item for item in response.json()}


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if not HA_TOKEN or not SINUM_EMAIL or not SINUM_PASSWORD or not SINUM_DEVICE:
        raise SystemExit("Set B7_TOKEN, SINUM_EMAIL, SINUM_PASSWORD and SINUM_DEVICE_ID")

    mapping: dict[str, dict[str, Any]] = json.loads(MAPPING_FILE.read_text())
    try:
        previous: dict[str, Any] = json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        previous = {}

    sinum = SinumClient()
    while True:
        states = ha_states()
        updates = 0
        for entity_id, entry in mapping.items():
            state = states.get(entity_id)
            if state is None:
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
                sinum.patch(int(entry["id"]), payload)
            except Exception as err:  # noqa: BLE001
                print(f"ERROR {entity_id}: {err}", flush=True)
                continue
            previous[entity_id] = value
            updates += 1
            print(f"PATCH {entry['name']}: {value}", flush=True)
        STATE_FILE.write_text(json.dumps(previous, ensure_ascii=False, indent=1))
        print(f"cycle done: {updates} updates", flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
