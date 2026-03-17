import base64
import json
import time

import httpx

from .config import config
from .exceptions import AuthenticationError


class AuthManager:
    def __init__(self):
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._access_exp: float = 0
        self._refresh_exp: float = 0

    @staticmethod
    def _decode_exp(token: str) -> float:
        """Extract expiration timestamp from JWT payload."""
        try:
            payload = token.split(".")[1]
            # Add padding
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            data = json.loads(base64.urlsafe_b64decode(payload))
            return float(data.get("exp", 0))
        except Exception:
            return 0

    async def login(self, client: httpx.AsyncClient) -> None:
        """Authenticate with Dimensigon and store tokens."""
        try:
            resp = await client.post(
                f"{config.base_url}/login",
                json={"username": config.username, "password": config.password},
            )
            resp.raise_for_status()
        except httpx.ConnectError as e:
            raise AuthenticationError(f"Cannot connect to {config.base_url}: {e}")
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(
                f"Login failed ({e.response.status_code}): {e.response.text}"
            )

        data = resp.json()
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        if not self._access_token:
            raise AuthenticationError("No access_token in login response")
        self._access_exp = self._decode_exp(self._access_token)
        self._refresh_exp = self._decode_exp(self._refresh_token) if self._refresh_token else 0

    async def refresh(self, client: httpx.AsyncClient) -> None:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            raise AuthenticationError("No refresh token available")
        try:
            resp = await client.post(
                f"{config.base_url}/refresh",
                headers={"Authorization": f"Bearer {self._refresh_token}"},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            # Refresh failed, need full re-login
            await self.login(client)
            return

        data = resp.json()
        self._access_token = data.get("access_token")
        if self._access_token:
            self._access_exp = self._decode_exp(self._access_token)

    async def get_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid access token, refreshing or re-logging in as needed."""
        now = time.time()

        if self._access_token and now < (self._access_exp - config.token_refresh_margin):
            return self._access_token

        # Token expired or near expiry
        if self._refresh_token and now < self._refresh_exp:
            await self.refresh(client)
        else:
            await self.login(client)

        if not self._access_token:
            raise AuthenticationError("Failed to obtain access token")
        return self._access_token
