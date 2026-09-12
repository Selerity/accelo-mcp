"""Integration tests for company tools with mocked HTTP."""

from __future__ import annotations

import json
import os

import httpx
import pytest
import respx

# Set env vars before importing server
os.environ.setdefault("ACCELO_DEPLOYMENT", "test")
os.environ.setdefault("ACCELO_CLIENT_ID", "test-id")
os.environ.setdefault("ACCELO_CLIENT_SECRET", "test-secret")

from accelo_mcp.server import create_server


@pytest.fixture
def server_and_client():
    """Create server with pre-authed client."""
    server, client = create_server()
    # Pre-seed auth to skip token acquisition
    client._auth._token = "test-token"
    client._auth._expires_at = 9999999999.0
    return server, client


def parse_result(result) -> dict:
    """Parse a CallToolResult into a dict."""
    return json.loads(result.content[0].text)


BASE = "https://test.api.accelo.com/api/v0"


class TestListCompanies:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_companies_basic(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/companies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "1", "name": "Planet Express"},
                        {"id": "2", "name": "Mom's Friendly Robot Company"},
                    ],
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_list_companies", {"limit": 10}))
        await client.close()

        assert result["response"][0]["name"] == "Planet Express"
        assert len(result["response"]) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_companies_with_filters(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/companies").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": [{"id": "1", "name": "Active Co"}]},
            )
        )

        await server.call_tool(
            "accelo_list_companies",
            {"filters": {"standing": "active"}, "fields": "website,phone"},
        )
        await client.close()

        # Verify the request was made with correct params (URL-encoded)
        request = route.calls[0].request
        url_str = str(request.url)
        assert "standing%28active%29" in url_str or "standing(active)" in url_str
        assert "website" in url_str
        assert "phone" in url_str


class TestGetCompany:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_company(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/companies/42").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "id": "42",
                        "name": "Planet Express",
                        "website": "planetexpress.com",
                    },
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_get_company", {"id": 42, "fields": "website"})
        )
        await client.close()

        assert result["response"]["id"] == "42"
        assert result["response"]["website"] == "planetexpress.com"


class TestCountCompanies:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_companies(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/companies/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "156"}},
            )
        )

        result = parse_result(await server.call_tool("accelo_count_companies", {}))
        await client.close()

        assert result["response"]["count"] == "156"


class TestCreateCompany:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_company(self, server_and_client):
        server, client = server_and_client

        respx.post(f"{BASE}/companies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "99", "name": "New Corp"},
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_create_company", {"name": "New Corp", "website": "newcorp.com"}
            )
        )
        await client.close()

        assert result["response"]["id"] == "99"


class TestUpdateCompany:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_company(self, server_and_client):
        server, client = server_and_client

        respx.put(f"{BASE}/companies/42").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "42", "name": "Updated Corp"},
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_update_company", {"id": 42, "name": "Updated Corp"})
        )
        await client.close()

        assert result["response"]["name"] == "Updated Corp"
