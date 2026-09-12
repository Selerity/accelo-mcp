"""Accelo Taxes tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register tax tools with the MCP server."""

    @server.tool()
    async def accelo_list_taxes(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List tax codes from Accelo.

        Tax codes define the tax rates applied to invoices, expenses, and materials.
        Key fields: title, rate (decimal, e.g. 0.10 for 10%), standing.

        Args:
            filters: Filter dict. Keys: id, standing,
                order_by_asc/desc (id, standing, title)
            fields: Additional fields, e.g. "rate,standing"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/taxes", params=params)

    @server.tool()
    async def accelo_get_tax(id: int, fields: str | None = None) -> dict:
        """Get a single tax code by ID.

        Args:
            id: Tax ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/taxes/{id}", params=params)

    @server.tool()
    async def accelo_count_taxes(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count tax codes matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/taxes/count", params=params)
