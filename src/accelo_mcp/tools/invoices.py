"""Accelo Invoices tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register invoice tools with the MCP server."""

    @server.tool()
    async def accelo_list_invoices(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List invoices from Accelo.

        Args:
            filters: Filter dict. Keys: id, invoice_number,
                date_raised/due/modified_before/after, order_by_asc/desc
            fields: Additional fields, e.g. "affiliation(),contact(),against_type"
            search: Search over subject, invoice_number
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/invoices", params=params)

    @server.tool()
    async def accelo_get_invoice(id: int, fields: str | None = None) -> dict:
        """Get a single invoice by ID.

        Args:
            id: Invoice ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/invoices/{id}", params=params)

    @server.tool()
    async def accelo_count_invoices(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count invoices matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/invoices/count", params=params)

    @server.tool()
    async def accelo_list_invoice_line_items(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List invoice line items from Accelo (Beta).

        Line items are the individual lines on an invoice, each carrying a
        quantity, rate, tax, total, and a link to its parent invoice, ledger,
        and tax code. Traverse from an invoice via filters={"invoice_id": <id>}.

        Args:
            filters: Filter dict. Keys: id, invoice_id, ledger_id, tax_id,
                quantity, rate, total, ordering (order/range filters), plus
                order_by_asc/desc
            fields: Additional fields, e.g. "line_item_ledger(),line_item_tax()"
            search: Search over the line item description
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/invoices/line_items", params=params)

    @server.tool()
    async def accelo_get_invoice_line_item(id: int, fields: str | None = None) -> dict:
        """Get a single invoice line item by ID (Beta).

        Args:
            id: Line item ID
            fields: Additional fields to return, e.g. "line_item_ledger(),line_item_tax()"
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/invoices/line_items/{id}", params=params)

    @server.tool()
    async def accelo_count_invoice_line_items(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count invoice line items matching the given filters (Beta)."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/invoices/line_items/count", params=params)
