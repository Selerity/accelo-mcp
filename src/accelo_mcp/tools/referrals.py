"""Accelo Referrals tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register referral tools with the MCP server."""

    @server.tool()
    async def accelo_list_referrals(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List referrals from Accelo.

        Referrals link an object to the object it was created from. For example,
        a job created from a prospect has a referral where referrer_type='prospect'
        and against_type='job'.

        Args:
            filters: Filter dict. Keys: id, against_type, against_id, referrer_type,
                referrer_id, created_by, updated_by, standing,
                date_created/updated_before/after,
                order_by_asc/desc (id, date_created, date_updated)
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/referrals", params=params)

    @server.tool()
    async def accelo_get_referral(id: int, fields: str | None = None) -> dict:
        """Get a single referral by ID.

        Args:
            id: Referral ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/referrals/{id}", params=params)

    @server.tool()
    async def accelo_count_referrals(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count referrals matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/referrals/count", params=params)
