"""Integration tests for object budget tools with mocked HTTP."""

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


class TestListObjectBudgets:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_object_budgets(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/object_budgets").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "1", "against_type": "job", "against_id": "10"},
                        {"id": "2", "against_type": "issue", "against_id": "20"},
                    ],
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_list_object_budgets", {"limit": 10}))
        await client.close()

        assert len(result["response"]) == 2
        assert result["response"][0]["against_type"] == "job"


class TestGetObjectBudget:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_object_budget(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/object_budgets/5").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "5", "billable": "3600", "nonbillable": "1800"},
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_get_object_budget", {"id": 5}))
        await client.close()

        assert result["response"]["id"] == "5"
        assert result["response"]["billable"] == "3600"


class TestCountObjectBudgets:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_object_budgets(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/object_budgets/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "42"}},
            )
        )

        result = parse_result(await server.call_tool("accelo_count_object_budgets", {}))
        await client.close()

        assert result["response"]["count"] == "42"


class TestListObjectBudgetTemplates:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_templates_basic(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/object_budgets/templates").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "1", "title": "Standard Project Budget"},
                        {"id": "2", "title": "Support Retainer"},
                    ],
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_object_budget_templates", {"limit": 10})
        )
        await client.close()

        assert len(result["response"]) == 2
        assert result["response"][0]["title"] == "Standard Project Budget"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_templates_with_filters(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/object_budgets/templates").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": [{"id": "1"}]},
            )
        )

        await server.call_tool(
            "accelo_list_object_budget_templates",
            {"filters": {"id": 1}, "fields": "title,standing"},
        )
        await client.close()

        request = route.calls[0].request
        url_str = str(request.url)
        assert "title" in url_str
        assert "standing" in url_str


class TestListObjectBudgetMaterials:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_materials_basic(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/object_budgets/materials").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "10", "title": "Licence", "quantity": "5", "unit_cost": "100.00"},
                        {"id": "11", "title": "Hardware", "quantity": "2", "unit_cost": "500.00"},
                    ],
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_object_budget_materials", {"limit": 10})
        )
        await client.close()

        assert len(result["response"]) == 2
        assert result["response"][0]["title"] == "Licence"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_materials_with_budget_filter(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/object_budgets/materials").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": []},
            )
        )

        await server.call_tool(
            "accelo_list_object_budget_materials",
            {"filters": {"budget_id": 5}},
        )
        await client.close()

        request = route.calls[0].request
        url_str = str(request.url)
        assert "budget_id" in url_str


class TestListObjectBudgetServices:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_services_basic(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/object_budgets/services").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {"id": "20", "title": "Development", "rate": "150.00"},
                        {"id": "21", "title": "Consulting", "rate": "200.00"},
                    ],
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_object_budget_services", {"limit": 10})
        )
        await client.close()

        assert len(result["response"]) == 2
        assert result["response"][1]["title"] == "Consulting"


class TestCreateObjectBudgetMaterial:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_material(self, server_and_client):
        server, client = server_and_client

        route = respx.post(f"{BASE}/object_budgets/materials").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "id": "50",
                        "title": "SSL Certificate",
                        "quantity": "1",
                        "unit_cost": "299.00",
                        "budget_id": "5",
                    },
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_create_object_budget_material",
                {
                    "budget_id": 5,
                    "title": "SSL Certificate",
                    "quantity": 1.0,
                    "unit_cost": 299.00,
                },
            )
        )
        await client.close()

        assert result["response"]["id"] == "50"
        assert result["response"]["title"] == "SSL Certificate"

        # Verify POST body
        request = route.calls[0].request
        body = request.content.decode()
        assert "budget_id" in body
        assert "SSL+Certificate" in body or "SSL%20Certificate" in body or "SSL Certificate" in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_material_with_billable(self, server_and_client):
        server, client = server_and_client

        route = respx.post(f"{BASE}/object_budgets/materials").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "51", "billable": "yes"},
                },
            )
        )

        await server.call_tool(
            "accelo_create_object_budget_material",
            {
                "budget_id": 5,
                "title": "Hosting",
                "quantity": 12.0,
                "unit_cost": 50.00,
                "billable": "yes",
            },
        )
        await client.close()

        request = route.calls[0].request
        body = request.content.decode()
        assert "billable" in body


class TestUpdateObjectBudgetMaterial:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_material(self, server_and_client):
        server, client = server_and_client

        respx.put(f"{BASE}/object_budgets/materials/50").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "id": "50",
                        "title": "Updated Certificate",
                        "unit_cost": "399.00",
                    },
                },
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_update_object_budget_material",
                {
                    "material_id": 50,
                    "title": "Updated Certificate",
                    "unit_cost": 399.00,
                },
            )
        )
        await client.close()

        assert result["response"]["title"] == "Updated Certificate"
        assert result["response"]["unit_cost"] == "399.00"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_material_partial(self, server_and_client):
        server, client = server_and_client

        route = respx.put(f"{BASE}/object_budgets/materials/50").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"id": "50", "quantity": "10"},
                },
            )
        )

        await server.call_tool(
            "accelo_update_object_budget_material",
            {"material_id": 50, "quantity": 10.0},
        )
        await client.close()

        # Verify only quantity was sent
        request = route.calls[0].request
        body = request.content.decode()
        assert "quantity" in body
        assert "title" not in body
        assert "unit_cost" not in body
