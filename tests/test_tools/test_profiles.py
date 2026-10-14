"""Integration tests for profile field tools with mocked HTTP."""

from __future__ import annotations

import json
import os
from urllib.parse import parse_qs

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


def _fields_route(field_type: str):
    """Mock the field-type resolution GET returning the given field_type."""
    return respx.get(f"{BASE}/contracts/profiles/fields").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"status": "ok"},
                "response": [{"id": "80", "field_name": "Contract", "field_type": field_type}],
            },
        )
    )


class TestSetProfileValue:
    @respx.mock
    @pytest.mark.asyncio
    async def test_hyperlink_happy_path(self, server_and_client):
        """Writes a hyperlink via the dedicated endpoint and verifies read-back."""
        server, client = server_and_client

        _fields_route("hyperlink")
        post_route = respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "80", "value": "https://example.com/doc"},
                },
            )
        )
        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"field_id": "80", "value": "https://example.com/doc"}],
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

        assert post_route.called
        body = parse_qs(post_route.calls[0].request.content.decode())
        assert body["value"] == ["https://example.com/doc"]
        assert "profile.80" not in body
        assert result.get("error") is not True

    @respx.mock
    @pytest.mark.asyncio
    async def test_silent_no_op_is_caught(self, server_and_client):
        """Write returns ok but read-back shows the old value -> verify_failed."""
        server, client = server_and_client

        _fields_route("hyperlink")
        respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}})
        )
        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"field_id": "80", "value": "https://OLD.example.com"}],
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
                    "value": "https://NEW.example.com",
                },
            )
        )
        await client.close()

        assert result["error"] is True
        assert result["status"] == "verify_failed"

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_row_is_caught(self, server_and_client):
        """Read-back returning no matching row -> verify_failed."""
        server, client = server_and_client

        _fields_route("hyperlink")
        respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}})
        )
        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": []},
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_set_profile_value",
                {
                    "object_type": "contracts",
                    "object_id": 29,
                    "profile_field_id": 80,
                    "value": "https://NEW.example.com",
                },
            )
        )
        await client.close()

        assert result["error"] is True
        assert result["status"] == "verify_failed"

    @respx.mock
    @pytest.mark.asyncio
    async def test_lookup_field(self, server_and_client):
        """Lookup field carries value_id + value_type in the body."""
        server, client = server_and_client

        _fields_route("lookup")
        post_route = respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}})
        )
        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"field_id": "80", "value_id": "42", "value_type": "company"}],
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
                    "value": "42",
                    "value_type": "company",
                },
            )
        )
        await client.close()

        assert post_route.called
        request_body = post_route.calls[0].request.content.decode()
        assert "value_id=42" in request_body
        assert "value_type=company" in request_body
        assert result.get("error") is not True

    @respx.mock
    @pytest.mark.asyncio
    async def test_integer_field(self, server_and_client):
        """Integer field maps the string value to value_int."""
        server, client = server_and_client

        _fields_route("integer")
        post_route = respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}})
        )
        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"field_id": "80", "value_int": "7"}],
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
                    "value": "7",
                },
            )
        )
        await client.close()

        assert post_route.called
        request_body = post_route.calls[0].request.content.decode()
        assert "value_int=7" in request_body
        assert result.get("error") is not True

    @respx.mock
    @pytest.mark.asyncio
    async def test_integer_field_rejects_non_integer_value(self, server_and_client):
        """Non-integer value on an integer field -> invalid_value, no write."""
        server, client = server_and_client

        _fields_route("integer")
        post_route = respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}})
        )

        result = parse_result(
            await server.call_tool(
                "accelo_set_profile_value",
                {
                    "object_type": "contracts",
                    "object_id": 29,
                    "profile_field_id": 80,
                    "value": "abc",
                },
            )
        )
        await client.close()

        assert result["error"] is True
        assert result["status"] == "invalid_value"
        assert not post_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_lookup_field_requires_value_type(self, server_and_client):
        """Lookup field with no value_type -> value_type_required, no write."""
        server, client = server_and_client

        _fields_route("lookup")
        post_route = respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}})
        )

        result = parse_result(
            await server.call_tool(
                "accelo_set_profile_value",
                {
                    "object_type": "contracts",
                    "object_id": 29,
                    "profile_field_id": 80,
                    "value": "42",
                },
            )
        )
        await client.close()

        assert result["error"] is True
        assert result["status"] == "value_type_required"
        assert not post_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_lookup_field_with_value_type_parsed_exact(self, server_and_client):
        """Lookup with value_type: body carries exact value_id + value_type."""
        server, client = server_and_client

        _fields_route("lookup")
        post_route = respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}})
        )
        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"field_id": "80", "value_id": "42", "value_type": "company"}],
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
                    "value": "42",
                    "value_type": "company",
                },
            )
        )
        await client.close()

        assert post_route.called
        body = parse_qs(post_route.calls[0].request.content.decode())
        assert body["value_id"] == ["42"]
        assert body["value_type"] == ["company"]
        assert "None" not in body.get("value_type", [])
        assert result.get("error") is not True

    @respx.mock
    @pytest.mark.asyncio
    async def test_field_resolution_requests_limit_100(self, server_and_client):
        """Field resolution sends _limit=100 so a field past page 1 resolves."""
        server, client = server_and_client

        def _fields_responder(request):
            params = parse_qs(request.url.query.decode())
            # Only return the target field when the max page size is requested,
            # proving the tool pages past Accelo's default page of 10.
            if params.get("_limit") == ["100"]:
                return httpx.Response(
                    200,
                    json={
                        "meta": {"status": "ok"},
                        "response": [
                            {"id": "80", "field_name": "Contract", "field_type": "hyperlink"}
                        ],
                    },
                )
            return httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": []},
            )

        fields_route = respx.get(f"{BASE}/contracts/profiles/fields").mock(
            side_effect=_fields_responder
        )
        post_route = respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "80", "value": "https://example.com/doc"},
                },
            )
        )
        respx.get(f"{BASE}/contracts/29/profiles/values").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"field_id": "80", "value": "https://example.com/doc"}],
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

        assert fields_route.called
        sent = parse_qs(fields_route.calls[0].request.url.query.decode())
        assert sent["_limit"] == ["100"]
        assert post_route.called
        assert result.get("error") is not True
        assert result.get("status") != "field_not_found"

    @respx.mock
    @pytest.mark.asyncio
    async def test_set_profile_value_returns_structured_error(self, server_and_client):
        """Surfaces the real Accelo error instead of an opaque failure."""
        server, client = server_and_client

        _fields_route("hyperlink")
        respx.post(f"{BASE}/contracts/29/profiles/fields/80").mock(
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
