"""Accelo Checklists tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register checklist tools with the MCP server."""

    @server.tool()
    async def accelo_list_checklists(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List checklists from Accelo.

        Checklists are to-do lists attached to tasks. Each checklist contains items
        that can be marked complete. Currently only supported against tasks.

        Args:
            filters: Filter dict. Keys: id, against_id, against_type, created_by,
                date_created_before/after, order_by_asc/desc (id, date_created)
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/checklists", params=params)

    @server.tool()
    async def accelo_get_checklist(id: int, fields: str | None = None) -> dict:
        """Get a single checklist by ID.

        Args:
            id: Checklist ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/checklists/{id}", params=params)

    @server.tool()
    async def accelo_count_checklists(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count checklists matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/checklists/count", params=params)

    @server.tool()
    async def accelo_create_checklist(
        against_type: str,
        against_id: int,
        items: list[dict[str, Any]],
        fields: str | None = None,
    ) -> dict:
        """Create a new checklist.

        Args:
            against_type: Object type (required) — currently only 'task' is supported
            against_id: Object ID (required)
            items: Array of items (required). Each item: {"title": "...", "ordering": 0}
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "against_type": against_type,
            "against_id": against_id,
            "items": items,
        }
        if fields:
            data["_fields"] = fields
        return await client.post("/checklists", data=data)

    @server.tool()
    async def accelo_update_checklist(
        id: int,
        items: list[dict[str, Any]] | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing checklist.

        Args:
            id: Checklist ID (required)
            items: Updated array of items. Each: {"title": "...", "ordering": 0}
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if items is not None:
            data["items"] = items
        if fields:
            data["_fields"] = fields
        return await client.put(f"/checklists/{id}", data=data)

    @server.tool()
    async def accelo_delete_checklist(id: int) -> dict:
        """Delete a checklist.

        Args:
            id: Checklist ID to delete
        """
        return await client.delete(f"/checklists/{id}")
