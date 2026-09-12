"""Integration tests for staff tools with mocked HTTP."""

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


class TestListStaff:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_staff(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/staff").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "14", "firstname": "Matthew", "surname": "Hughes"}],
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_list_staff", {"limit": 10}))
        await client.close()

        assert result["response"][0]["surname"] == "Hughes"


class TestListStaffMemberships:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_memberships(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/staff/memberships").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "1", "staff_id": "14", "group_id": "2"},
                    ],
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_staff_memberships", {"limit": 10})
        )
        await client.close()

        assert result["response"][0]["group_id"] == "2"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_memberships_with_staff_filter(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/staff/memberships").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": []},
            )
        )

        await server.call_tool("accelo_list_staff_memberships", {"filters": {"staff_id": 14}})
        await client.close()

        assert "staff_id" in str(route.calls[0].request.url)


class TestCreateStaff:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_staff(self, server_and_client):
        server, client = server_and_client

        route = respx.post(f"{BASE}/staff").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "id": "99",
                        "username": "jdoe",
                        "firstname": "Jane",
                        "surname": "Doe",
                        "email": "jane@example.com",
                    },
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_create_staff",
                {
                    "username": "jdoe",
                    "password": "s3cret-pw",
                    "firstname": "Jane",
                    "surname": "Doe",
                    "email": "jane@example.com",
                },
            )
        )
        await client.close()

        assert result["response"]["id"] == "99"
        # Verify the required fields were sent in the POST body
        body = route.calls[0].request.content.decode()
        assert "username=jdoe" in body
        assert "firstname=Jane" in body
        assert "jane" in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_staff_with_optional_fields(self, server_and_client):
        server, client = server_and_client

        route = respx.post(f"{BASE}/staff").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "100"}},
            )
        )

        await server.call_tool(
            "accelo_create_staff",
            {
                "username": "bsmith",
                "password": "pw",
                "firstname": "Bob",
                "surname": "Smith",
                "email": "bob@example.com",
                "position": "Consultant",
                "mobile": "0400000000",
            },
        )
        await client.close()

        body = route.calls[0].request.content.decode()
        assert "position" in body
        assert "mobile" in body


class TestUpdateStaff:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_staff(self, server_and_client):
        server, client = server_and_client

        respx.put(f"{BASE}/staff/14").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "14", "position": "Lead Consultant"},
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_update_staff",
                {"id": 14, "position": "Lead Consultant"},
            )
        )
        await client.close()

        assert result["response"]["position"] == "Lead Consultant"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_staff_partial_only_sends_provided(self, server_and_client):
        server, client = server_and_client

        route = respx.put(f"{BASE}/staff/14").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "14"}},
            )
        )

        await server.call_tool("accelo_update_staff", {"id": 14, "email": "new@example.com"})
        await client.close()

        body = route.calls[0].request.content.decode()
        assert "email" in body
        # Fields not provided must not be sent
        assert "firstname" not in body
        assert "position" not in body
