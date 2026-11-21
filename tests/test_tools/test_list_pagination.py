"""Pagination arguments on list tools that wrap Accelo list endpoints."""

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

BASE = "https://test.api.accelo.com/api/v0"

# (tool name, base arguments, API path the tool must call)
LIST_TOOLS = [
    (
        "accelo_list_extension_fields",
        {"object_type": "prospects"},
        "/prospects/extensions/fields",
    ),
    (
        "accelo_get_extension_values",
        {"object_type": "jobs", "object_id": 7},
        "/jobs/7/extensions/values",
    ),
    (
        "accelo_list_profile_fields",
        {"object_type": "companies"},
        "/companies/profiles/fields",
    ),
    (
        "accelo_get_profile_values",
        {"object_type": "companies", "object_id": 7},
        "/companies/7/profiles/values",
    ),
    (
        "accelo_list_progressions",
        {"object_type": "tasks", "object_id": 24},
        "/tasks/24/progressions",
    ),
    (
        "accelo_list_collections",
        {"object_type": "issues", "object_id": 9},
        "/issues/9/collections",
    ),
]
IDS = [t[0] for t in LIST_TOOLS]


@pytest.fixture
def server_and_client():
    """Create server with pre-authed client."""
    server, client = create_server()
    client._auth._token = "test-token"
    client._auth._expires_at = 9999999999.0
    return server, client


def _query(route) -> dict[str, list[str]]:
    return parse_qs(route.calls[0].request.url.query.decode())


def _ok_route(path: str):
    return respx.get(f"{BASE}{path}").mock(
        return_value=httpx.Response(200, json={"meta": {"status": "ok"}, "response": []})
    )


@pytest.mark.parametrize(("tool", "args", "path"), LIST_TOOLS, ids=IDS)
class TestListToolPagination:
    @respx.mock
    @pytest.mark.asyncio
    async def test_page_and_limit_are_forwarded(self, server_and_client, tool, args, path):
        server, client = server_and_client
        route = _ok_route(path)

        await server.call_tool(tool, {**args, "page": 3, "limit": 25})
        await client.close()

        query = _query(route)
        assert query["_page"] == ["3"]
        assert query["_limit"] == ["25"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_defaults_are_first_page_of_ten(self, server_and_client, tool, args, path):
        server, client = server_and_client
        route = _ok_route(path)

        await server.call_tool(tool, args)
        await client.close()

        query = _query(route)
        assert query["_page"] == ["0"]
        assert query["_limit"] == ["10"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_limit_is_capped_at_100(self, server_and_client, tool, args, path):
        server, client = server_and_client
        route = _ok_route(path)

        await server.call_tool(tool, {**args, "limit": 500})
        await client.close()

        assert _query(route)["_limit"] == ["100"]


class TestFieldsStillForwarded:
    @respx.mock
    @pytest.mark.asyncio
    async def test_extension_fields_keeps_fields_param_with_paging(self, server_and_client):
        server, client = server_and_client
        route = _ok_route("/prospects/extensions/fields")

        await server.call_tool(
            "accelo_list_extension_fields",
            {"object_type": "prospects", "fields": "name,field_type", "page": 1},
        )
        await client.close()

        query = _query(route)
        assert query["_fields"] == ["name,field_type"]
        assert query["_page"] == ["1"]


class TestSecondPageIsReachable:
    @respx.mock
    @pytest.mark.asyncio
    async def test_extension_fields_beyond_first_ten(self, server_and_client):
        """The report: a field past the first 10 results could not be listed."""
        server, client = server_and_client

        def respond(request: httpx.Request) -> httpx.Response:
            page = int(parse_qs(request.url.query.decode())["_page"][0])
            rows = [{"id": str(page * 10 + n)} for n in range(10 if page == 0 else 1)]
            return httpx.Response(200, json={"meta": {"status": "ok"}, "response": rows})

        respx.get(f"{BASE}/prospects/extensions/fields").mock(side_effect=respond)

        first = await server.call_tool("accelo_list_extension_fields", {"object_type": "prospects"})
        second = await server.call_tool(
            "accelo_list_extension_fields", {"object_type": "prospects", "page": 1}
        )
        await client.close()

        first_ids = [row["id"] for row in json.loads(first.content[0].text)["response"]]
        second_ids = [row["id"] for row in json.loads(second.content[0].text)["response"]]
        assert len(first_ids) == 10
        assert second_ids == ["10"]
