"""Accelo Resources (Attachments) tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register resource/attachment tools with the MCP server."""

    @server.tool()
    async def accelo_list_collections(
        object_type: str,
        object_id: int,
    ) -> dict:
        """List resource collections for an object.

        Args:
            object_type: The object type (e.g. "companies", "issues", "jobs", "contacts")
            object_id: The object's ID
        """
        return await client.get(f"/{object_type}/{object_id}/collections")

    @server.tool()
    async def accelo_list_resources(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List resources (attachments) from Accelo.

        Args:
            filters: Filter dict. Keys: id, mimetype, activity_id, collection_id,
                date_created_before/after, order_by_asc/desc
            fields: Additional fields, e.g. "owner_type,owner_id,collection_id"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/resources", params=params)

    @server.tool()
    async def accelo_count_resources(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count resources (attachments) matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/resources/count", params=params)

    @server.tool()
    async def accelo_get_resource(id: int, fields: str | None = None) -> dict:
        """Get a single resource (attachment) by ID.

        Args:
            id: Resource ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/resources/{id}", params=params)

    @server.tool()
    async def accelo_download_resource_url(id: int) -> dict:
        """Get the download URL for a resource.

        Returns the URL path to download the resource. The actual download
        requires the Bearer token as authentication.

        Args:
            id: Resource ID
        """
        return {
            "download_url": f"{client._base_url}/resources/{id}/download",
            "resource_id": id,
            "note": "Use the Bearer token in Authorization header to download",
        }
