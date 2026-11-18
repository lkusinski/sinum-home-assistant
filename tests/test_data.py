"""Tests for the normalized data model."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.sinum_home_assistant"
PACKAGE_DIR = ROOT / "custom_components" / "sinum_home_assistant"

components = types.ModuleType("custom_components")
components.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", components)
package = types.ModuleType(PACKAGE)
package.__path__ = [str(PACKAGE_DIR)]
sys.modules.setdefault(PACKAGE, package)


def _load(name):
    full = f"{PACKAGE}.{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, PACKAGE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


_load("const")
data_module = _load("data")
build_data = data_module.build_data


def test_bridge_owned_modules_are_filtered():
    modules = [
        {"id": 10, "custom_device_id": 1, "type": "relay", "room_id": None},
        {"id": 11, "custom_device_id": 2, "type": "dimmer", "room_id": None},
    ]
    devices = {
        "virtual": [
            {"id": 1, "integration_uid": "z2m-bridge", "room_id": 13},
            {"id": 2, "integration_uid": "", "room_id": 12},
        ],
        "custom_device_module": modules,
    }

    data = build_data(
        info={},
        rooms=[{"id": 12, "name": "LAB Active"}],
        parents={},
        devices=devices,
        custom_modules=modules,
        weather=None,
    )

    assert set(data.custom_modules) == {11}
    assert set(data.device_groups["custom_device_module"]) == {11}
    assert data.custom_modules[11]["room_id"] == 12
    assert data.custom_modules[11]["parent_custom_device_id"] == 2
    assert 1 not in data.virtual


def test_visible_non_bridge_modules_keep_their_room():
    devices = {
        "virtual": [
            {"id": 3, "integration_uid": "", "room_id": 13},
        ]
    }
    modules = [
        {
            "id": 12,
            "custom_device_id": 3,
            "type": "temperature_sensor",
            "room_id": 13,
            "temperature": 215,
        },
    ]

    data = build_data(
        info={},
        rooms=[{"id": 13, "name": "LAB Virtual"}],
        parents={},
        devices=devices,
        custom_modules=modules,
        weather=None,
    )

    assert data.custom_modules[12]["room_id"] == 13
    assert data.custom_modules[12]["temperature"] == 215
