"""Thin async client for the Intergas Orion (ARCH_2_0) cloud API.

The API is a FastAPI backend that returns an ES256 JWT in the ``jwt`` field of
the authenticate response. The JWT lasts about an hour; this client simply
re-authenticates with email/password on a 401/403 instead of depending on the
refresh-token contract.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_BASE

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class IntergasAuthError(Exception):
    """Raised when authentication fails (bad credentials)."""


class IntergasApiError(Exception):
    """Raised for any other API failure."""


class IntergasOrionClient:
    """Minimal client for one Intergas Comfort Touch account."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str):
        self._session = session
        self._email = email
        self._password = password
        self._jwt: str | None = None
        self._account_id: str | None = None
        self._auth_lock = asyncio.Lock()

    @property
    def account_id(self) -> str | None:
        return self._account_id

    async def _raw(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        """Perform one HTTP request and return (status, parsed JSON or None)."""
        url = f"{API_BASE}{path}"
        try:
            async with self._session.request(
                method, url, json=json_body, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status >= 400:
                    return resp.status, None
                body = await resp.read()
                if not body:
                    return resp.status, None
                return resp.status, await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise IntergasApiError(f"{method} {path} failed: {err!r}") from err

    async def authenticate(self) -> None:
        """Log in and cache the JWT and account_id."""
        status, data = await self._raw(
            "POST",
            "/v1/accounts/authenticate",
            json_body={"email": self._email, "password": self._password},
        )
        if status in (401, 403):
            raise IntergasAuthError("Invalid credentials")
        if status != 200 or not isinstance(data, dict):
            raise IntergasApiError(f"authenticate failed: HTTP {status}")
        self._jwt = data.get("jwt")
        self._account_id = data.get("account_id")
        if not self._jwt or not self._account_id:
            raise IntergasApiError("authenticate response missing jwt/account_id")

    async def platform(self) -> str:
        """Return 'ARCH_1_0' or 'ARCH_2_0' for this account."""
        status, data = await self._raw(
            "POST", "/v1/accounts/platform_check", json_body={"email": self._email}
        )
        if status != 200 or not isinstance(data, dict):
            raise IntergasApiError(f"platform_check failed: HTTP {status}")
        return data.get("platform", "")

    async def _ensure_auth(self, stale_jwt: str | None = None) -> None:
        """Authenticate if there is no token, or if the token in use went stale."""
        async with self._auth_lock:
            if self._jwt is None or self._jwt == stale_jwt:
                self._jwt = None
                await self.authenticate()

    async def _request(self, method: str, path: str, *, json_body: Any = None) -> Any:
        """Authenticated request; ``{aid}`` in path is replaced by the account id."""
        await self._ensure_auth()
        path = path.format(aid=self._account_id)
        jwt = self._jwt
        status, data = await self._raw(
            method, path, json_body=json_body, headers={"Authorization": f"Bearer {jwt}"}
        )
        if status in (401, 403):
            # Token most likely expired: re-authenticate once and retry.
            await self._ensure_auth(stale_jwt=jwt)
            status, data = await self._raw(
                method,
                path,
                json_body=json_body,
                headers={"Authorization": f"Bearer {self._jwt}"},
            )
        if status in (401, 403):
            raise IntergasAuthError(f"{method} {path}: HTTP {status} after re-auth")
        if status >= 400:
            raise IntergasApiError(f"{method} {path}: HTTP {status}")
        return data

    # --- resource helpers -------------------------------------------------
    async def get_heaters(self) -> list[dict]:
        return await self._request("GET", "/v1/accounts/{aid}/heaters") or []

    async def get_heater(self, heater_id: str) -> dict:
        return await self._request(
            "GET", f"/v1/accounts/{{aid}}/heaters/{heater_id}"
        )

    async def get_zones(self, heater_id: str) -> list[dict]:
        return (
            await self._request(
                "GET", f"/v1/accounts/{{aid}}/heaters/{heater_id}/zones"
            )
            or []
        )

    async def set_zone_temperature(
        self, heater_id: str, zone_number: int, temperature: float
    ) -> None:
        """Set a zone's manual target temperature (ZoneUpdate.target_temperature)."""
        await self._request(
            "PATCH",
            f"/v1/accounts/{{aid}}/heaters/{heater_id}/zones/{zone_number}",
            json_body={"target_temperature": round(float(temperature), 1)},
        )
