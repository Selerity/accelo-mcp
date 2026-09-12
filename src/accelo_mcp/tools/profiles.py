"""Accelo Profile Fields tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient


def register(server: MCPServer, client: AcceloClient):
    """Register profile tools with the MCP server."""

    @server.tool()
    async def accelo_list_profile_fields(
        object_type: str,
        fields: str | None = None,
    ) -> dict:
        """List profile fields available for an object type.

        Args:
            object_type: The object type — affiliations, companies, contacts, contracts,
                invoices, issues, jobs, milestones, prospects, staff
            fields: Additional fields to return
        """
        params = {}
        if fields:
            params["_fields"] = fields
        return await client.get(f"/{object_type}/profiles/fields", params=params)

    @server.tool()
    async def accelo_get_profile_values(
        object_type: str,
        object_id: int,
        fields: str | None = None,
    ) -> dict:
        """Get profile field values for a specific object.

        Args:
            object_type: The object type (e.g. "companies", "issues")
            object_id: The object's ID
            fields: Additional fields to return
        """
        params = {}
        if fields:
            params["_fields"] = fields
        return await client.get(f"/{object_type}/{object_id}/profiles/values", params=params)

    @server.tool()
    async def accelo_set_profile_value(
        object_type: str,
        object_id: int,
        profile_field_id: int,
        value: str,
    ) -> dict:
        """Set a profile field value on an object.

        Args:
            object_type: The object type (e.g. "companies", "issues")
            object_id: The object's ID
            profile_field_id: The profile field's ID
            value: The value to set (type depends on the field: text, integer, date, etc.)
        """
        return await client.post(
            f"/{object_type}/{object_id}/profiles/fields/{profile_field_id}",
            data={"value": value},
        )
