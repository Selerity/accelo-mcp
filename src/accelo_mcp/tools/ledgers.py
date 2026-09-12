"""Accelo Ledgers tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register ledger tools with the MCP server."""

    @server.tool()
    async def accelo_list_ledgers(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List account ledgers from Accelo.

        Ledgers are accounting codes used for invoicing and financial reporting.
        They may sync with external systems (Xero, QuickBooks). Key fields: title,
        code, standing, parent_id, comment.

        Args:
            filters: Filter dict. Keys: id, code, parent_id, standing,
                order_by_asc/desc (id, code, parent_id, standing, title)
            fields: Additional fields, e.g. "code,comment"
            search: Search over title, code
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/ledgers", params=params)

    @server.tool()
    async def accelo_get_ledger(id: int, fields: str | None = None) -> dict:
        """Get a single ledger by ID.

        Args:
            id: Ledger ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/ledgers/{id}", params=params)

    @server.tool()
    async def accelo_count_ledgers(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count ledgers matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/ledgers/count", params=params)
