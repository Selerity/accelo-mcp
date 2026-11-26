"""The has_more flag on paged list tools (one extra row is fetched and trimmed)."""

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
PAGED_TOOLS = [
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
]
IDS = [t[0] for t in PAGED_TOOLS]


@pytest.fixture
def server_and_client():
    """Create server with pre-authed client."""
    server, client = create_server()
    client._auth._token = "test-token"
    client._auth._expires_at = 9999999999.0
    return server, client


def _rows(n: int) -> list[dict]:
    return [{"id": str(i)} for i in range(n)]


def _mock_total(path: str, total: int):
    """Mock a list endpoint holding ``total`` rows that honours _page and _limit."""

    def respond(request: httpx.Request) -> httpx.Response:
        query = parse_qs(request.url.query.decode())
        limit = int(query["_limit"][0])
        if "_offset" in query:
            start = int(query["_offset"][0])
        else:
            start = int(query["_page"][0]) * limit
        rows = _rows(total)[start : start + limit]
        return httpx.Response(
            200, json={"meta": {"status": "ok", "message": "Everything is ok"}, "response": rows}
        )

    return respx.get(f"{BASE}{path}").mock(side_effect=respond)


async def _call(server, tool: str, args: dict) -> dict:
    result = await server.call_tool(tool, args)
    return json.loads(result.content[0].text)


@pytest.mark.parametrize(("tool", "args", "path"), PAGED_TOOLS, ids=IDS)
class TestHasMore:
    @respx.mock
    @pytest.mark.asyncio
    async def test_full_page_with_more_rows_after_it(self, server_and_client, tool, args, path):
        server, client = server_and_client
        route = _mock_total(path, 25)

        out = await _call(server, tool, {**args, "limit": 10})
        await client.close()

        assert out["has_more"] is True
        assert [r["id"] for r in out["response"]] == [str(i) for i in range(10)]
        query = parse_qs(route.calls[0].request.url.query.decode())
        assert query["_limit"] == ["11"]
        assert query["_offset"] == ["0"]
        assert "_page" not in query
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_partial_last_page(self, server_and_client, tool, args, path):
        server, client = server_and_client
        _mock_total(path, 25)

        out = await _call(server, tool, {**args, "page": 2, "limit": 10})
        await client.close()

        assert out["has_more"] is False
        assert len(out["response"]) == 5

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_page_past_the_end(self, server_and_client, tool, args, path):
        server, client = server_and_client
        _mock_total(path, 25)

        out = await _call(server, tool, {**args, "page": 9, "limit": 10})
        await client.close()

        assert out["has_more"] is False
        assert out["response"] == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_total_is_an_exact_multiple_of_limit(self, server_and_client, tool, args, path):
        """A full last page must not be reported as having a next page."""
        server, client = server_and_client
        _mock_total(path, 20)

        first = await _call(server, tool, {**args, "page": 0, "limit": 10})
        last = await _call(server, tool, {**args, "page": 1, "limit": 10})
        await client.close()

        assert first["has_more"] is True
        assert len(last["response"]) == 10
        assert last["has_more"] is False


class TestPagesDoNotOverlap:
    @respx.mock
    @pytest.mark.asyncio
    async def test_walking_every_page_returns_each_row_once(self, server_and_client):
        """Fetching limit + 1 rows must not shift where the next page starts."""
        server, client = server_and_client
        _mock_total("/prospects/extensions/fields", 23)

        seen: list[str] = []
        page = 0
        while True:
            out = await _call(
                server,
                "accelo_list_extension_fields",
                {"object_type": "prospects", "page": page, "limit": 5},
            )
            seen.extend(r["id"] for r in out["response"])
            if not out["has_more"]:
                break
            page += 1
        await client.close()

        assert seen == [str(i) for i in range(23)]
        assert page == 4


class TestFullSizePage:
    """Accelo caps _limit at 100, so a 101st row cannot be requested."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_limit_100_sends_100_and_flags_a_full_page(self, server_and_client):
        server, client = server_and_client
        route = _mock_total("/prospects/extensions/fields", 250)

        out = await _call(
            server, "accelo_list_extension_fields", {"object_type": "prospects", "limit": 100}
        )
        await client.close()

        assert parse_qs(route.calls[0].request.url.query.decode())["_limit"] == ["100"]
        assert len(out["response"]) == 100
        assert out["has_more"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_limit_above_cap_behaves_like_100(self, server_and_client):
        server, client = server_and_client
        route = _mock_total("/prospects/extensions/fields", 40)

        out = await _call(
            server, "accelo_list_extension_fields", {"object_type": "prospects", "limit": 500}
        )
        await client.close()

        assert parse_qs(route.calls[0].request.url.query.decode())["_limit"] == ["100"]
        assert len(out["response"]) == 40
        assert out["has_more"] is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_limit_99_still_probes(self, server_and_client):
        server, client = server_and_client
        route = _mock_total("/prospects/extensions/fields", 150)

        out = await _call(
            server, "accelo_list_extension_fields", {"object_type": "prospects", "limit": 99}
        )
        await client.close()

        assert parse_qs(route.calls[0].request.url.query.decode())["_limit"] == ["100"]
        assert len(out["response"]) == 99
        assert out["has_more"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_limit_100_later_page_uses_page_and_no_offset(self, server_and_client):
        server, client = server_and_client
        route = _mock_total("/prospects/extensions/fields", 250)

        out = await _call(
            server,
            "accelo_list_extension_fields",
            {"object_type": "prospects", "page": 1, "limit": 100},
        )
        await client.close()

        query = parse_qs(route.calls[0].request.url.query.decode())
        assert query["_page"] == ["1"]
        assert query["_limit"] == ["100"]
        assert "_offset" not in query
        assert out["response"][0]["id"] == "100"

    @respx.mock
    @pytest.mark.asyncio
    async def test_exactly_100_rows_at_limit_100_is_may_have_more(self, server_and_client):
        """The 100-row case cannot be probed: page 0 says true, page 1 is empty."""
        server, client = server_and_client
        _mock_total("/prospects/extensions/fields", 100)
        args = {"object_type": "prospects", "limit": 100}

        first = await _call(server, "accelo_list_extension_fields", {**args, "page": 0})
        second = await _call(server, "accelo_list_extension_fields", {**args, "page": 1})
        await client.close()

        assert len(first["response"]) == 100
        assert first["has_more"] is True
        assert second["response"] == []
        assert second["has_more"] is False


class TestOutOfRangeArguments:
    """limit below 1 and a negative page are clamped before the flag is computed."""

    @respx.mock
    @pytest.mark.asyncio
    @pytest.mark.parametrize("limit", [0, -1, -5])
    async def test_limit_below_one_is_treated_as_one(self, server_and_client, limit):
        server, client = server_and_client
        route = _mock_total("/prospects/extensions/fields", 25)

        out = await _call(
            server, "accelo_list_extension_fields", {"object_type": "prospects", "limit": limit}
        )
        await client.close()

        query = parse_qs(route.calls[0].request.url.query.decode())
        assert query["_limit"] == ["2"]
        assert query["_offset"] == ["0"]
        assert [r["id"] for r in out["response"]] == ["0"]
        assert out["has_more"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_limit_below_one_never_reports_more_on_an_empty_page(self, server_and_client):
        server, client = server_and_client
        _mock_total("/prospects/extensions/fields", 0)

        out = await _call(
            server, "accelo_list_extension_fields", {"object_type": "prospects", "limit": 0}
        )
        await client.close()

        assert out["response"] == []
        assert out["has_more"] is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_negative_page_is_treated_as_first_page(self, server_and_client):
        server, client = server_and_client
        route = _mock_total("/prospects/extensions/fields", 25)

        out = await _call(
            server,
            "accelo_list_extension_fields",
            {"object_type": "prospects", "page": -1, "limit": 10},
        )
        await client.close()

        query = parse_qs(route.calls[0].request.url.query.decode())
        assert query["_limit"] == ["11"]
        assert query["_offset"] == ["0"]
        assert [r["id"] for r in out["response"]] == [str(i) for i in range(10)]
        assert out["has_more"] is True


class TestResponseShape:
    @respx.mock
    @pytest.mark.asyncio
    async def test_meta_is_kept_and_has_more_is_added_beside_it(self, server_and_client):
        server, client = server_and_client
        _mock_total("/prospects/extensions/fields", 3)

        out = await _call(server, "accelo_list_extension_fields", {"object_type": "prospects"})
        await client.close()

        assert out["meta"] == {"status": "ok", "message": "Everything is ok"}
        assert set(out) == {"meta", "response", "has_more"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_collections_is_not_probed_and_is_returned_unchanged(self, server_and_client):
        """Collections may return an object of arrays, so it asks for exactly ``limit`` rows."""
        server, client = server_and_client
        body = {"meta": {"status": "ok"}, "response": {"collections": [{"id": "1"}]}}
        route = respx.get(f"{BASE}/issues/9/collections").mock(
            return_value=httpx.Response(200, json=body)
        )

        out = await _call(
            server,
            "accelo_list_collections",
            {"object_type": "issues", "object_id": 9, "limit": 10},
        )
        await client.close()

        query = parse_qs(route.calls[0].request.url.query.decode())
        assert query["_limit"] == ["10"]
        assert query["_page"] == ["0"]
        assert "_offset" not in query
        assert out == body

    @respx.mock
    @pytest.mark.asyncio
    async def test_fields_still_forwarded(self, server_and_client):
        server, client = server_and_client
        route = _mock_total("/prospects/extensions/fields", 3)

        await _call(
            server,
            "accelo_list_extension_fields",
            {"object_type": "prospects", "fields": "name,field_type"},
        )
        await client.close()

        query = parse_qs(route.calls[0].request.url.query.decode())
        assert query["_fields"] == ["name,field_type"]
