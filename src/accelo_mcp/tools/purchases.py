"""Accelo Purchases tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register purchase tools with the MCP server."""

    @server.tool()
    async def accelo_list_purchases(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List purchases from Accelo.

        Purchases track costs incurred when completing jobs, issues, or contracts.
        Key fields: title, amount, tax, total, date_purchased, owner_id, creator_id,
        affiliation_id.

        Args:
            filters: Filter dict. Keys: id, owner_id, creator_id, affiliation_id,
                date_purchased_before/after,
                order_by_asc/desc (id, amount, tax, total)
            fields: Additional fields, e.g. "amount,tax,total"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/purchases", params=params)

    @server.tool()
    async def accelo_get_purchase(id: int, fields: str | None = None) -> dict:
        """Get a single purchase by ID.

        Args:
            id: Purchase ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/purchases/{id}", params=params)

    @server.tool()
    async def accelo_count_purchases(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count purchases matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/purchases/count", params=params)
