"""Accelo Contributors tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register contributor tools with the MCP server."""

    @server.tool()
    async def accelo_list_contributors(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List contributors from Accelo.

        Contributors are third-party contacts involved in client work (jobs, issues,
        prospects). They link a staff member or affiliation to a work object, and can
        be auto-CC'd on correspondence.

        Args:
            filters: Filter dict. Keys: id, standing, status_id, contributor_type_id,
                against_type, against_id, object_id, object_type, auto_cc,
                order_by_asc/desc (id, contributor_type_id, standing, status_id)
            fields: Additional fields, e.g. "contributor_type(),description"
            search: Search over description
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/contributors", params=params)

    @server.tool()
    async def accelo_get_contributor(id: int, fields: str | None = None) -> dict:
        """Get a single contributor by ID.

        Args:
            id: Contributor ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/contributors/{id}", params=params)

    @server.tool()
    async def accelo_count_contributors(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count contributors matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/contributors/count", params=params)

    @server.tool()
    async def accelo_list_contributor_types(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List contributor types from Accelo.

        Contributor types (e.g. 'Advisor') define whether the type has a status,
        whether contributors of the type are auto-CC'd, and its default standing.

        Args:
            filters: Filter dict. Keys: id, title, default_status_id, default_standing,
                order_by_asc/desc (ordering)
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/contributors/types", params=params)

    @server.tool()
    async def accelo_get_contributor_type(id: int, fields: str | None = None) -> dict:
        """Get a single contributor type by ID.

        Args:
            id: Contributor type ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/contributors/types/{id}", params=params)

    @server.tool()
    async def accelo_count_contributor_types(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count contributor types matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/contributors/types/count", params=params)
