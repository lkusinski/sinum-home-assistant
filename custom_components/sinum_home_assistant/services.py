"""Services for Sinum Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, TEMP_SCALE

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_ID = "device_id"
ATTR_TEMPERATURE = "temperature"

SERVICE_SET_VIRTUAL_TEMPERATURE = "set_virtual_temperature"
SERVICE_REFRESH = "refresh"

SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.positive_int,
        vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register the virtual-temperature service once."""

    if all(
        hass.services.has_service(DOMAIN, service)
        for service in (SERVICE_SET_VIRTUAL_TEMPERATURE, SERVICE_REFRESH)
    ):
        return

    async def _set_virtual_temperature(call: ServiceCall) -> None:
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.runtime_data is not None
        ]
        if not entries:
            raise HomeAssistantError("Sinum Home Assistant is not loaded")
        coordinator = entries[0].runtime_data
        device_id = int(call.data[ATTR_DEVICE_ID])
        temperature = float(call.data[ATTR_TEMPERATURE])
        raw = round(temperature / TEMP_SCALE)
        await coordinator.client.async_patch_device(
            "virtual",
            device_id,
            {"variant_device": {"temperature": raw}},
        )
        await coordinator.async_request_refresh()

    async def _refresh(call: ServiceCall) -> None:
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.runtime_data is not None
        ]
        for entry in entries:
            try:
                await entry.runtime_data.async_request_refresh()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sinum refresh failed: %s", err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VIRTUAL_TEMPERATURE,
        _set_virtual_temperature,
        schema=SCHEMA,
    )
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services when the last entry is unloaded."""

    if hass.config_entries.async_entries(DOMAIN):
        return
    for service in (SERVICE_SET_VIRTUAL_TEMPERATURE, SERVICE_REFRESH):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
