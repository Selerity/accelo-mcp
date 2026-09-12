"""Accelo Filters tools.

Filters are saved searches on the deployment. They can be listed, listed against
a specific object type, updated (title/shared), and run to return the objects they
match. Supported object types: activities, affiliations, companies, contracts,
expenses, issues, jobs, milestones, prospects, quotes, staff, tasks.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register filter tools with the MCP server."""

    @server.tool()
    async def accelo_list_filters(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List saved filters on the deployment.

        Does not include filters created by other users that have not been shared.

        Args:
            filters: Filter dict. Keys: id, shared, staff (staff_id), object_type,
                order_by_asc/desc (id, title, shared)
            fields: Additional fields, e.g. "staff()"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/filters", params=params)

    @server.tool()
    async def accelo_list_object_filters(
        object: str,
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List saved filters for a particular object type.

        Args:
            object: Object type, e.g. "companies", "issues", "jobs" (one of:
                activities, affiliations, companies, contracts, expenses, issues,
                jobs, milestones, prospects, quotes, staff, tasks)
            filters: Filter dict. Keys: id, shared, staff (staff_id)
            fields: Additional fields
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get(f"/{object}/filters", params=params)

    @server.tool()
    async def accelo_update_filter(
        id: int,
        title: str | None = None,
        shared: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update a saved filter's title or shared flag.

        Args:
            id: Filter ID (required)
            title: New title
            shared: "yes" or "no" — whether the filter is shared on the deployment
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if shared:
            data["shared"] = shared
        if fields:
            data["_fields"] = fields
        return await client.put(f"/filters/{id}", data=data)

    @server.tool()
    async def accelo_run_filter(
        id: int,
        fields: str | None = None,
        limit: int = 10,
    ) -> dict:
        """Run a saved filter and return the objects it matches.

        The returned objects are of the filter's own object_type, with their default
        fields plus any requested via `fields`.

        Args:
            id: Filter ID (required)
            fields: Additional fields on the matched objects
            limit: Max results (this endpoint accepts only _limit, not _page)
        """
        params: dict[str, Any] = {"_limit": min(limit, 100)}
        if fields:
            params["_fields"] = fields
        return await client.get(f"/filters/{id}/run", params=params)
