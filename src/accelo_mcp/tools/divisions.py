"""Accelo Divisions tools (Beta)."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register division tools with the MCP server."""

    @server.tool()
    async def accelo_list_divisions(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List divisions from Accelo (Beta).

        Divisions allow managing contacts, companies, and staff under different
        details, rates, or identities.

        Args:
            filters: Filter dict. Keys: id, title, standing,
                order_by_asc/desc (id, title, standing, ordering)
            fields: Additional fields, e.g. "standing,ordering"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/divisions", params=params)

    @server.tool()
    async def accelo_get_division(id: int, fields: str | None = None) -> dict:
        """Get a single division by ID (Beta).

        Args:
            id: Division ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/divisions/{id}", params=params)

    @server.tool()
    async def accelo_count_divisions(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count divisions matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/divisions/count", params=params)
