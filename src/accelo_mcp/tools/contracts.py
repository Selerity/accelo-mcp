"""Accelo Contracts (Retainers) tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register contract tools with the MCP server."""

    @server.tool()
    async def accelo_list_contracts(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List contracts (retainers) from Accelo.

        Contracts are always 'against' a company (against_type="company").
        Each contract has billing periods (contract_periods). To find a
        contract's company: the against_id IS the company_id.
        Use fields="company()" to expand the company inline.

        Contract periods link back via contract_id. To resolve a contract_period
        to its company: get period → contract_id → get contract → against_id.

        Args:
            filters: Filter dict. Keys: id, standing, contract_type, manager,
                billable_affiliation, status, against_type, against_id,
                date_created/started/expired_before/after, order_by_asc/desc
            fields: Additional fields, e.g. "manager(),company(),contract_type()"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/contracts", params=params)

    @server.tool()
    async def accelo_get_contract(id: int, fields: str | None = None) -> dict:
        """Get a single contract by ID.

        Args:
            id: Contract ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/contracts/{id}", params=params)

    @server.tool()
    async def accelo_count_contracts(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count contracts matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/contracts/count", params=params)
