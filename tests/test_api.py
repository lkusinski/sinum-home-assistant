"""Tests for the Sinum cloud API client."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.sinum_home_assistant"

# Load api.py without executing the integration __init__, which needs a full
# Home Assistant installation.
components = types.ModuleType("custom_components")
components.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", components)
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "sinum_home_assistant")]
sys.modules.setdefault(PACKAGE, package)

spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.api", ROOT / "custom_components" / "sinum_home_assistant" / "api.py"
)
api = importlib.util.module_from_spec(spec)
sys.modules[f"{PACKAGE}.api"] = api
spec.loader.exec_module(api)

SinumHomeAssistantClient = api.SinumHomeAssistantClient
SinumNotSupportedError = api.SinumNotSupportedError


class FakeRequest:
    def __init__(self, session, response, delay):
        self._session = session
        self._response = response
        self._delay = delay

    async def __aenter__(self):
        self._session.active += 1
        self._session.max_active = max(
            self._session.max_active, self._session.active
        )
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._response

    async def __aexit__(self, *_exc):
        self._session.active -= 1
        return False


class FakeResponse:
    def __init__(self, status, body=""):
        self.status = status
        self._body = body

    async def text(self):
        return self._body


class FakeSession:
    def __init__(self, responses=None, delay=0.01):
        self.responses = list(responses or [])
        self.calls: list[tuple[str, str]] = []
        self.active = 0
        self.max_active = 0
        self.delay = delay

    def request(self, method, url, **_kwargs):
        self.calls.append((method, url))
        if self.responses:
            status, body = self.responses.pop(0)
        else:
            status, body = 200, '{"data": {}}'
        return FakeRequest(self, FakeResponse(status, body), self.delay)


def make_client(session):
    client = SinumHomeAssistantClient(
        session, email="test@example.com", device_id="device", refresh_token="r"
    )
    client._access_token = "token"
    client._expires_at = time.monotonic() + 3600
    return client


@pytest.mark.asyncio
async def test_requests_are_serialized():
    session = FakeSession()
    client = make_client(session)

    await asyncio.gather(
        *(client.async_get(f"path/{index}") for index in range(5))
    )

    assert len(session.calls) == 5
    assert session.max_active == 1


@pytest.mark.asyncio
async def test_retries_http_429(monkeypatch):
    monkeypatch.setattr(api, "REQUEST_RETRY_DELAY", 0)
    session = FakeSession(
        [
            (429, "already has a request in flight"),
            (200, '{"data": {"ok": true}}'),
        ]
    )
    client = make_client(session)

    result = await client.async_get("path")

    assert result == {"data": {"ok": True}}
    assert len(session.calls) == 2


@pytest.mark.asyncio
async def test_retries_transient_5xx(monkeypatch):
    monkeypatch.setattr(api, "REQUEST_RETRY_DELAY", 0)
    session = FakeSession([(503, "busy"), (200, '{"data": {"ok": true}}')])
    client = make_client(session)

    result = await client.async_get("path")

    assert result == {"data": {"ok": True}}
    assert len(session.calls) == 2


@pytest.mark.asyncio
async def test_not_supported_on_404():
    session = FakeSession([(404, "missing")])
    client = make_client(session)

    with pytest.raises(SinumNotSupportedError):
        await client.async_get("path")
