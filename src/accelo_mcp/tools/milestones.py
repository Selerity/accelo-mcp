"""Accelo Milestones tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register milestone tools with the MCP server."""

    @server.tool()
    async def accelo_list_milestones(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List milestones from Accelo.

        Milestones are phases within a job. Each milestone has a job_id linking to its
        parent job. To find the company: get milestone → job_id → get job → against_id (company).
        Use fields="job()" to expand the parent job inline.

        Args:
            filters: Filter dict. Keys: id, standing, ordering, job, parent, manager,
                rate, object_budget, status,
                date_modified/created/started/commenced/due/completed_before/after,
                order_by_asc/desc
            fields: Additional fields, e.g. "description,manager(),job()"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/milestones", params=params)

    @server.tool()
    async def accelo_get_milestone(id: int, fields: str | None = None) -> dict:
        """Get a single milestone by ID.

        Args:
            id: Milestone ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/milestones/{id}", params=params)

    @server.tool()
    async def accelo_count_milestones(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count milestones matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/milestones/count", params=params)
