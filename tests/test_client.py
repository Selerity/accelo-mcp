"""Tests for accelo_mcp.client module."""

from __future__ import annotations

import httpx
import pytest
import respx

from accelo_mcp.auth import AuthManager
from accelo_mcp.client import (
    AcceloClient,
    RateLimitError,
    build_filters,
    build_params,
)


@pytest.fixture
@respx.mock
async def client(mock_config):
    """Create an AcceloClient with a pre-authenticated AuthManager."""
    # Pre-seed the auth with a valid token
    auth = AuthManager(mock_config)
    auth._token = "test-token"
    auth._expires_at = 9999999999.0

    c = AcceloClient(auth, mock_config)
    yield c
    await c.close()


class TestBuildFilters:
    """Tests for filter dict -> Accelo filter string serialization."""

    def test_none_returns_none(self):
        assert build_filters(None) is None

    def test_empty_returns_none(self):
        assert build_filters({}) is None

    def test_simple_filter(self):
        assert build_filters({"standing": "active"}) == "standing(active)"

    def test_multiple_filters(self):
        result = build_filters({"standing": "active", "status": 3})
        assert "standing(active)" in result
        assert "status(3)" in result

    def test_list_values(self):
        assert build_filters({"status": [1, 2, 3]}) == "status(1,2,3)"

    def test_object_filter(self):
        result = build_filters({"owner": {"staff": [17, 13]}})
        assert result == "owner(staff(17,13))"

    def test_object_filter_multiple_types(self):
        result = build_filters({"owner": {"staff": [17], "affiliation": [22]}})
        assert "staff(17)" in result
        assert "affiliation(22)" in result

    def test_boolean_filter(self):
        assert build_filters({"reimbursable": True}) == "reimbursable(yes)"
        assert build_filters({"reimbursable": False}) == "reimbursable(no)"

    def test_date_filter(self):
        result = build_filters({"date_created_after": 1490140800})
        assert result == "date_created_after(1490140800)"

    def test_order_filter(self):
        assert build_filters({"order_by_desc": "id"}) == "order_by_desc(id)"


class TestBuildParams:
    """Tests for build_params helper."""

    def test_defaults(self):
        params = build_params()
        assert params == {"_page": 0, "_limit": 10}

    def test_with_all_options(self):
        params = build_params(
            filters={"standing": "active"},
            fields="website,phone",
            search="Planet Express",
            page=2,
            limit=25,
        )
        assert params["_page"] == 2
        assert params["_limit"] == 25
        assert params["_filters"] == "standing(active)"
        assert params["_fields"] == "website,phone"
        assert params["_search"] == "Planet Express"

    def test_limit_capped_at_100(self):
        params = build_params(limit=500)
        assert params["_limit"] == 100

    def test_no_filters_key_when_none(self):
        params = build_params(filters=None)
        assert "_filters" not in params

    def test_no_fields_key_when_none(self):
        params = build_params(fields=None)
        assert "_fields" not in params


class TestAcceloClientRequests:
    """Tests for AcceloClient request methods."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_request(self, mock_config):
        """GET request with params."""
        auth = AuthManager(mock_config)
        auth._token = "test-token"
        auth._expires_at = 9999999999.0
        client = AcceloClient(auth, mock_config)

        route = respx.get(f"{mock_config.base_url}/companies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok", "message": "Everything executed as expected."},
                    "response": [{"id": "1", "name": "Planet Express"}],
                },
            )
        )

        result = await client.get("/companies", params={"_limit": 10})
        await client.close()

        assert result["response"][0]["name"] == "Planet Express"
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_request(self, mock_config):
        """POST request with data."""
        auth = AuthManager(mock_config)
        auth._token = "test-token"
        auth._expires_at = 9999999999.0
        client = AcceloClient(auth, mock_config)

        respx.post(f"{mock_config.base_url}/companies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "45", "name": "New Company"},
                },
            )
        )

        result = await client.post("/companies", data={"name": "New Company"})
        await client.close()

        assert result["response"]["id"] == "45"

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_tracking(self, mock_config):
        """Updates rate limit from response headers."""
        auth = AuthManager(mock_config)
        auth._token = "test-token"
        auth._expires_at = 9999999999.0
        client = AcceloClient(auth, mock_config)

        respx.get(f"{mock_config.base_url}/staff").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "X-RateLimit-Remaining": "4500",
                    "X-RateLimit-Limit": "5000",
                    "X-RateLimit-Reset": "1700000000",
                },
                json={"meta": {"status": "ok"}, "response": []},
            )
        )

        await client.get("/staff")
        await client.close()

        assert client.rate_remaining == 4500
        assert client.rate_limit == 5000
        assert client.rate_reset == 1700000000.0

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_config):
        """Raises RateLimitError on 429."""
        auth = AuthManager(mock_config)
        auth._token = "test-token"
        auth._expires_at = 9999999999.0
        client = AcceloClient(auth, mock_config)

        respx.get(f"{mock_config.base_url}/companies").mock(
            return_value=httpx.Response(
                429,
                headers={"X-RateLimit-Reset": "1700000000"},
                json={
                    "meta": {
                        "status": "too_many_requests",
                        "message": "Rate limit exceeded",
                    }
                },
            )
        )

        with pytest.raises(RateLimitError):
            await client.get("/companies")
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_401_retry(self, mock_config):
        """Retries once on 401 after refreshing token."""
        auth = AuthManager(mock_config)
        auth._token = "expired-token"
        auth._expires_at = 9999999999.0
        client = AcceloClient(auth, mock_config)

        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(401, json={"meta": {"status": "invalid_client"}})
            return httpx.Response(200, json={"meta": {"status": "ok"}, "response": []})

        respx.get(f"{mock_config.base_url}/staff").mock(side_effect=side_effect)
        # Mock the token re-acquisition
        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(200, json={"access_token": "new-token", "expires_in": 3600})
        )

        result = await client.get("/staff")
        await client.close()

        assert result["response"] == []
        assert call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_5xx_retry(self, mock_config):
        """Retries once on 5xx."""
        auth = AuthManager(mock_config)
        auth._token = "test-token"
        auth._expires_at = 9999999999.0
        client = AcceloClient(auth, mock_config)

        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(500, json={"meta": {"status": "server_error"}})
            return httpx.Response(200, json={"meta": {"status": "ok"}, "response": {"id": "1"}})

        respx.get(f"{mock_config.base_url}/companies/1").mock(side_effect=side_effect)

        result = await client.get("/companies/1")
        await client.close()

        assert result["response"]["id"] == "1"
        assert call_count == 2
