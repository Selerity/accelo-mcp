"""Integration tests for resource tools with mocked HTTP."""

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


class TestCountResources:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_resources(self, server_and_client):
        server, client = server_and_client
        route = respx.get(f"{BASE}/resources/count").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"count": "42"}}
            )
        )
        result = parse_result(await server.call_tool("accelo_count_resources", {}))
        await client.close()
        assert result["response"]["count"] == "42"
        url_str = str(route.calls[0].request.url)
        assert "_page" not in url_str
        assert "_limit" not in url_str

    @respx.mock
    @pytest.mark.asyncio
    async def test_count_resources_with_filter(self, server_and_client):
        server, client = server_and_client
        route = respx.get(f"{BASE}/resources/count").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"count": "3"}}
            )
        )
        await server.call_tool("accelo_count_resources", {"filters": {"collection_id": 83}})
        await client.close()
        assert "collection_id" in str(route.calls[0].request.url)
