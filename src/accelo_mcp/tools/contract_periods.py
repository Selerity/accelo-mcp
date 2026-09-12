"""Accelo Contract Periods tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register contract period tools with the MCP server."""

    @server.tool()
    async def accelo_list_contract_periods(
        contract_id: int,
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List contract periods for a specific contract.

        Contract periods are billing intervals within a contract (retainer). Each has
        a budget, allowance type, and rate. To find the company:
        period → contract_id → get contract → against_id (company_id).

        Args:
            contract_id: Contract ID (required) — the parent contract
            filters: Filter dict. Keys: id, standing, budget_type, allowance_type,
                rate_type, rate, service_item, duration_type, rollover, contract_budget,
                date_created/commenced/expires/closed_before/after,
                order_by_asc/desc (id, date_created, date_commenced, date_expires,
                date_closed)
            fields: Additional fields, e.g. "contract_budget(),rate()"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get(f"/contracts/{contract_id}/periods", params=params)

    @server.tool()
    async def accelo_get_contract_period(id: int, fields: str | None = None) -> dict:
        """Get a single contract period by ID.

        Args:
            id: Contract Period ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/contracts/periods/{id}", params=params)

    @server.tool()
    async def accelo_close_contract_period(id: int, fields: str | None = None) -> dict:
        """Close a contract period.

        WARNING: This replicates the actions taken when closing a period via the Web App,
        including auto-completing linked issues/tickets if the contract is configured
        for it, and triggering invoicing.

        Args:
            id: Contract Period ID to close
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if fields:
            data["_fields"] = fields
        return await client.put(f"/contracts/periods/{id}/close", data=data)

    @server.tool()
    async def accelo_reopen_contract_period(id: int, fields: str | None = None) -> dict:
        """Reopen a previously closed contract period.

        Args:
            id: Contract Period ID to reopen
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if fields:
            data["_fields"] = fields
        return await client.put(f"/contracts/periods/{id}/open", data=data)
