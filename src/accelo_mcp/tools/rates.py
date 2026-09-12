"""Accelo Rates tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register rate tools with the MCP server."""

    @server.tool()
    async def accelo_list_rates(
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List rates from Accelo.

        Rates define the hourly rate charged for billable work. They are referenced
        by jobs, milestones, tasks, contracts, and staff. Key fields: title, charged
        (hourly rate as decimal), standing, object (comma-separated list of object
        types the rate applies to).

        Args:
            fields: Additional fields, e.g. "charged,object,standing"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(fields=fields, page=page, limit=limit)
        return await client.get("/rates", params=params)

    @server.tool()
    async def accelo_get_rate(id: int, fields: str | None = None) -> dict:
        """Get a single rate by ID.

        Args:
            id: Rate ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/rates/{id}", params=params)

    @server.tool()
    async def accelo_count_rates() -> dict:
        """Count all rates on the deployment."""
        return await client.get("/rates/count")
