"""Integration tests for the composite enumeration tools with mocked HTTP."""

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
    """Create server with pre-authed client."""
    server, client = create_server()
    client._auth._token = "test-token"
    client._auth._expires_at = 9999999999.0
    return server, client


def parse_result(result) -> dict:
    """Parse a CallToolResult into a dict."""
    return json.loads(result.content[0].text)


BASE = "https://test.api.accelo.com/api/v0"


class TestListEnum:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_issue_statuses(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/issues/statuses").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "1", "title": "Open", "standing": "open"},
                        {"id": "4", "title": "Closed", "standing": "closed"},
                    ],
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_list_enum", {"object": "issues", "enum_type": "statuses"}
            )
        )
        await client.close()

        assert len(result["response"]) == 2
        assert result["response"][0]["title"] == "Open"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_job_types(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/jobs/types").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "3", "title": "Retainer"}],
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_enum", {"object": "jobs", "enum_type": "types"})
        )
        await client.close()

        assert result["response"][0]["title"] == "Retainer"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_activity_classes(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/activities/classes").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "1", "title": "Client Work"}],
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_list_enum", {"object": "activities", "enum_type": "classes"}
            )
        )
        await client.close()

        assert result["response"][0]["title"] == "Client Work"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_enum_with_filters(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/issues/statuses").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": []},
            )
        )

        await server.call_tool(
            "accelo_list_enum",
            {
                "object": "issues",
                "enum_type": "statuses",
                "filters": {"standing": "open"},
                "fields": "color",
            },
        )
        await client.close()

        url_str = str(route.calls[0].request.url)
        assert "standing" in url_str
        assert "color" in url_str

    @pytest.mark.asyncio
    async def test_list_enum_invalid_combo(self, server_and_client):
        server, client = server_and_client

        result = parse_result(
            await server.call_tool(
                "accelo_list_enum", {"object": "companies", "enum_type": "types"}
            )
        )
        await client.close()

        assert result["error"] == "invalid_enum"
        assert "companies/statuses" in result["message"]


class TestGetEnum:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_issue_status(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/issues/priorities/1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "1", "title": "Extreme"},
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_get_enum",
                {"object": "issues", "enum_type": "priorities", "id": 1},
            )
        )
        await client.close()

        assert result["response"]["title"] == "Extreme"

    @pytest.mark.asyncio
    async def test_get_enum_unsupported(self, server_and_client):
        server, client = server_and_client

        # issues/statuses has get=False in the registry
        result = parse_result(
            await server.call_tool(
                "accelo_get_enum",
                {"object": "issues", "enum_type": "statuses", "id": 1},
            )
        )
        await client.close()

        assert result["error"] == "unsupported_operation"

    @pytest.mark.asyncio
    async def test_get_enum_invalid_combo(self, server_and_client):
        server, client = server_and_client

        result = parse_result(
            await server.call_tool(
                "accelo_get_enum",
                {"object": "widgets", "enum_type": "statuses", "id": 1},
            )
        )
        await client.close()

        assert result["error"] == "invalid_enum"


class TestCountEnum:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_company_statuses(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/companies/statuses/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "5"}},
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_count_enum", {"object": "companies", "enum_type": "statuses"}
            )
        )
        await client.close()

        assert result["response"]["count"] == "5"
        url_str = str(route.calls[0].request.url)
        assert "_page" not in url_str
        assert "_limit" not in url_str

    @pytest.mark.asyncio
    async def test_count_enum_unsupported(self, server_and_client):
        server, client = server_and_client

        # issues/statuses has count=False in the registry
        result = parse_result(
            await server.call_tool(
                "accelo_count_enum", {"object": "issues", "enum_type": "statuses"}
            )
        )
        await client.close()

        assert result["error"] == "unsupported_operation"
