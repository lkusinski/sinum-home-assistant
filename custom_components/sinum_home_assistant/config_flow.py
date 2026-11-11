"""Config flow for Sinum Home Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    SinumApiError,
    SinumAuthError,
    SinumHomeAssistantClient,
    SinumHomeAssistantError,
)
from .const import (
    CONF_BRIDGE_ENABLED,
    CONF_BRIDGE_LABEL,
    CONF_BRIDGE_ROOM_ID,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_ENABLE_SCHEDULES,
    CONF_ENABLE_SYSTEM_MODULES,
    CONF_ENABLE_WEATHER,
    CONF_HUB_NAME,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_BRIDGE_LABEL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

DEVICE_ID_EXAMPLE = "0x1234abcd0000000000000000000000"


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL)
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_DEVICE_ID): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
    )


def _reauth_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )


class SinumHomeAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Sinum Home Assistant config flow."""

    VERSION = 1

    async def _validate(
        self, email: str, password: str, device_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        client = SinumHomeAssistantClient(
            async_get_clientsession(self.hass),
            email=email,
            password=password,
            device_id=device_id,
        )
        try:
            await client.async_login()
            info = await client.async_get_info()
        except SinumAuthError:
            return None, "invalid_auth"
        except SinumApiError as err:
            text = str(err)
            if "401" in text or "403" in text:
                return None, "invalid_device_id"
            return None, "cannot_connect"
        except SinumHomeAssistantError:
            return None, "cannot_connect"

        uid = str(info.get("uid") or "")
        if uid and uid.lower() != device_id.lower():
            return None, "invalid_device_id"
        if not client.refresh_token:
            return None, "cannot_connect"
        info["_refresh_token"] = client.refresh_token
        return info, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = str(user_input[CONF_EMAIL]).strip()
            device_id = str(user_input[CONF_DEVICE_ID]).strip().lower()
            info, error = await self._validate(
                email, str(user_input[CONF_PASSWORD]), device_id
            )
            if error is not None:
                errors["base"] = error
            elif info is not None:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                hub_name = str(info.get("name") or "").strip()
                title = (
                    f"Sinum Home Assistant - {hub_name}"
                    if hub_name and hub_name.lower() != "sinum"
                    else "Sinum Home Assistant"
                )
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_EMAIL: email,
                        CONF_DEVICE_ID: device_id,
                        CONF_REFRESH_TOKEN: info["_refresh_token"],
                        CONF_HUB_NAME: str(info.get("name") or ""),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
            description_placeholders={"device_id_example": DEVICE_ID_EXAMPLE},
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            info, error = await self._validate(
                entry.data[CONF_EMAIL],
                str(user_input[CONF_PASSWORD]),
                entry.data[CONF_DEVICE_ID],
            )
            if error is not None:
                errors["base"] = error
            elif info is not None:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_REFRESH_TOKEN: info["_refresh_token"],
                        CONF_HUB_NAME: str(info.get("name") or ""),
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: Any) -> OptionsFlow:
        return SinumHomeAssistantOptionsFlow()


class SinumHomeAssistantOptionsFlow(OptionsFlow):
    """Options for polling and optional platforms."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL
                        ),
                    ),
                    vol.Optional(
                        CONF_ENABLE_WEATHER,
                        default=options.get(CONF_ENABLE_WEATHER, True),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_SYSTEM_MODULES,
                        default=options.get(
                            CONF_ENABLE_SYSTEM_MODULES, True
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_SCHEDULES,
                        default=options.get(CONF_ENABLE_SCHEDULES, True),
                    ): bool,
                    vol.Optional(
                        CONF_BRIDGE_ENABLED,
                        default=options.get(CONF_BRIDGE_ENABLED, True),
                    ): bool,
                    vol.Optional(
                        CONF_BRIDGE_LABEL,
                        default=options.get(
                            CONF_BRIDGE_LABEL, DEFAULT_BRIDGE_LABEL
                        ),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                    vol.Optional(
                        CONF_BRIDGE_ROOM_ID,
                        default=options.get(CONF_BRIDGE_ROOM_ID, 0),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                }
            ),
        )
