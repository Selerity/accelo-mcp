"""Accelo Extension Fields (Custom Fields) tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register extension tools with the MCP server."""

    @server.tool()
    async def accelo_list_extension_fields(
        object_type: str,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List extension fields available for an object type.

        Args:
            object_type: The object type — assets, contracts, issues, jobs, prospects
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(fields=fields, page=page, limit=limit)
        return await client.get(f"/{object_type}/extensions/fields", params=params)

    @server.tool()
    async def accelo_get_extension_values(
        object_type: str,
        object_id: int,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """Get extension field values for a specific object.

        Args:
            object_type: The object type (e.g. "issues", "jobs", "contracts")
            object_id: The object's ID
            fields: Additional fields to return
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(fields=fields, page=page, limit=limit)
        return await client.get(f"/{object_type}/{object_id}/extensions/values", params=params)

    @server.tool()
    async def accelo_set_extension_value(
        object_type: str,
        object_id: int,
        extension_field_id: int,
        value: str,
    ) -> dict:
        """Set an extension field value on an object.

        Args:
            object_type: The object type (e.g. "issues", "jobs")
            object_id: The object's ID
            extension_field_id: The extension field's ID
            value: The value to set (use value_int, value_date, value_id for typed fields)
        """
        return await client.post(
            f"/{object_type}/{object_id}/extensions/fields/{extension_field_id}",
            data={"value": value},
        )
