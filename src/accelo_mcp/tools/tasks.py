"""Accelo Tasks tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register task tools with the MCP server."""

    @server.tool()
    async def accelo_list_tasks(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List tasks from Accelo.

        Tasks are 'against' a job, milestone, or issue. To find the company:
        - against_type="job": get job → against_id (company)
        - against_type="milestone": get milestone → job_id → job → company
        - against_type="issue": get issue → resolve to company (see issues)
        Use child_of_job filter to find all tasks under a job (including via milestones).

        Args:
            filters: Filter dict. Keys: id, assignee, manager, task_status, standing,
                against_type, against_id, custom_id, child_of_job, rate_id,
                date_created/started/due/completed/modified_before/after,
                order_by_asc/desc
            fields: Additional fields, e.g. "description,assignee(),manager()"
            search: Search over description, title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/tasks", params=params)

    @server.tool()
    async def accelo_get_task(id: int, fields: str | None = None) -> dict:
        """Get a single task by ID.

        Args:
            id: Task ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/tasks/{id}", params=params)

    @server.tool()
    async def accelo_count_tasks(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count tasks matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/tasks/count", params=params)

    @server.tool()
    async def accelo_create_task(
        title: str,
        against_type: str,
        against_id: int,
        date_started: int,
        description: str | None = None,
        assignee_id: int | None = None,
        manager_id: int | None = None,
        date_due: int | None = None,
        priority_id: int | None = None,
        status_id: int | None = None,
        remaining: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new task.

        Args:
            title: Task title (required)
            against_type: Object type (required) — e.g. job, milestone, issue
            against_id: Object ID (required)
            date_started: Start date as unix timestamp (required)
            description: Task description
            assignee_id: Staff ID to assign
            manager_id: Staff ID for manager
            date_due: Due date (unix timestamp)
            priority_id: Priority ID
            status_id: Initial status ID
            remaining: Budgeted time remaining in seconds
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "title": title,
            "against_type": against_type,
            "against_id": against_id,
            "date_started": date_started,
        }
        if description:
            data["description"] = description
        if assignee_id is not None:
            data["assignee_id"] = assignee_id
        if manager_id is not None:
            data["manager_id"] = manager_id
        if date_due is not None:
            data["date_due"] = date_due
        if priority_id is not None:
            data["priority_id"] = priority_id
        if status_id is not None:
            data["status_id"] = status_id
        if remaining is not None:
            data["remaining"] = remaining
        if fields:
            data["_fields"] = fields
        return await client.post("/tasks", data=data)

    @server.tool()
    async def accelo_update_task(
        id: int,
        title: str | None = None,
        description: str | None = None,
        assignee_id: int | None = None,
        manager_id: int | None = None,
        date_due: int | None = None,
        priority_id: int | None = None,
        remaining: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing task.

        Args:
            id: Task ID (required)
            title: New title
            description: New description
            assignee_id: New assignee staff ID
            manager_id: New manager staff ID
            date_due: New due date (unix timestamp)
            priority_id: New priority ID
            remaining: New remaining time in seconds
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if assignee_id is not None:
            data["assignee_id"] = assignee_id
        if manager_id is not None:
            data["manager_id"] = manager_id
        if date_due is not None:
            data["date_due"] = date_due
        if priority_id is not None:
            data["priority_id"] = priority_id
        if remaining is not None:
            data["remaining"] = remaining
        if fields:
            data["_fields"] = fields
        return await client.put(f"/tasks/{id}", data=data)

    @server.tool()
    async def accelo_progress_task_to_start(id: int) -> dict:
        """Auto-progress a task's status to "start" (mark it started).

        Args:
            id: Task ID
        """
        return await client.post(f"/tasks/{id}/progressions/start")

    @server.tool()
    async def accelo_progress_task_to_done(id: int) -> dict:
        """Auto-progress a task's status to "done" (mark it complete).

        Args:
            id: Task ID
        """
        return await client.post(f"/tasks/{id}/progressions/done")
