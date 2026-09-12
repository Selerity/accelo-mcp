"""Accelo Segmentations tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register segmentation tools with the MCP server."""

    @server.tool()
    async def accelo_list_segmentations(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List segmentations (categories) from Accelo.

        Segmentations organize companies, contacts, and affiliations into categories
        for management and reporting. Each segmentation has a link_type ('company',
        'contact', or 'affiliation') and can be exclusive (single value) or
        multi-value.

        Args:
            filters: Filter dict. Keys: id, link_type, standing, required, exclusive,
                leaf, order_by_asc/desc (id)
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/segmentations", params=params)

    @server.tool()
    async def accelo_get_segmentation(id: int, fields: str | None = None) -> dict:
        """Get a single segmentation by ID.

        Args:
            id: Segmentation ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/segmentations/{id}", params=params)

    @server.tool()
    async def accelo_count_segmentations(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count segmentations matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/segmentations/count", params=params)
