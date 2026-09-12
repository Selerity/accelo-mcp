"""Integration tests for the issue #17 grab-bag tools with mocked HTTP."""

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


class TestFilters:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_filters(self, server_and_client):
        server, client = server_and_client
        respx.get(f"{BASE}/filters").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "1", "title": "My filter", "object_type": "companies"}],
                },
            )
        )
        result = parse_result(await server.call_tool("accelo_list_filters", {}))
        await client.close()
        assert result["response"][0]["object_type"] == "companies"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_object_filters(self, server_and_client):
        server, client = server_and_client
        route = respx.get(f"{BASE}/companies/filters").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": []})
        )
        await server.call_tool("accelo_list_object_filters", {"object": "companies"})
        await client.close()
        assert "/companies/filters" in str(route.calls[0].request.url)

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_filter(self, server_and_client):
        server, client = server_and_client
        route = respx.put(f"{BASE}/filters/1").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"id": "1", "shared": "yes"}}
            )
        )
        result = parse_result(
            await server.call_tool("accelo_update_filter", {"id": 1, "shared": "yes"})
        )
        await client.close()
        assert result["response"]["shared"] == "yes"
        assert "shared" in route.calls[0].request.content.decode()

    @respx.mock
    @pytest.mark.asyncio
    async def test_run_filter(self, server_and_client):
        server, client = server_and_client
        route = respx.get(f"{BASE}/filters/1/run").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": [{"id": "39"}]}
            )
        )
        result = parse_result(await server.call_tool("accelo_run_filter", {"id": 1}))
        await client.close()
        assert result["response"][0]["id"] == "39"
        assert "_limit" in str(route.calls[0].request.url)


class TestCompanyManagers:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_managers(self, server_and_client):
        server, client = server_and_client
        respx.get(f"{BASE}/companies/39/managers").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": [{"id": "14", "firstname": "Matt"}]},
            )
        )
        result = parse_result(
            await server.call_tool("accelo_list_company_managers", {"company_id": 39})
        )
        await client.close()
        assert result["response"][0]["firstname"] == "Matt"

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_manager(self, server_and_client):
        server, client = server_and_client
        route = respx.post(f"{BASE}/companies/39/managers/add").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": []})
        )
        await server.call_tool("accelo_add_company_manager", {"company_id": 39, "manager_id": 14})
        await client.close()
        assert "manager_id" in route.calls[0].request.content.decode()

    @respx.mock
    @pytest.mark.asyncio
    async def test_remove_manager_uses_method_override(self, server_and_client):
        server, client = server_and_client
        route = respx.post(f"{BASE}/companies/39/managers/delete").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": []})
        )
        await server.call_tool(
            "accelo_remove_company_manager", {"company_id": 39, "relationship_id": 23}
        )
        await client.close()
        body = route.calls[0].request.content.decode()
        assert "relationship_id" in body
        assert "_method" in body


class TestDeactivateContact:
    @respx.mock
    @pytest.mark.asyncio
    async def test_deactivate_contact(self, server_and_client):
        server, client = server_and_client
        route = respx.delete(f"{BASE}/contacts/98").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": None})
        )
        result = parse_result(await server.call_tool("accelo_deactivate_contact", {"id": 98}))
        await client.close()
        assert result["meta"]["status"] == "ok"
        assert route.calls[0].request.method == "DELETE"


class TestAssetLinks:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_asset_links(self, server_and_client):
        server, client = server_and_client
        respx.get(f"{BASE}/assets/links").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": [{"id": "1"}]}
            )
        )
        result = parse_result(await server.call_tool("accelo_list_asset_links", {}))
        await client.close()
        assert result["response"][0]["id"] == "1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_asset_link(self, server_and_client):
        server, client = server_and_client
        route = respx.post(f"{BASE}/assets/2/links").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"id": "5"}}
            )
        )
        result = parse_result(
            await server.call_tool(
                "accelo_create_asset_link",
                {"asset_id": 2, "linked_object_id": 39, "linked_object_type": "job"},
            )
        )
        await client.close()
        assert result["response"]["id"] == "5"
        body = route.calls[0].request.content.decode()
        assert "linked_object_id" in body
        assert "linked_object_type" in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_asset_link(self, server_and_client):
        server, client = server_and_client
        route = respx.delete(f"{BASE}/assets/links/5").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": None})
        )
        await server.call_tool("accelo_delete_asset_link", {"link_id": 5})
        await client.close()
        assert route.calls[0].request.method == "DELETE"


class TestConvertTimeExternal:
    @respx.mock
    @pytest.mark.asyncio
    async def test_convert(self, server_and_client):
        server, client = server_and_client
        route = respx.post(f"{BASE}/time/externals/2/convert_to_meeting").mock(
            return_value=httpx.Response(
                200, json={"meta": {"status": "ok"}, "response": {"id": "1053"}}
            )
        )
        result = parse_result(
            await server.call_tool(
                "accelo_convert_time_external_to_activity",
                {"id": 2, "engagement_table": "company", "engagement_id": 39},
            )
        )
        await client.close()
        assert result["response"]["id"] == "1053"
        body = route.calls[0].request.content.decode()
        assert "engagement_table" in body
        assert "engagement_id" in body


class TestTaskProgressions:
    @respx.mock
    @pytest.mark.asyncio
    async def test_progress_to_start(self, server_and_client):
        server, client = server_and_client
        route = respx.post(f"{BASE}/tasks/24/progressions/start").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "24", "standing": "started"}},
            )
        )
        result = parse_result(await server.call_tool("accelo_progress_task_to_start", {"id": 24}))
        await client.close()
        assert result["response"]["standing"] == "started"
        assert route.calls[0].request.method == "POST"

    @respx.mock
    @pytest.mark.asyncio
    async def test_progress_to_done(self, server_and_client):
        server, client = server_and_client
        respx.post(f"{BASE}/tasks/24/progressions/done").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "24", "standing": "complete"}},
            )
        )
        result = parse_result(await server.call_tool("accelo_progress_task_to_done", {"id": 24}))
        await client.close()
        assert result["response"]["standing"] == "complete"


class TestRequestThreads:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_request_threads(self, server_and_client):
        server, client = server_and_client
        route = respx.get(f"{BASE}/requests/threads").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [{"id": "31", "title": "Urgent support request"}],
                },
            )
        )
        result = parse_result(
            await server.call_tool(
                "accelo_list_request_threads", {"filters": {"standing": "pending"}}
            )
        )
        await client.close()
        assert result["response"][0]["id"] == "31"
        assert "standing" in str(route.calls[0].request.url)
