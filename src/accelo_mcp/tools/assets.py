"""Accelo Assets tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register asset tools with the MCP server."""

    @server.tool()
    async def accelo_list_assets(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List assets from Accelo.

        Assets are flexible objects representing any trackable item — computers,
        licenses, equipment, etc. They are created 'against' a company and can be
        linked to jobs, issues, prospects, or contracts via asset links.

        Args:
            filters: Filter dict. Keys: id, standing, type_id, affiliation_id,
                manager_id, address_id, against_type, against_id,
                date_created_before/after, order_by_asc/desc (id, date_created, standing)
            fields: Additional fields, e.g. "asset_type(),manager(),affiliation()"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/assets", params=params)

    @server.tool()
    async def accelo_get_asset(id: int, fields: str | None = None) -> dict:
        """Get a single asset by ID.

        Args:
            id: Asset ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/assets/{id}", params=params)

    @server.tool()
    async def accelo_count_assets(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count assets matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/assets/count", params=params)

    @server.tool()
    async def accelo_update_asset(
        id: int,
        title: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing asset.

        Args:
            id: Asset ID (required)
            title: New title
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if fields:
            data["_fields"] = fields
        return await client.put(f"/assets/{id}", data=data)

    @server.tool()
    async def accelo_list_asset_types(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List asset types from Accelo.

        Asset types define the schema for assets — which fields are available,
        whether they have managers, affiliations, or addresses.

        Args:
            filters: Filter dict. Keys: id, standing,
                order_by_asc/desc (id, standing, title)
            fields: Additional fields, e.g. "object_link_fields"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/assets/types", params=params)

    @server.tool()
    async def accelo_get_asset_type(id: int, fields: str | None = None) -> dict:
        """Get a single asset type by ID.

        Args:
            id: Asset Type ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/assets/types/{id}", params=params)

    @server.tool()
    async def accelo_list_asset_links(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List asset links (joins between an asset and another object).

        Returns the asset links and the linked assets. A link joins an asset to an
        issue, job, prospect, or contract.

        Args:
            filters: Filter dict
            fields: Additional fields
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/assets/links", params=params)

    @server.tool()
    async def accelo_create_asset_link(
        asset_id: int,
        linked_object_id: int,
        linked_object_type: str,
        description: str | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> dict:
        """Create an asset link between an asset and another object.

        Args:
            asset_id: The asset to link (required)
            linked_object_id: ID of the object to link the asset to (required)
            linked_object_type: Object type to link to — one of the supported types
                for asset links (issue, job, prospect, contract) (required)
            description: Optional description of the link
            start_date: Optional link start date (unix timestamp)
            end_date: Optional link end date (unix timestamp)
        """
        data: dict[str, Any] = {
            "linked_object_id": linked_object_id,
            "linked_object_type": linked_object_type,
        }
        if description:
            data["description"] = description
        if start_date is not None:
            data["start_date"] = start_date
        if end_date is not None:
            data["end_date"] = end_date
        return await client.post(f"/assets/{asset_id}/links", data=data)

    @server.tool()
    async def accelo_delete_asset_link(link_id: int) -> dict:
        """Delete an asset link (does NOT delete the asset itself).

        Args:
            link_id: The asset_link_id to delete
        """
        return await client.delete(f"/assets/links/{link_id}")
