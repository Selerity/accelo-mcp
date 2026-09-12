"""Accelo Time Externals tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register time external tools with the MCP server."""

    @server.tool()
    async def accelo_list_time_externals(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List time externals (imported calendar appointments) from Accelo.

        Time externals are appointments imported from Google, Exchange, or Outlook
        calendars. They can be converted to activities for scheduling and timesheets.

        Args:
            filters: Filter dict. Keys: id, staff_id,
                order_by_asc/desc (id, staff_id, date_created, date_modified,
                date_started, date_ended)
            fields: Additional fields, e.g. "description,date_started,date_ended"
            search: Search over title, description
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/time/externals", params=params)

    @server.tool()
    async def accelo_get_time_external(id: int, fields: str | None = None) -> dict:
        """Get a single time external by ID.

        Args:
            id: Time External ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/time/externals/{id}", params=params)

    @server.tool()
    async def accelo_count_time_externals(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count time externals matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/time/externals/count", params=params)

    @server.tool()
    async def accelo_convert_time_external_to_activity(
        id: int,
        engagement_table: str,
        engagement_id: int,
    ) -> dict:
        """Convert a time external (imported calendar appointment) into an activity.

        Creates a meeting activity against the given object, plus a second activity
        as a report on the meeting — the process for turning an imported appointment
        into a workable Accelo timesheet/schedule entry.

        Args:
            id: Time External ID to convert (required)
            engagement_table: The against_type for the new activity — the object type
                the meeting is created against (e.g. "company", "job", "issue") (required)
            engagement_id: The against_id — ID of the object to create against (required)
        """
        data: dict[str, Any] = {
            "engagement_table": engagement_table,
            "engagement_id": engagement_id,
        }
        return await client.post(f"/time/externals/{id}/convert_to_meeting", data=data)
