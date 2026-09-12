"""Accelo Timers tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register timer tools with the MCP server."""

    @server.tool()
    async def accelo_list_timers(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List timers from Accelo (current user's timers only for service apps).

        Args:
            filters: Filter dict. Keys: id, staff, status
            fields: Additional fields, e.g. "staff(),against_title"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/timers", params=params)

    @server.tool()
    async def accelo_get_timer(id: int, fields: str | None = None) -> dict:
        """Get a single timer by ID.

        Args:
            id: Timer ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/timers/{id}", params=params)

    @server.tool()
    async def accelo_create_timer(
        subject: str,
        against_type: str | None = None,
        against_id: int | None = None,
        seconds: int | None = None,
        auto_start: bool = False,
        fields: str | None = None,
    ) -> dict:
        """Create a new timer.

        Args:
            subject: Timer subject (required)
            against_type: Object type to time against
            against_id: Object ID to time against
            seconds: Initial seconds
            auto_start: Whether to start immediately (stops other timers)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {"subject": subject}
        if against_type:
            data["against_type"] = against_type
        if against_id is not None:
            data["against_id"] = against_id
        if seconds is not None:
            data["seconds"] = seconds
        data["auto_start"] = "1" if auto_start else "0"
        if fields:
            data["_fields"] = fields
        return await client.post("/timers", data=data)

    @server.tool()
    async def accelo_start_timer(id: int, fields: str | None = None) -> dict:
        """Start a timer.

        Args:
            id: Timer ID
            fields: Additional fields to return
        """
        data = {"_fields": fields} if fields else {}
        return await client.put(f"/timers/{id}/start", data=data or None)

    @server.tool()
    async def accelo_pause_timer(id: int, fields: str | None = None) -> dict:
        """Pause a running timer.

        Args:
            id: Timer ID
            fields: Additional fields to return
        """
        data = {"_fields": fields} if fields else {}
        return await client.put(f"/timers/{id}/pause", data=data or None)

    @server.tool()
    async def accelo_cancel_timer(id: int) -> dict:
        """Cancel and delete a timer.

        Args:
            id: Timer ID
        """
        return await client.put(f"/timers/{id}/cancel")

    @server.tool()
    async def accelo_delete_timer(id: int) -> dict:
        """Delete a timer.

        Args:
            id: Timer ID to delete
        """
        return await client.delete(f"/timers/{id}")
