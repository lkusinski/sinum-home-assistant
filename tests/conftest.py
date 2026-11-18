"""Minimal Home Assistant stubs for pure API unit tests.

The cloud client only needs ``homeassistant.const.Platform`` from the HA
package. Stubbing it keeps these tests fast and independent from a full Home
Assistant installation.
"""

from __future__ import annotations

import sys
import types

if "homeassistant" not in sys.modules:
    homeassistant = types.ModuleType("homeassistant")
    const = types.ModuleType("homeassistant.const")

    class Platform:
        BINARY_SENSOR = "binary_sensor"
        CLIMATE = "climate"
        LIGHT = "light"
        SENSOR = "sensor"
        SWITCH = "switch"
        UPDATE = "update"
        WEATHER = "weather"

    const.Platform = Platform
    homeassistant.const = const
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.const"] = const
