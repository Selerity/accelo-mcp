"""Accelo Payments tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register payment tools with the MCP server."""

    @server.tool()
    async def accelo_list_payments(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List payments from Accelo.

        Payments record money received against invoices. Each payment has a method,
        receipt, and currency. Use fields="payment_method(),payment_receipt(),
        payment_currency()" to expand linked objects.

        Args:
            filters: Filter dict. Keys: id, currency_id, method_id, receipt_id,
                created_by_staff_id, against_id, against_type,
                date_created_before/after,
                against (object filter, e.g. {"account_invoice": [133]}),
                order_by_asc/desc (id, amount, date_created, direction)
            fields: Additional fields, e.g. "payment_method(),payment_receipt()"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/payments", params=params)

    @server.tool()
    async def accelo_get_payment(id: int, fields: str | None = None) -> dict:
        """Get a single payment by ID.

        Args:
            id: Payment ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/payments/{id}", params=params)

    @server.tool()
    async def accelo_count_payments(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count payments matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/payments/count", params=params)
