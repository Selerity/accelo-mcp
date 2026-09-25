"""Integration tests for activity tools with mocked HTTP."""

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


class TestListInteractions:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_interactions(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/activities/1053/interacts").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "staff": [
                            {
                                "id": "14",
                                "firstname": "Matthew",
                                "surname": "Hughes",
                                "interact": {"id": "2053", "type": "from"},
                            }
                        ],
                        "contacts": [
                            {
                                "id": "94",
                                "firstname": "Hubert",
                                "surname": "Farnsworth",
                                "interact": {"id": "2052", "type": "to"},
                            }
                        ],
                    },
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_list_interactions", {"id": 1053}))
        await client.close()

        assert result["response"]["staff"][0]["interact"]["type"] == "from"
        assert result["response"]["contacts"][0]["interact"]["type"] == "to"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_interactions_with_fields(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities/1053/interacts").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"staff": [], "contacts": []}},
            )
        )

        await server.call_tool("accelo_list_interactions", {"id": 1053, "fields": "email,mobile"})
        await client.close()

        url_str = str(route.calls[0].request.url)
        assert "email" in url_str


class TestCountInteractions:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_interactions(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/activities/1053/interacts/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "2"}},
            )
        )

        result = parse_result(await server.call_tool("accelo_count_interactions", {"id": 1053}))
        await client.close()

        assert result["response"]["count"] == "2"


class TestGetActivityTimeAllocated:
    @respx.mock
    @pytest.mark.asyncio
    async def test_time_allocated_basic(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/activities/allocations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "billable": "1660",
                        "nonbillable": "3600",
                        "charged": "21.26",
                    },
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_get_activity_time_allocated", {}))
        await client.close()

        assert result["response"]["billable"] == "1660"
        assert result["response"]["charged"] == "21.26"

    @respx.mock
    @pytest.mark.asyncio
    async def test_time_allocated_with_filters_drops_pagination(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities/allocations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {"billable": "0", "nonbillable": "0", "charged": "0.00"},
                },
            )
        )

        await server.call_tool(
            "accelo_get_activity_time_allocated",
            {"filters": {"staff": 14, "date_logged_after": 1690000000}},
        )
        await client.close()

        url_str = str(route.calls[0].request.url)
        assert "staff" in url_str
        assert "date_logged_after" in url_str
        assert "_page" not in url_str
        assert "_limit" not in url_str


class TestListActivityThreads:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_threads_basic(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/activities/threads").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": [
                        {
                            "id": 278,
                            "event_text": "replied by email",
                            "total_activities": "3",
                            "activities": [{"id": "280", "subject": "Redesign update"}],
                        }
                    ],
                },
            )
        )

        result = parse_result(await server.call_tool("accelo_list_activity_threads", {"limit": 10}))
        await client.close()

        assert result["response"][0]["event_text"] == "replied by email"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_threads_with_against_filter(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities/threads").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": []},
            )
        )

        await server.call_tool(
            "accelo_list_activity_threads",
            {"filters": {"against_type": "company", "against_id": 39}},
        )
        await client.close()

        url_str = str(route.calls[0].request.url)
        assert "against_type" in url_str
        assert "against_id" in url_str


class TestCountActivityThreads:
    @respx.mock
    @pytest.mark.asyncio
    async def test_count_threads(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities/threads/count").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"count": "17"}},
            )
        )

        result = parse_result(await server.call_tool("accelo_count_activity_threads", {}))
        await client.close()

        assert result["response"]["count"] == "17"
        url_str = str(route.calls[0].request.url)
        assert "_page" not in url_str
        assert "_limit" not in url_str


class TestListThreadActivities:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_thread_activities(self, server_and_client):
        server, client = server_and_client

        respx.get(f"{BASE}/activities/threads/278").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"status": "ok"},
                    "response": {
                        "thread": {
                            "id": "278",
                            "event_text": "replied by email",
                            "total_activities": "3",
                            "activities": [
                                {"id": "280", "subject": "Redesign update"},
                                {"id": "279", "subject": "Redesign update"},
                                {"id": "278", "subject": "Redesign update"},
                            ],
                        }
                    },
                },
            )
        )

        result = parse_result(
            await server.call_tool("accelo_list_thread_activities", {"thread_id": 278})
        )
        await client.close()

        assert result["response"]["thread"]["total_activities"] == "3"
        assert len(result["response"]["thread"]["activities"]) == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_thread_activities_with_fields(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities/threads/278").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"thread": {}}},
            )
        )

        await server.call_tool(
            "accelo_list_thread_activities",
            {"thread_id": 278, "fields": "thread,parent"},
        )
        await client.close()

        url_str = str(route.calls[0].request.url)
        assert "thread" in url_str
        assert "parent" in url_str


class TestListActivitiesSearchGuard:
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_is_rejected_without_http_call(self, server_and_client):
        """Accelo /activities ignores _search, so the tool rejects it up front."""
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities").mock(
            return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": []})
        )

        result = parse_result(
            await server.call_tool(
                "accelo_list_activities",
                {"search": "Example Order Form #1329"},
            )
        )
        await client.close()

        assert result["error"] == "unsupported_parameter"
        assert result["rejected_search"] == "Example Order Form #1329"
        # No request should have been issued to the /activities endpoint.
        assert route.call_count == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_blank_search_still_lists(self, server_and_client):
        """An empty/whitespace search is treated as absent and lists normally."""
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": [{"id": "1"}]},
            )
        )

        result = parse_result(await server.call_tool("accelo_list_activities", {"search": "   "}))
        await client.close()

        assert "error" not in result
        assert route.call_count == 1
        # _search must never be forwarded to /activities.
        assert "_search" not in str(route.calls[0].request.url)

    @respx.mock
    @pytest.mark.asyncio
    async def test_normal_list_has_no_search_param(self, server_and_client):
        server, client = server_and_client

        route = respx.get(f"{BASE}/activities").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": [{"id": "1"}]},
            )
        )

        await server.call_tool(
            "accelo_list_activities",
            {"filters": {"against_type": "prospect", "against_id": 1313}},
        )
        await client.close()

        assert "_search" not in str(route.calls[0].request.url)


class TestCreateActivity:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_minimal(self, server_and_client):
        server, client = server_and_client

        route = respx.post(f"{BASE}/activities").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "2001"}},
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_create_activity",
                {"subject": "Kickoff note", "against_type": "company", "against_id": 39},
            )
        )
        await client.close()

        assert result["response"]["id"] == "2001"
        body = route.calls[0].request.content.decode()
        assert "subject=Kickoff" in body
        assert "against_type=company" in body
        assert "against_id=39" in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_logs_time_against_task(self, server_and_client):
        """Time logging against a task: parent as against, task id + visibility=all."""
        server, client = server_and_client

        route = respx.post(f"{BASE}/activities").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "2002"}},
            )
        )

        await server.call_tool(
            "accelo_create_activity",
            {
                "subject": "Worked on SEO audit",
                "against_type": "milestone",
                "against_id": 15,
                "task": 24,
                "visibility": "all",
                "date_started": 1690000000,
                "billable": 3600,
            },
        )
        await client.close()

        body = route.calls[0].request.content.decode()
        # The create endpoint expects task_id, not task.
        assert "task_id=24" in body
        assert "task=24" not in body
        assert "visibility=all" in body
        assert "date_started=1690000000" in body
        assert "billable=3600" in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_omits_unset_new_fields(self, server_and_client):
        server, client = server_and_client

        route = respx.post(f"{BASE}/activities").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "2003"}},
            )
        )

        await server.call_tool(
            "accelo_create_activity",
            {"subject": "Plain note", "against_type": "staff", "against_id": 14},
        )
        await client.close()

        body = route.calls[0].request.content.decode()
        assert "task_id" not in body
        assert "visibility" not in body
        assert "date_started" not in body


class TestUpdateActivity:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_class_and_date_started(self, server_and_client):
        server, client = server_and_client

        route = respx.put(f"{BASE}/activities/1002").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "1002"}},
            )
        )

        result = parse_result(
            await server.call_tool(
                "accelo_update_activity",
                {"id": 1002, "class_id": 5, "date_started": 1690000000},
            )
        )
        await client.close()

        assert result["response"]["id"] == "1002"
        body = route.calls[0].request.content.decode()
        assert "class_id=5" in body
        assert "date_started=1690000000" in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_omits_unset_new_fields(self, server_and_client):
        server, client = server_and_client

        route = respx.put(f"{BASE}/activities/1002").mock(
            return_value=httpx.Response(
                200,
                json={"meta": {"status": "ok"}, "response": {"id": "1002"}},
            )
        )

        await server.call_tool(
            "accelo_update_activity",
            {"id": 1002, "subject": "Renamed"},
        )
        await client.close()

        body = route.calls[0].request.content.decode()
        assert "subject=Renamed" in body
        assert "class_id" not in body
        assert "date_started" not in body
