"""Accelo Tags tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register tag tools with the MCP server."""

    @server.tool()
    async def accelo_list_tags(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List tags from Accelo.

        Tags are keywords applied to activities, jobs, and other objects to aid
        categorisation and search. Use the 'against' object filter to find tags
        on a specific object.

        Args:
            filters: Filter dict. Keys: id, name,
                against (object filter, e.g. {"job": [2]}),
                order_by_asc/desc (id, name)
            search: Search over name
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, search=search, page=page, limit=limit)
        return await client.get("/tags", params=params)

    @server.tool()
    async def accelo_count_tags(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count tags matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/tags/count", params=params)

    @server.tool()
    async def accelo_create_tag(name: str, fields: str | None = None) -> dict:
        """Create a new tag.

        Args:
            name: Tag name (required)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {"name": name}
        if fields:
            data["_fields"] = fields
        return await client.post("/tags", data=data)
