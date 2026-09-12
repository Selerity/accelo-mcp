"""Accelo Requests tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register request tools with the MCP server."""

    @server.tool()
    async def accelo_list_requests(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List requests from Accelo.

        Args:
            filters: Filter dict. Keys: id, standing, affiliation, type,
                request_priority, lead, claimer_id,
                date_created/modified_before/after, order_by_asc/desc
            fields: Additional fields, e.g. "body,affiliation(),claimer()"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/requests", params=params)

    @server.tool()
    async def accelo_get_request(id: int, fields: str | None = None) -> dict:
        """Get a single request by ID.

        Args:
            id: Request ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/requests/{id}", params=params)

    @server.tool()
    async def accelo_count_requests(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count requests matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/requests/count", params=params)

    @server.tool()
    async def accelo_create_request(
        title: str,
        type_id: int,
        body: str | None = None,
        affiliation_id: int | None = None,
        priority_id: int | None = None,
        source: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new request.

        Args:
            title: Request title (required)
            type_id: Request type ID (required)
            body: Request body
            affiliation_id: Affiliation ID
            priority_id: Priority ID
            source: Source ('email' or null)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {"title": title, "type_id": type_id}
        if body:
            data["body"] = body
        if affiliation_id is not None:
            data["affiliation_id"] = affiliation_id
        if priority_id is not None:
            data["priority_id"] = priority_id
        if source:
            data["source"] = source
        if fields:
            data["_fields"] = fields
        return await client.post("/requests", data=data)

    @server.tool()
    async def accelo_update_request(
        id: int,
        title: str | None = None,
        body: str | None = None,
        type_id: int | None = None,
        standing: str | None = None,
        claimer_id: int | None = None,
        priority_id: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing request.

        Args:
            id: Request ID (required)
            title: New title
            body: New body
            type_id: New type ID
            standing: New standing (pending, open, converted, closed)
            claimer_id: Staff ID to claim the request
            priority_id: New priority ID
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if body is not None:
            data["body"] = body
        if type_id is not None:
            data["type_id"] = type_id
        if standing:
            data["standing"] = standing
        if claimer_id is not None:
            data["claimer_id"] = claimer_id
        if priority_id is not None:
            data["priority_id"] = priority_id
        if fields:
            data["_fields"] = fields
        return await client.put(f"/requests/{id}", data=data)

    @server.tool()
    async def accelo_list_request_threads(
        filters: dict[str, Any] | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List request threads on the deployment.

        A request thread groups a request with its activity thread. Returns a
        "requests" array plus a "linked_objects" array of objects linked to those
        requests.

        Args:
            filters: Filter dict. Keys: standing, request_type_id (the request
                type_id), interact_from_staff (staff_id), date_created_before/after
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, page=page, limit=limit)
        return await client.get("/requests/threads", params=params)
