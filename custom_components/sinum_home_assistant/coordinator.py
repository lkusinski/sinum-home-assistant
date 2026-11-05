"""Data update coordinator for Sinum Home Assistant."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SinumAuthError,
    SinumHomeAssistantClient,
    SinumHomeAssistantError,
    SinumNotSupportedError,
)
from .const import (
    CONF_ENABLE_SYSTEM_MODULES,
    CONF_ENABLE_WEATHER,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .data import SinumHomeAssistantData, build_data

_LOGGER = logging.getLogger(__name__)

INFO_CACHE_SECONDS = 300


class SinumHomeAssistantCoordinator(DataUpdateCoordinator[SinumHomeAssistantData]):
    """Poll the Sinum cloud and normalize the response."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: SinumHomeAssistantClient
    ) -> None:
        self.client = client
        self.options = dict(entry.options)
        self.enable_weather = bool(
            self.options.get(CONF_ENABLE_WEATHER, True)
        )
        self.enable_system_modules = bool(
            self.options.get(CONF_ENABLE_SYSTEM_MODULES, True)
        )
        self._info: dict[str, Any] = {}
        self._info_at = 0.0
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=int(
                    self.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                )
            ),
        )

    async def _async_info(self) -> dict[str, Any]:
        if self._info and time.monotonic() - self._info_at < INFO_CACHE_SECONDS:
            return self._info
        info = await self.client.async_get_info()
        if info:
            self._info = info
            self._info_at = time.monotonic()
        return self._info

    async def _async_update_data(self) -> SinumHomeAssistantData:
        try:
            info, rooms, parents, devices = await asyncio.gather(
                self._async_info(),
                self.client.async_get_rooms(),
                self.client.async_get_parent_devices(),
                self.client.async_get_devices(),
            )
        except SinumAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SinumHomeAssistantError as err:
            raise UpdateFailed(str(err)) from err
        except (TimeoutError, OSError) as err:
            raise UpdateFailed(str(err)) from err

        weather: dict[str, Any] | None = None
        if self.enable_weather:
            try:
                weather = await self.client.async_get_weather()
            except SinumNotSupportedError:
                weather = None
            except SinumAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except SinumHomeAssistantError as err:
                _LOGGER.debug("Sinum weather unavailable: %s", err)

        return build_data(
            info=info,
            rooms=rooms,
            parents=parents,
            devices=devices,
            weather=weather,
        )
