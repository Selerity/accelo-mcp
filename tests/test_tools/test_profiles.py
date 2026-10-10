"""Integration tests for profile field tools with mocked HTTP."""

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
    client._auth._token = "test-token"
    client._auth._expires_at = 9999999999.0
    return server, client


def parse_result(result) -> dict:
    """Parse a CallToolResult into a dict."""
    return json.loads(result.content[0].text)


BASE = "https://test.api.accelo.com/api/v0"


class TestSetProfileValue:
    @respx.mock
    @pytest.mark.asyncio
    async def test_set_profile_value_uses_object_put(self, server_and_client):
        """Writes via PUT /{object_type}/{object_id} keyed as profile.{field_id}."""
        server, client = server_and_client

        route = respx.put(f"{BASE}/contracts/29").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "29"},
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_set_profile_value",
                {
                    "object_type": "contracts",
                    "object_id": 29,
                    "profile_field_id": 80,
                    "value": "https://example.com/doc",
                },
            )
        )
        await client.close()

        assert route.called
        # Body is form-encoded with the profile.{field_id} key
        request_body = route.calls[0].request.content.decode()
        assert "profile.80" in request_body
        assert result["response"]["id"] == "29"

    @respx.mock
    @pytest.mark.asyncio
    async def test_set_profile_value_returns_structured_error(self, server_and_client):
        """Surfaces the real Accelo error instead of an opaque failure."""
        server, client = server_and_client

        respx.put(f"{BASE}/contracts/29").mock(
            return_value=httpx.Response(
                400,
                json={
                    "meta": {
                        "status": "invalid_request",
                        "message": "The resource endpoint was not recognized.",
                        "more_info": "https://api.accelo.com/docs",
                    }
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_set_profile_value",
                {
                    "object_type": "contracts",
                    "object_id": 29,
                    "profile_field_id": 80,
                    "value": "x",
                },
            )
        )
        await client.close()

        assert result["error"] is True
        assert result["status"] == "invalid_request"
        assert "resource endpoint" in result["message"]
        assert result["http_code"] == 400
        assert result["more_info"] == "https://api.accelo.com/docs"


class TestListProfileFields:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_profile_fields(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/contracts/profiles/fields").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "80", "field_name": "Contract", "field_type": "hyperlink"}],
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_profile_fields", {"object_type": "contracts"})
        )
        await client.close()

        assert result["response"][0]["id"] == "80"


class TestGetProfileValues:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_profile_values(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "80", "value": "https://example.com/doc"}],
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_get_profile_values",
                {"object_type": "contracts", "object_id": 29},
            )
        )
        await client.close()

        assert result["response"][0]["value"] == "https://example.com/doc"
