"""Async HTTP client wrapper for the Accelo REST API."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .auth import AuthManager
from .config import AcceloConfig

logger = logging.getLogger(__name__)


class AcceloAPIError(Exception):
    """Raised when the Accelo API returns an error."""

    def __init__(self, status: str, message: str, http_code: int, more_info: str = ""):
        self.status = status
        self.message = message
        self.http_code = http_code
        self.more_info = more_info
        super().__init__(f"[{http_code}] {status}: {message}")


class RateLimitError(AcceloAPIError):
    """Raised when rate limited (429)."""

    def __init__(self, message: str, reset_at: float):
        self.reset_at = reset_at
        super().__init__("too_many_requests", message, 429)


class AcceloClient:
    """Async wrapper around Accelo's REST API.

    Handles auth header injection, rate limit tracking, retry logic,
    and parameter serialization.
    """

    def __init__(self, auth: AuthManager, config: AcceloConfig):
        self._auth = auth
        self._base_url = config.base_url
        self._http = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self.rate_remaining: int = 5000
        self.rate_limit: int = 5000
        self.rate_reset: float = 0

    async def close(self):
        """Close HTTP client and auth manager."""
        await self._http.aclose()
        await self._auth.close()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """GET request to Accelo API."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, data: dict[str, Any] | None = None) -> dict:
        """POST request to Accelo API."""
        return await self._request("POST", path, data=data)

    async def put(self, path: str, data: dict[str, Any] | None = None) -> dict:
        """PUT request to Accelo API."""
        return await self._request("PUT", path, data=data)

    async def delete(self, path: str) -> dict:
        """DELETE request to Accelo API."""
        return await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        _retry: bool = True,
    ) -> dict:
        """Execute an API request with auth, rate limit tracking, and retry."""
        token = await self._auth.get_token()
        url = f"{self._base_url}{path}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        response = await self._http.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
        )

        # Track rate limits from response headers
        self._update_rate_limits(response)

        # Handle 401 — refresh token and retry once
        if response.status_code == 401 and _retry:
            logger.info("Got 401, refreshing token and retrying")
            self._auth._token = None  # Force re-acquisition
            self._auth._expires_at = 0
            return await self._request(method, path, params=params, data=data, _retry=False)

        # Handle 429 — rate limited
        if response.status_code == 429:
            raise RateLimitError(
                f"Rate limit exceeded. Resets at {self.rate_reset}",
                reset_at=self.rate_reset,
            )

        # Handle 5xx — retry once with backoff
        if response.status_code >= 500 and _retry:
            logger.warning("Got %d, retrying in 1s", response.status_code)
            await asyncio.sleep(1)
            return await self._request(method, path, params=params, data=data, _retry=False)

        # Parse response
        try:
            result = response.json()
        except Exception:
            raise AcceloAPIError(
                "parse_error",
                f"Failed to parse response: {response.text[:200]}",
                response.status_code,
            )

        # Check for API-level errors
        meta = result.get("meta", {})
        if meta.get("status") != "ok" and response.status_code >= 400:
            raise AcceloAPIError(
                status=meta.get("status", "unknown"),
                message=meta.get("message", response.text[:200]),
                http_code=response.status_code,
                more_info=meta.get("more_info", ""),
            )

        return result

    def _update_rate_limits(self, response: httpx.Response):
        """Update rate limit tracking from response headers."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            self.rate_remaining = int(remaining)

        limit = response.headers.get("X-RateLimit-Limit")
        if limit is not None:
            self.rate_limit = int(limit)

        reset = response.headers.get("X-RateLimit-Reset")
        if reset is not None:
            self.rate_reset = float(reset)

        if self.rate_remaining < 100:
            logger.warning(
                "Rate limit low: %d/%d remaining, resets at %s",
                self.rate_remaining,
                self.rate_limit,
                time.strftime("%H:%M:%S", time.localtime(self.rate_reset)),
            )


def build_filters(filters: dict[str, Any] | None) -> str | None:
    """Convert a filter dict to Accelo's filter string syntax.

    Examples:
        {"standing": "active"} -> "standing(active)"
        {"standing": "active", "order_by_desc": "date_modified"}
            -> "standing(active),order_by_desc(date_modified)"
        {"status": [1, 2]} -> "status(1,2)"
        {"owner": {"staff": [17, 13]}} -> "owner(staff(17,13))"
    """
    if not filters:
        return None

    parts = []
    for key, value in filters.items():
        if isinstance(value, dict):
            # Object filter: {"owner": {"staff": [17, 13]}} -> "owner(staff(17,13))"
            inner_parts = []
            for obj_type, obj_ids in value.items():
                if isinstance(obj_ids, list):
                    inner_parts.append(f"{obj_type}({','.join(str(v) for v in obj_ids)})")
                else:
                    inner_parts.append(f"{obj_type}({obj_ids})")
            parts.append(f"{key}({','.join(inner_parts)})")
        elif isinstance(value, list):
            # Multi-value filter: {"status": [1, 2]} -> "status(1,2)"
            parts.append(f"{key}({','.join(str(v) for v in value)})")
        elif isinstance(value, bool):
            parts.append(f"{key}({'yes' if value else 'no'})")
        else:
            # Simple filter: {"standing": "active"} -> "standing(active)"
            parts.append(f"{key}({value})")

    return ",".join(parts)


def build_params(
    filters: dict[str, Any] | None = None,
    fields: str | None = None,
    search: str | None = None,
    page: int = 0,
    limit: int = 10,
) -> dict[str, Any]:
    """Build Accelo API query parameters from structured inputs.

    Args:
        filters: Dict of filter name -> value(s), serialized to _filters syntax
        fields: Accelo _fields string (e.g. "website,phone,postal_address(city)")
        search: Free-text search term
        page: Page number (0-indexed)
        limit: Results per page (max 100)
    """
    params: dict[str, Any] = {
        "_page": page,
        "_limit": min(limit, 100),
    }

    filter_str = build_filters(filters)
    if filter_str:
        params["_filters"] = filter_str

    if fields:
        params["_fields"] = fields

    if search:
        params["_search"] = search

    return params
