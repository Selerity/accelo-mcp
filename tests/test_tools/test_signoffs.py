"""Integration tests for signoff write-path tools with mocked HTTP."""

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


class TestListSignoffs:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_signoffs(self, server_and_client):
        server, client = server_and_client
        respx.get(f"{BASE}/signoffs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "1", "subject": "Creating things", "standing": "draft"}],
                },
            )
        )
        result = parse_result(await server.call_tool("accelo_list_signoffs", {"limit": 10}))
        await client.close()
        assert result["response"][0]["standing"] == "draft"


class TestUpdateSignoff:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_signoff(self, server_and_client):
        server, client = server_and_client
        route = respx.put(f"{BASE}/signoffs/signoff/1").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "1", "body": "Updated body"}},
            )
        )
        result = parse_result(
            await server.call_tool("accelo_update_signoff", {"id": 1, "body": "Updated body"})
        )
        await client.close()
        assert result["response"]["body"] == "Updated body"
        assert "body" in route.calls[0].request.content.decode()


class TestRedraftSignoff:
    @respx.mock
    @pytest.mark.asyncio
    async def test_redraft(self, server_and_client):
        server, client = server_and_client
        route = respx.post(f"{BASE}/signoffs/1/redraft").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "1", "standing": "draft"}},
            )
        )
        result = parse_result(await server.call_tool("accelo_redraft_signoff", {"id": 1}))
        await client.close()
        assert result["response"]["standing"] == "draft"
        assert route.calls[0].request.method == "POST"


class TestSendSignoff:
    @respx.mock
    @pytest.mark.asyncio
    async def test_send(self, server_and_client):
        server, client = server_and_client
        respx.post(f"{BASE}/signoffs/1/send").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "1", "standing": "sent"}},
            )
        )
        result = parse_result(await server.call_tool("accelo_send_signoff", {"id": 1}))
        await client.close()
        assert result["response"]["standing"] == "sent"


class TestSignoffRecipients:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_recipient(self, server_and_client):
        server, client = server_and_client
        route = respx.post(f"{BASE}/signoffs/recipients").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"id": "6"}}
            )
        )
        result = parse_result(
            await server.call_tool(
                "accelo_create_signoff_recipient",
                {
                    "signoff_id": 2,
                    "recipient_id": 300,
                    "recipient_type": "affiliation",
                    "approver": True,
                },
            )
        )
        await client.close()
        assert result["response"]["id"] == "6"
        body = route.calls[0].request.content.decode()
        assert "recipient_type" in body
        assert "approver" in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_recipient_partial(self, server_and_client):
        server, client = server_and_client
        route = respx.put(f"{BASE}/signoffs/recipients/6").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"id": "6"}}
            )
        )
        await server.call_tool(
            "accelo_update_signoff_recipient", {"recipient_id": 6, "response": "approved"}
        )
        await client.close()
        body = route.calls[0].request.content.decode()
        assert "response" in body
        assert "approver" not in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_recipient(self, server_and_client):
        server, client = server_and_client
        route = respx.delete(f"{BASE}/signoffs/recipients/6").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": None})
        )
        await server.call_tool("accelo_delete_signoff_recipient", {"recipient_id": 6})
        await client.close()
        assert route.calls[0].request.method == "DELETE"


class TestUpdateSignoffAttachment:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_attachment(self, server_and_client):
        server, client = server_and_client
        route = respx.put(f"{BASE}/signoffs/attachments/1").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "1", "standing": "inactive"}},
            )
        )
        result = parse_result(
            await server.call_tool(
                "accelo_update_signoff_attachment",
                {"attachment_id": 1, "standing": "inactive"},
            )
        )
        await client.close()
        assert result["response"]["standing"] == "inactive"
        assert "standing" in route.calls[0].request.content.decode()
