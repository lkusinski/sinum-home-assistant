"""Small async client for the Sinum cloud proxy API."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .const import API_BASE, APP_BASIC, OAUTH_URL, TOKEN_SAFETY


class SinumHomeAssistantError(Exception):
    """Base error for the Sinum cloud client."""


class SinumAuthError(SinumHomeAssistantError):
    """Authentication or token refresh failed."""


class SinumConnectionError(SinumHomeAssistantError):
    """The cloud could not be reached."""


class SinumApiError(SinumHomeAssistantError):
    """The cloud returned an unexpected response."""


class SinumNotSupportedError(SinumHomeAssistantError):
    """The cloud does not expose this endpoint."""


class SinumHomeAssistantClient:
    """Cloud API client with password and refresh-token support."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        email: str,
        device_id: str,
        password: str | None = None,
        refresh_token: str | None = None,
        token_update: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._email = email
        self._device_id = device_id
        self._password = password
        self._refresh_token = refresh_token
        self._token_update = token_update
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    async def _post_token(self, fields: dict[str, str]) -> None:
        try:
            async with self._session.post(
                OAUTH_URL,
                data=fields,
                headers={
                    "Authorization": "Basic " + APP_BASIC,
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                body = await response.text()
                if response.status != 200:
                    raise SinumAuthError(
                        f"Sinum OAuth failed with HTTP {response.status}"
                    )
                data = json.loads(body)
        except SinumAuthError:
            raise
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError) as err:
            raise SinumConnectionError(f"Sinum OAuth request failed: {err}") from err

        access_token = data.get("access_token")
        if not access_token:
            raise SinumAuthError("Sinum OAuth response has no access token")

        self._access_token = str(access_token)
        self._expires_at = (
            time.monotonic() + int(data.get("expires_in", 599)) - TOKEN_SAFETY
        )

        refresh_token = data.get("refresh_token")
        if refresh_token and refresh_token != self._refresh_token:
            self._refresh_token = str(refresh_token)
            if self._token_update is not None:
                await self._token_update(self._refresh_token)

    async def async_login(self) -> None:
        if not self._password:
            raise SinumAuthError("No password available")
        await self._post_token(
            {
                "grant_type": "password",
                "username": self._email,
                "password": self._password,
                "device_info": "Home Assistant / Sinum Home Assistant",
                "os_info": "Linux",
            }
        )

    async def _async_refresh(self) -> None:
        if not self._refresh_token:
            raise SinumAuthError("No refresh token available")
        await self._post_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }
        )

    async def async_ensure_token(self, force: bool = False) -> str:
        async with self._lock:
            if (
                not force
                and self._access_token
                and time.monotonic() < self._expires_at
            ):
                return self._access_token

            if self._refresh_token:
                try:
                    await self._async_refresh()
                    return self._access_token  # type: ignore[return-value]
                except SinumAuthError:
                    if not self._password:
                        raise
                except SinumConnectionError:
                    raise

            await self.async_login()
            return self._access_token  # type: ignore[return-value]

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> Any:
        token = await self.async_ensure_token()
        url = f"{API_BASE}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Device-ID": self._device_id,
            "Accept": "application/json",
        }
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=45),
            ) as response:
                if response.status == 401 and retry:
                    await self.async_ensure_token(force=True)
                    return await self._async_request(
                        method, path, payload=payload, retry=False
                    )
                if response.status in (404, 501):
                    raise SinumNotSupportedError(path)
                if response.status == 304:
                    return None
                if response.status >= 400:
                    body = (await response.text())[:200]
                    raise SinumApiError(
                        f"{method} {path} failed with HTTP {response.status}: {body}"
                    )
                if response.status == 204:
                    return None
                body = await response.text()
                if not body:
                    return None
                return json.loads(body)
        except SinumHomeAssistantError:
            raise
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError) as err:
            raise SinumConnectionError(f"{method} {path} failed: {err}") from err

    async def async_get(self, path: str) -> Any:
        return await self._async_request("GET", path)

    async def async_patch(self, path: str, payload: dict[str, Any]) -> Any:
        return await self._async_request("PATCH", path, payload=payload)

    async def async_get_info(self) -> dict[str, Any]:
        data = await self.async_get("info")
        return data.get("data", {}) if isinstance(data, dict) else {}

    async def async_get_rooms(self) -> list[dict[str, Any]]:
        data = await self.async_get("rooms")
        value = data.get("data", []) if isinstance(data, dict) else []
        return value if isinstance(value, list) else []

    async def async_get_devices(self) -> dict[str, list[dict[str, Any]]]:
        data = await self.async_get("devices")
        value = data.get("data", {}) if isinstance(data, dict) else {}
        return value if isinstance(value, dict) else {}

    async def async_get_parent_devices(self) -> dict[str, list[dict[str, Any]]]:
        data = await self.async_get("parent-devices")
        value = data.get("data", {}) if isinstance(data, dict) else {}
        return value if isinstance(value, dict) else {}

    async def async_get_weather(self) -> dict[str, Any]:
        data = await self.async_get("weather")
        return data.get("data", {}) if isinstance(data, dict) else {}

    async def async_get_schedules(self) -> list[dict[str, Any]]:
        data = await self.async_get("schedules")
        value = data.get("data", []) if isinstance(data, dict) else []
        return value if isinstance(value, list) else []

    async def async_patch_device(
        self, device_class: str, device_id: int, payload: dict[str, Any]
    ) -> Any:
        return await self.async_patch(
            f"devices/{device_class}/{device_id}", payload
        )
