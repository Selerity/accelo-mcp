"""Accelo Holidays tools (Beta)."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register holiday tools with the MCP server."""

    @server.tool()
    async def accelo_list_holidays(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List holidays from Accelo (Beta).

        Holidays are staff leave/time-off entries imported from calendars or
        entered manually. Each has a staff_id, date_start, and either date_end
        or duration_seconds.

        Args:
            filters: Filter dict. Keys: id, staff_id,
                date_start/end_before/after,
                order_by_asc/desc (id, staff_id, date_start, date_end, title)
            fields: Additional fields, e.g. "staff(),duration_seconds"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/holidays", params=params)

    @server.tool()
    async def accelo_get_holiday(id: int, fields: str | None = None) -> dict:
        """Get a single holiday by ID (Beta).

        Args:
            id: Holiday ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/holidays/{id}", params=params)

    @server.tool()
    async def accelo_count_holidays(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count holidays matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/holidays/count", params=params)

    @server.tool()
    async def accelo_create_holiday(
        title: str,
        date_start: int,
        date_end: int | None = None,
        duration_seconds: int | None = None,
        staff_id: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new holiday (Beta).

        Only one of date_end or duration_seconds should be provided.

        Args:
            title: Holiday name (required)
            date_start: Start date as unix timestamp (required)
            date_end: End date as unix timestamp (provide this OR duration_seconds)
            duration_seconds: Duration in seconds (provide this OR date_end)
            staff_id: Staff member ID (defaults to current user)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "title": title,
            "date_start": date_start,
        }
        if date_end is not None:
            data["date_end"] = date_end
        if duration_seconds is not None:
            data["duration_seconds"] = duration_seconds
        if staff_id is not None:
            data["staff_id"] = staff_id
        if fields:
            data["_fields"] = fields
        return await client.post("/holidays", data=data)

    @server.tool()
    async def accelo_update_holiday(
        id: int,
        title: str | None = None,
        date_start: int | None = None,
        date_end: int | None = None,
        duration_seconds: int | None = None,
        staff_id: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing holiday (Beta).

        Args:
            id: Holiday ID (required)
            title: New title
            date_start: New start date
            date_end: New end date
            duration_seconds: New duration
            staff_id: New staff ID
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if date_start is not None:
            data["date_start"] = date_start
        if date_end is not None:
            data["date_end"] = date_end
        if duration_seconds is not None:
            data["duration_seconds"] = duration_seconds
        if staff_id is not None:
            data["staff_id"] = staff_id
        if fields:
            data["_fields"] = fields
        return await client.put(f"/holidays/{id}", data=data)

    @server.tool()
    async def accelo_delete_holiday(id: int) -> dict:
        """Delete a holiday (Beta).

        Args:
            id: Holiday ID to delete
        """
        return await client.delete(f"/holidays/{id}")
