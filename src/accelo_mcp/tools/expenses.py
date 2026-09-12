"""Accelo Expenses tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register expense tools with the MCP server."""

    @server.tool()
    async def accelo_list_expenses(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List expenses from Accelo.

        Args:
            filters: Filter dict. Keys: id, standing, expense_type, submitter, approver,
                against_type, against_id, date_incurred_before/after, order_by_asc/desc
            fields: Additional fields, e.g. "expense_type(),resource()"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/expenses", params=params)

    @server.tool()
    async def accelo_get_expense(id: int, fields: str | None = None) -> dict:
        """Get a single expense by ID.

        Args:
            id: Expense ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/expenses/{id}", params=params)

    @server.tool()
    async def accelo_count_expenses(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count expenses matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/expenses/count", params=params)

    @server.tool()
    async def accelo_create_expense(
        title: str,
        against_type: str,
        against_id: int,
        unit_cost: float,
        quantity: float,
        type_id: int,
        billable: str | None = None,
        reimbursable: str | None = None,
        date_incurred: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new expense.

        Args:
            title: Expense title (required)
            against_type: Object type (required)
            against_id: Object ID (required)
            unit_cost: Cost per unit (required)
            quantity: Quantity (required)
            type_id: Expense type ID (required)
            billable: "yes" or "no"
            reimbursable: "yes" or "no"
            date_incurred: Date incurred (unix timestamp)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "title": title,
            "against_type": against_type,
            "against_id": against_id,
            "unit_cost": unit_cost,
            "quantity": quantity,
            "type_id": type_id,
        }
        if billable:
            data["billable"] = billable
        if reimbursable:
            data["reimbursable"] = reimbursable
        if date_incurred is not None:
            data["date_incurred"] = date_incurred
        if fields:
            data["_fields"] = fields
        return await client.post("/expenses", data=data)

    @server.tool()
    async def accelo_update_expense(
        id: int,
        title: str | None = None,
        unit_cost: float | None = None,
        quantity: float | None = None,
        billable: str | None = None,
        reimbursable: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing expense.

        Args:
            id: Expense ID (required)
            title: New title
            unit_cost: New unit cost
            quantity: New quantity
            billable: "yes" or "no"
            reimbursable: "yes" or "no"
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if unit_cost is not None:
            data["unit_cost"] = unit_cost
        if quantity is not None:
            data["quantity"] = quantity
        if billable:
            data["billable"] = billable
        if reimbursable:
            data["reimbursable"] = reimbursable
        if fields:
            data["_fields"] = fields
        return await client.put(f"/expenses/{id}", data=data)

    @server.tool()
    async def accelo_delete_expense(id: int) -> dict:
        """Delete an expense.

        Args:
            id: Expense ID to delete
        """
        return await client.delete(f"/expenses/{id}")
