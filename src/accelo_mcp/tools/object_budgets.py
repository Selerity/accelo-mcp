"""Accelo Object Budgets tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register object budget tools with the MCP server."""

    @server.tool()
    async def accelo_list_object_budgets(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List object budgets from Accelo.

        Object budgets track time and money spent against issues, milestones, jobs,
        and contract periods. Key fields include billable, nonbillable, logged, charged,
        service_price, material_price, and is_billable. Each budget is linked via
        against_type/against_id (e.g. against_type='milestone', against_id=15).

        Args:
            filters: Filter dict. Keys: id, against_id, against_type,
                order_by_asc/desc (id)
            fields: Additional fields, e.g. "service_price_subtotal,material_cost"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/object_budgets", params=params)

    @server.tool()
    async def accelo_get_object_budget(id: int, fields: str | None = None) -> dict:
        """Get a single object budget by ID.

        Returns financial tracking data: billable/nonbillable time, charged amounts,
        service and material costs, and remaining budget.

        Args:
            id: Object Budget ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/object_budgets/{id}", params=params)

    @server.tool()
    async def accelo_count_object_budgets(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count object budgets matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/object_budgets/count", params=params)

    @server.tool()
    async def accelo_list_object_budget_templates(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List object budget templates from Accelo.

        Budget templates define reusable budget configurations that can be applied
        to objects. They contain default values for service rates, material costs,
        and billing settings.

        Args:
            filters: Filter dict. Keys: id, order_by_asc/desc (id)
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/object_budgets/templates", params=params)

    @server.tool()
    async def accelo_list_object_budget_materials(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List materials (line items) from object budgets.

        Materials represent physical goods, licences, or other non-time cost items
        tracked against a budget. Each material has a title, quantity, unit cost,
        and billing status.

        Args:
            filters: Filter dict. Keys: id, budget_id, against_type, against_id,
                order_by_asc/desc (id)
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/object_budgets/materials", params=params)

    @server.tool()
    async def accelo_list_object_budget_services(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List services (time-based line items) from object budgets.

        Services represent billable time items tracked against a budget. Each service
        has a rate, quantity (time), and billing configuration.

        Args:
            filters: Filter dict. Keys: id, budget_id, against_type, against_id,
                order_by_asc/desc (id)
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/object_budgets/services", params=params)

    @server.tool()
    async def accelo_create_object_budget_material(
        budget_id: int,
        title: str,
        quantity: float,
        unit_cost: float,
        billable: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new material line item on an object budget.

        Args:
            budget_id: ID of the object budget to add the material to (required)
            title: Material title/description (required)
            quantity: Quantity of the material (required)
            unit_cost: Cost per unit (required)
            billable: "yes" or "no" — whether this material is billable
            fields: Additional fields to return on the created material
        """
        data: dict[str, Any] = {
            "budget_id": budget_id,
            "title": title,
            "quantity": quantity,
            "unit_cost": unit_cost,
        }
        if billable is not None:
            data["billable"] = billable
        if fields:
            data["_fields"] = fields
        return await client.post("/object_budgets/materials", data=data)

    @server.tool()
    async def accelo_update_object_budget_material(
        material_id: int,
        title: str | None = None,
        quantity: float | None = None,
        unit_cost: float | None = None,
        billable: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing material line item on an object budget.

        Args:
            material_id: ID of the material to update (required)
            title: New material title/description
            quantity: New quantity
            unit_cost: New cost per unit
            billable: "yes" or "no" — whether this material is billable
            fields: Additional fields to return on the updated material
        """
        data: dict[str, Any] = {}
        if title is not None:
            data["title"] = title
        if quantity is not None:
            data["quantity"] = quantity
        if unit_cost is not None:
            data["unit_cost"] = unit_cost
        if billable is not None:
            data["billable"] = billable
        if fields:
            data["_fields"] = fields
        return await client.put(f"/object_budgets/materials/{material_id}", data=data)
