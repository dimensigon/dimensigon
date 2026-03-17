from __future__ import annotations

from typing import Any

import httpx

from .auth import AuthManager
from .config import config
from .exceptions import DimensigonAPIError, DimensigonConnectionError


class DimensigonClient:
    def __init__(self):
        self._auth = AuthManager()
        self._client = httpx.AsyncClient(verify=config.verify_ssl, timeout=60.0)

    async def _request(
        self, method: str, path: str, params: list[str] | None = None, **kwargs: Any
    ) -> Any:
        """Make an authenticated request to the Dimensigon API.

        params is a list of key-only query parameters (e.g. ["human", "steps"])
        that are appended as ?human&steps per Dimensigon's check_param_in_uri pattern.
        """
        token = await self._auth.get_token(self._client)
        headers = {"Authorization": f"Bearer {token}"}

        url = f"{config.api_url}{path}"
        if params:
            url += "?" + "&".join(params)

        try:
            resp = await self._client.request(method, url, headers=headers, **kwargs)
        except httpx.ConnectError as e:
            raise DimensigonConnectionError(
                f"Cannot connect to Dimensigon at {config.host}:{config.port}: {e}"
            )

        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("error", body.get("message", resp.text))
            except Exception:
                msg = resp.text
            raise DimensigonAPIError(resp.status_code, str(msg), path)

        if resp.status_code == 204:
            return None
        return resp.json()

    async def _get(self, path: str, params: list[str] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, data: Any = None, params: list[str] | None = None) -> Any:
        return await self._request("POST", path, params=params, json=data)

    # ── Discovery ──

    async def list_servers(self, gates: bool = False) -> Any:
        p = ["human"]
        if gates:
            p.append("gates")
        return await self._get("/servers", p)

    async def get_server(self, server_id: str) -> Any:
        return await self._get(f"/servers/{server_id}", ["gates", "human"])

    async def list_granules(self) -> Any:
        return await self._get("/granules")

    async def list_orchestrations(
        self, steps: bool = False, schema: bool = False, target: bool = False
    ) -> Any:
        p = ["split_lines"]
        if steps:
            p.extend(["steps", "action"])
        if schema:
            p.append("schema")
        if target:
            p.append("target")
        return await self._get("/orchestrations", p)

    async def get_orchestration(self, orch_id: str) -> Any:
        return await self._get(
            f"/orchestrations/{orch_id}", ["schema", "target", "steps", "action", "split_lines"]
        )

    async def list_action_templates(self) -> Any:
        return await self._get("/action_templates", ["split_lines"])

    async def get_action_template(self, at_id: str) -> Any:
        return await self._get(f"/action_templates/{at_id}", ["split_lines"])

    async def list_executions(self, steps: bool = False) -> Any:
        p = ["human"]
        if steps:
            p.append("steps")
        return await self._get("/orchestration_executions", p)

    async def get_execution(self, exec_id: str) -> Any:
        return await self._get(f"/orchestration_executions/{exec_id}", ["steps", "human"])

    # ── Creation ──

    async def create_action_template(self, data: dict) -> Any:
        return await self._post("/action_templates", data)

    async def create_orchestration_full(self, data: dict) -> Any:
        return await self._post("/orchestrations/full", data)

    async def create_steps(self, data: list[dict] | dict) -> Any:
        return await self._post("/steps", data)

    # ── Execution ──

    async def launch_orchestration(
        self, data: dict, orch_id: str | None = None
    ) -> tuple[Any, int]:
        """Returns (response_body, status_code)."""
        path = f"/launch/orchestration/{orch_id}" if orch_id else "/launch/orchestration"
        token = await self._auth.get_token(self._client)
        url = f"{config.api_url}{path}?human"
        try:
            resp = await self._client.post(
                url,
                json=data,
                headers={"Authorization": f"Bearer {token}"},
                timeout=120.0,
            )
        except httpx.ConnectError as e:
            raise DimensigonConnectionError(str(e))

        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("error", resp.text)
            except Exception:
                msg = resp.text
            raise DimensigonAPIError(resp.status_code, str(msg), path)

        return resp.json(), resp.status_code

    async def launch_command(self, data: dict) -> Any:
        return await self._post("/launch/command", data, ["human"])

    # ── Vault ──

    async def list_vault(self, scopes: bool = False, scope: str | None = None) -> Any:
        if scopes:
            return await self._get("/vault", ["scopes"])
        p = ["human"]
        if scope:
            p.append(f"scope={scope}")
        return await self._get("/vault", p)

    async def close(self) -> None:
        await self._client.aclose()
