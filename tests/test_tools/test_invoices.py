"""Integration tests for invoice tools with mocked HTTP."""

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


class TestListInvoices:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_invoices(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/invoices").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "75", "subject": "My Test Invoice", "amount": "200.00"},
                        {"id": "76", "subject": "Second Invoice", "amount": "500.00"},
                    ],
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_list_invoices", {"limit": 10}))
        await client.close()

        assert len(result["response"]) == 2
        assert result["response"][0]["subject"] == "My Test Invoice"


class TestGetInvoice:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_invoice(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/invoices/75").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "75", "amount": "200.00", "tax": "10.00"},
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_get_invoice", {"id": 75}))
        await client.close()

        assert result["response"]["id"] == "75"
        assert result["response"]["amount"] == "200.00"


class TestCountInvoices:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_invoices(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/invoices/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "12"}},
            )
        )

        result = parse_result(await server.call_tool("accelo_count_invoices", {}))
        await client.close()

        assert result["response"]["count"] == "12"


class TestListInvoiceLineItems:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_line_items_basic(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/invoices/line_items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "1", "invoice_id": "75", "quantity": "2", "total": "220.00"},
                        {"id": "2", "invoice_id": "75", "quantity": "1", "total": "110.00"},
                    ],
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_invoice_line_items", {"limit": 10})
        )
        await client.close()

        assert len(result["response"]) == 2
        assert result["response"][0]["invoice_id"] == "75"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_line_items_with_invoice_filter(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/invoices/line_items").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": [{"id": "1"}]},
            )
        )

        await server.call_tool(
            "accelo_list_invoice_line_items",
            {"filters": {"invoice_id": 75}, "fields": "description,total"},
        )
        await client.close()

        request = route.calls[0].request
        url_str = str(request.url)
        assert "invoice_id" in url_str
        assert "description" in url_str
        assert "total" in url_str

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_line_items_with_search(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/invoices/line_items").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": []},
            )
        )

        await server.call_tool(
            "accelo_list_invoice_line_items",
            {"search": "consulting"},
        )
        await client.close()

        request = route.calls[0].request
        assert "consulting" in str(request.url)


class TestGetInvoiceLineItem:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_line_item(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/invoices/line_items/5").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "id": "5",
                        "invoice_id": "75",
                        "quantity": "3",
                        "rate": "100.00",
                        "total": "330.00",
                        "tax": "30.00",
                    },
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_get_invoice_line_item", {"id": 5}))
        await client.close()

        assert result["response"]["id"] == "5"
        assert result["response"]["total"] == "330.00"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_line_item_with_fields(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/invoices/line_items/5").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "5"}},
            )
        )

        await server.call_tool(
            "accelo_get_invoice_line_item",
            {"id": 5, "fields": "line_item_ledger(),line_item_tax()"},
        )
        await client.close()

        request = route.calls[0].request
        url_str = str(request.url)
        assert "line_item_ledger" in url_str
        assert "line_item_tax" in url_str


class TestCountInvoiceLineItems:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_line_items(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/invoices/line_items/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "87"}},
            )
        )

        result = parse_result(await server.call_tool("accelo_count_invoice_line_items", {}))
        await client.close()

        assert result["response"]["count"] == "87"

    @respx.mock
    @pytest.mark.asyncio
    async def test_count_line_items_with_filter(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/invoices/line_items/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "4"}},
            )
        )

        await server.call_tool(
            "accelo_count_invoice_line_items",
            {"filters": {"invoice_id": 75}},
        )
        await client.close()

        request = route.calls[0].request
        assert "invoice_id" in str(request.url)
        # Count must not send pagination params
        assert "_page" not in str(request.url)
        assert "_limit" not in str(request.url)
