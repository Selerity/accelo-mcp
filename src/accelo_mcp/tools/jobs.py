"""Accelo Jobs (Projects) tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register job tools with the MCP server."""

    @server.tool()
    async def accelo_list_jobs(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List jobs (projects) from Accelo.

        Jobs are always 'against' a company (against_type="company", against_id=company_id).
        Jobs contain milestones (phases) which contain tasks. To find a job's company,
        the against_id IS the company_id. Use fields="company(),manager()" to expand inline.

        Args:
            filters: Filter dict. Keys: id, standing, against_type, against_id, paused,
                job_type, manager, modified_by, status, rate,
                date_created/started/due/modified/commenced_before/after,
                order_by_asc/desc
            fields: Additional fields, e.g. "manager(),company(),job_type()"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/jobs", params=params)

    @server.tool()
    async def accelo_get_job(id: int, fields: str | None = None) -> dict:
        """Get a single job (project) by ID.

        Args:
            id: Job ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/jobs/{id}", params=params)

    @server.tool()
    async def accelo_count_jobs(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count jobs matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/jobs/count", params=params)

    @server.tool()
    async def accelo_create_job(
        title: str,
        against_type: str,
        against_id: int,
        manager_id: int,
        type_id: int,
        status_id: int | None = None,
        date_due: int | None = None,
        date_started: int | None = None,
        affiliation_id: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new job (project).

        Args:
            title: Job title (required)
            against_type: Object type (required)
            against_id: Object ID (required)
            manager_id: Staff ID for manager (required)
            type_id: Job type ID (required)
            status_id: Initial status ID
            date_due: Due date (unix timestamp)
            date_started: Start date (unix timestamp)
            affiliation_id: Affiliation ID
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "title": title,
            "against_type": against_type,
            "against_id": against_id,
            "manager_id": manager_id,
            "type_id": type_id,
        }
        if status_id is not None:
            data["status_id"] = status_id
        if date_due is not None:
            data["date_due"] = date_due
        if date_started is not None:
            data["date_started"] = date_started
        if affiliation_id is not None:
            data["affiliation_id"] = affiliation_id
        if fields:
            data["_fields"] = fields
        return await client.post("/jobs", data=data)

    @server.tool()
    async def accelo_update_job(
        id: int,
        title: str | None = None,
        manager_id: int | None = None,
        status_id: int | None = None,
        date_due: int | None = None,
        affiliation_id: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing job.

        Args:
            id: Job ID (required)
            title: New title
            manager_id: New manager staff ID
            status_id: New status ID
            date_due: New due date (unix timestamp)
            affiliation_id: New affiliation ID
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if manager_id is not None:
            data["manager_id"] = manager_id
        if status_id is not None:
            data["status_id"] = status_id
        if date_due is not None:
            data["date_due"] = date_due
        if affiliation_id is not None:
            data["affiliation_id"] = affiliation_id
        if fields:
            data["_fields"] = fields
        return await client.put(f"/jobs/{id}", data=data)

    @server.tool()
    async def accelo_delete_job(id: int) -> dict:
        """Delete a job.

        Args:
            id: Job ID to delete
        """
        return await client.delete(f"/jobs/{id}")
