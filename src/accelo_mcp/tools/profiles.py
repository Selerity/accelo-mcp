"""Accelo Profile Fields tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloAPIError, AcceloClient
from ..models import format_error


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

        The write is driven through the parent object's update endpoint
        (``PUT /{object_type}/{object_id}``) with the value keyed as
        ``profile.{profile_field_id}``, matching Accelo's documented
        "Setting Profile Field Values" syntax. The dedicated
        ``/profiles/fields/{id}`` POST path is rejected by Accelo with
        "The resource endpoint was not recognized." (HTTP 400).

        Args:
            object_type: The object type (e.g. "companies", "issues")
            object_id: The object's ID
            profile_field_id: The profile field's ID
            value: The value to set. The accepted form depends on the field type
                (text, integer, date, lookup, hyperlink, multi_select); pass the
                value in the form Accelo expects for that field.
        """
        try:
            return await client.put(
                f"/{object_type}/{object_id}",
                data={f"profile.{profile_field_id}": value},
            )
        except AcceloAPIError as error:
            # Surface the real Accelo error (status, message, http_code,
            # more_info) to the caller instead of an opaque "Error executing
            # tool" — profile-value writes are a common failure point and the
            # typed-value handling differs by field type.
            return format_error(error)
