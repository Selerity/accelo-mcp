"""Accelo Prospects (Sales) tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register prospect tools with the MCP server."""

    @server.tool()
    async def accelo_list_prospects(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List prospects (sales) from Accelo.

        Prospects link to a company via affiliation_id → get affiliation → company_id.
        Use fields="affiliation()" to expand the client contact, or filter by company
        directly with the 'company' filter.

        Args:
            filters: Filter dict. Keys: id, standing, weighting, success, affiliation,
                manager, prospect_type, status, prospect_probability, company,
                date_created/due/actioned_before/after, order_by_asc/desc
            fields: Additional fields, e.g. "manager(),affiliation(),value"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/prospects", params=params)

    @server.tool()
    async def accelo_get_prospect(id: int, fields: str | None = None) -> dict:
        """Get a single prospect (sale) by ID.

        Args:
            id: Prospect ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/prospects/{id}", params=params)

    @server.tool()
    async def accelo_count_prospects(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count prospects matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/prospects/count", params=params)

    @server.tool()
    async def accelo_create_prospect(
        title: str,
        affiliation_id: int,
        type_id: int,
        value: float | None = None,
        staff_id: int | None = None,
        date_due: int | None = None,
        weighting: int | None = None,
        status_id: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new prospect (sale).

        Args:
            title: Prospect title (required)
            affiliation_id: Affiliation ID (required)
            type_id: Prospect type ID (required)
            value: Monetary value
            staff_id: Manager staff ID
            date_due: Due date (unix timestamp)
            weighting: Weighting 0-5
            status_id: Initial status ID
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "title": title,
            "affiliation_id": affiliation_id,
            "type_id": type_id,
        }
        if value is not None:
            data["value"] = value
        if staff_id is not None:
            data["staff_id"] = staff_id
        if date_due is not None:
            data["date_due"] = date_due
        if weighting is not None:
            data["weighting"] = weighting
        if status_id is not None:
            data["status_id"] = status_id
        if fields:
            data["_fields"] = fields
        return await client.post("/prospects", data=data)

    @server.tool()
    async def accelo_update_prospect(
        id: int,
        title: str | None = None,
        value: float | None = None,
        staff_id: int | None = None,
        date_due: int | None = None,
        weighting: int | None = None,
        progress: int | None = None,
        status_id: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing prospect.

        Args:
            id: Prospect ID (required)
            title: New title
            value: New value
            staff_id: New manager staff ID
            date_due: New due date (unix timestamp)
            weighting: New weighting (0-5)
            progress: New progress (0-100)
            status_id: New status ID (bypasses progressions)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if value is not None:
            data["value"] = value
        if staff_id is not None:
            data["staff_id"] = staff_id
        if date_due is not None:
            data["date_due"] = date_due
        if weighting is not None:
            data["weighting"] = weighting
        if progress is not None:
            data["progress"] = progress
        if status_id is not None:
            data["status_id"] = status_id
        if fields:
            data["_fields"] = fields
        return await client.put(f"/prospects/{id}", data=data)

    @server.tool()
    async def accelo_delete_prospect(id: int) -> dict:
        """Delete a prospect.

        Args:
            id: Prospect ID to delete
        """
        return await client.delete(f"/prospects/{id}")
