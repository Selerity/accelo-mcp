"""Accelo Groups tools (Beta)."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register group tools with the MCP server."""

    @server.tool()
    async def accelo_list_groups(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List staff groups from Accelo (Beta).

        Groups categorize staff for bulk assignments and access controls.
        Use filter staff_id to find groups a specific staff member belongs to.

        Args:
            filters: Filter dict. Keys: id, title, staff_id
            fields: Additional fields, e.g. "standing,parent_id"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/groups", params=params)

    @server.tool()
    async def accelo_get_group(id: int, fields: str | None = None) -> dict:
        """Get a single group by ID (Beta).

        Args:
            id: Group ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/groups/{id}", params=params)

    @server.tool()
    async def accelo_count_groups(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count groups matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/groups/count", params=params)
