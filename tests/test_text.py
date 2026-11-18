"""Tests for bridge text helpers."""

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

spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.text", PACKAGE_DIR / "text.py"
)
text = importlib.util.module_from_spec(spec)
sys.modules[f"{PACKAGE}.text"] = text
spec.loader.exec_module(text)

fix_mojibake = text.fix_mojibake
bridge_name = text.bridge_name


def test_fix_mojibake_unit():
    assert fix_mojibake("Ã\x82Â°C") == "°C"


def test_fix_mojibake_polish_text():
    assert fix_mojibake("ZamkniÄ\x99ta") == "Zamknięta"
    assert fix_mojibake("HA Ã\x82Â· Ã\x85Â\x81ukasz") == "HA · Łukasz"


def test_fix_mojibake_keeps_valid_text():
    assert fix_mojibake("Garaż") == "Garaż"
    assert fix_mojibake("20.6 °C") == "20.6 °C"


def test_bridge_name():
    assert bridge_name("Salon PIR Temperatura") == "HA · Salon PIR Temperatura"
    assert bridge_name("HA Ã\x82Â· GaraÅ¼ Agrestowa") == "HA · Garaż Agrestowa"
    assert len(bridge_name("x" * 100)) == 64
