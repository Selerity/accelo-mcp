"""Accelo Issues (Tickets) tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register issue tools with the MCP server."""

    @server.tool()
    async def accelo_list_issues(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List issues (tickets) from Accelo.

        Issues are 'against' a company or a job. To find the company:
        - If against_type="company": against_id IS the company_id
        - If against_type="job": get job → against_id (company_id)
        Issues have an assignee (staff), affiliation (client contact), class, and priority.

        Args:
            filters: Filter dict. Keys: id, standing, custom_id, against_type, against_id,
                status, issue_type, affiliation, class, issue_priority, assignee,
                date_created/started/due/modified/closed_before/after,
                order_by_asc/desc
            fields: Additional fields, e.g. "description,resolution_detail,assignee()"
            search: Search over subject
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/issues", params=params)

    @server.tool()
    async def accelo_get_issue(id: int, fields: str | None = None) -> dict:
        """Get a single issue (ticket) by ID.

        Args:
            id: Issue ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/issues/{id}", params=params)

    @server.tool()
    async def accelo_count_issues(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count issues matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/issues/count", params=params)

    @server.tool()
    async def accelo_create_issue(
        title: str,
        type_id: int,
        against_type: str,
        against_id: int,
        description: str | None = None,
        status_id: int | None = None,
        class_id: int | None = None,
        assignee: int | None = None,
        priority_id: int | None = None,
        affiliation_id: int | None = None,
        date_started: int | None = None,
        date_due: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new issue (ticket).

        Args:
            title: Issue title (required)
            type_id: Issue type ID (required)
            against_type: Object type (required) — e.g. company, job
            against_id: Object ID (required)
            description: Issue description
            status_id: Initial status ID
            class_id: Issue class ID
            assignee: Staff ID to assign
            priority_id: Priority ID
            affiliation_id: Affiliation ID
            date_started: Start date (unix timestamp)
            date_due: Due date (unix timestamp)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "title": title,
            "type_id": type_id,
            "against_type": against_type,
            "against_id": against_id,
        }
        if description:
            data["description"] = description
        if status_id is not None:
            data["status_id"] = status_id
        if class_id is not None:
            data["class_id"] = class_id
        if assignee is not None:
            data["assignee"] = assignee
        if priority_id is not None:
            data["priority_id"] = priority_id
        if affiliation_id is not None:
            data["affiliation_id"] = affiliation_id
        if date_started is not None:
            data["date_started"] = date_started
        if date_due is not None:
            data["date_due"] = date_due
        if fields:
            data["_fields"] = fields
        return await client.post("/issues", data=data)

    @server.tool()
    async def accelo_update_issue(
        id: int,
        title: str | None = None,
        description: str | None = None,
        status_id: int | None = None,
        class_id: int | None = None,
        assignee: int | None = None,
        priority_id: int | None = None,
        date_due: int | None = None,
        resolution_detail: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing issue.

        Args:
            id: Issue ID (required)
            title: New title
            description: New description
            status_id: New status ID (bypasses progressions)
            class_id: New class ID
            assignee: New assignee staff ID
            priority_id: New priority ID
            date_due: New due date (unix timestamp)
            resolution_detail: Resolution details
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if status_id is not None:
            data["status_id"] = status_id
        if class_id is not None:
            data["class_id"] = class_id
        if assignee is not None:
            data["assignee"] = assignee
        if priority_id is not None:
            data["priority_id"] = priority_id
        if date_due is not None:
            data["date_due"] = date_due
        if resolution_detail is not None:
            data["resolution_detail"] = resolution_detail
        if fields:
            data["_fields"] = fields
        return await client.put(f"/issues/{id}", data=data)

    @server.tool()
    async def accelo_delete_issue(id: int) -> dict:
        """Delete an issue.

        Args:
            id: Issue ID to delete
        """
        return await client.delete(f"/issues/{id}")
