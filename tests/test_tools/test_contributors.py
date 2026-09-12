"""Integration tests for contributor-type tools with mocked HTTP."""

from __future__ import annotations

import json
import os

import httpx
import pytest
import respx

os.environ.setdefault("ACCELO_DEPLOYMENT", "test")
os.environ.setdefault("ACCELO_CLIENT_ID", "test-id")
os.environ.setdefault("ACCELO_CLIENT_SECRET", "test-secret")

from accelo_mcp.server import create_server


@pytest.fixture
def server_and_client():
    server, client = create_server()
    client._auth._token = "test-token"
    client._auth._expires_at = 9999999999.0
    return server, client


def parse_result(result) -> dict:
    return json.loads(result.content[0].text)


BASE = "https://test.api.accelo.com/api/v0"


class TestListContributorTypes:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list(self, server_and_client):
        server, client = server_and_client
        respx.get(f"{BASE}/contributors/types").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "1", "title": "Advisor", "standing": "active"}],
                },
            )
        )
        result = parse_result(
            await server.call_tool("accelo_list_contributor_types", {"limit": 10})
        )
        await client.close()
        assert result["response"][0]["title"] == "Advisor"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_with_filter(self, server_and_client):
        server, client = server_and_client
        route = respx.get(f"{BASE}/contributors/types").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": []})
        )
        await server.call_tool(
            "accelo_list_contributor_types", {"filters": {"default_standing": "active"}}
        )
        await client.close()
        assert "default_standing" in str(route.calls[0].request.url)


class TestGetContributorType:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get(self, server_and_client):
        server, client = server_and_client
        respx.get(f"{BASE}/contributors/types/1").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "1", "title": "Advisor"}},
            )
        )
        result = parse_result(await server.call_tool("accelo_get_contributor_type", {"id": 1}))
        await client.close()
        assert result["response"]["id"] == "1"


class TestCountContributorTypes:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_drops_pagination(self, server_and_client):
        server, client = server_and_client
        route = respx.get(f"{BASE}/contributors/types/count").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"count": "3"}}
            )
        )
        result = parse_result(await server.call_tool("accelo_count_contributor_types", {}))
        await client.close()
        assert result["response"]["count"] == "3"
        url_str = str(route.calls[0].request.url)
        assert "_page" not in url_str
        assert "_limit" not in url_str
