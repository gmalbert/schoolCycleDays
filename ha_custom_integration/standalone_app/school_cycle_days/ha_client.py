"""Remote Home Assistant REST and WebSocket client."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx
import websockets


class HomeAssistantError(RuntimeError):
    """Raised when Home Assistant returns an error."""


class HomeAssistantClient:
    """Use Home Assistant's public APIs without running inside HA."""

    def __init__(self, base_url: str, token: str, *, verify_ssl: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify_ssl = verify_ssl

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @property
    def websocket_url(self) -> str:
        if self.base_url.startswith("https://"):
            return "wss://" + self.base_url.removeprefix("https://") + "/api/websocket"
        if self.base_url.startswith("http://"):
            return "ws://" + self.base_url.removeprefix("http://") + "/api/websocket"
        raise HomeAssistantError("Home Assistant URL must begin with http:// or https://")

    async def _get_json(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            response = await client.get(
                f"{self.base_url}{path}", headers=self._headers, params=params
            )
            response.raise_for_status()
            return response.json()

    async def test_connection(self) -> dict[str, Any]:
        return await self._get_json("/api/")

    async def config(self) -> dict[str, Any]:
        return await self._get_json("/api/config")

    async def calendars(self) -> list[dict[str, str]]:
        return await self._get_json("/api/calendars")

    async def events(
        self, entity_id: str, start: str, end: str
    ) -> list[dict[str, Any]]:
        encoded = quote(entity_id, safe=".")
        return await self._get_json(
            f"/api/calendars/{encoded}", params={"start": start, "end": end}
        )

    async def create_event(
        self,
        entity_id: str,
        *,
        start_date: str,
        end_date: str,
        summary: str,
        description: str,
    ) -> None:
        payload = {
            "entity_id": entity_id,
            "start_date": start_date,
            "end_date": end_date,
            "summary": summary,
            "description": description,
        }
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/api/services/calendar/create_event",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()

    async def delete_event(
        self,
        entity_id: str,
        uid: str,
        *,
        recurrence_id: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "type": "calendar/event/delete",
            "entity_id": entity_id,
            "uid": uid,
        }
        if recurrence_id:
            payload["recurrence_id"] = recurrence_id
        await self.websocket_command(payload)

    async def websocket_command(self, payload: dict[str, Any]) -> Any:
        """Authenticate to HA WebSocket and execute one command."""
        ssl_context = None
        if self.websocket_url.startswith("wss://") and not self.verify_ssl:
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        async with websockets.connect(self.websocket_url, ssl=ssl_context) as websocket:
            first = json.loads(await websocket.recv())
            if first.get("type") != "auth_required":
                raise HomeAssistantError(f"Unexpected HA WebSocket greeting: {first}")

            await websocket.send(
                json.dumps({"type": "auth", "access_token": self.token})
            )
            auth = json.loads(await websocket.recv())
            if auth.get("type") != "auth_ok":
                raise HomeAssistantError(
                    f"Home Assistant WebSocket authentication failed: {auth}"
                )

            message = {"id": 1, **payload}
            await websocket.send(json.dumps(message))
            while True:
                result = json.loads(await websocket.recv())
                if result.get("id") != 1:
                    continue
                if not result.get("success", False):
                    error = result.get("error", {})
                    raise HomeAssistantError(
                        error.get("message", "Home Assistant WebSocket command failed")
                    )
                return result.get("result")
