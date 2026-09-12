"""Accelo Addresses tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register address tools with the MCP server."""

    @server.tool()
    async def accelo_list_addresses(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List addresses from Accelo.

        Addresses store location info for companies and contacts. Each address can be
        postal, physical, or both. Use filters against_type and against_id to find
        addresses for a specific company or contact.

        Args:
            filters: Filter dict. Keys: id, against_type, against_id, physical,
                postal, country_id, state_id, zipcode, order_by_asc/desc (id, title)
            fields: Additional fields, e.g. "country(),state(),street1,city"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/addresses", params=params)

    @server.tool()
    async def accelo_get_address(id: int, fields: str | None = None) -> dict:
        """Get a single address by ID.

        Args:
            id: Address ID
            fields: Additional fields to return, e.g. "country(),state()"
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/addresses/{id}", params=params)

    @server.tool()
    async def accelo_count_addresses(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count addresses matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/addresses/count", params=params)

    @server.tool()
    async def accelo_create_address(
        against_type: str,
        against_id: int,
        title: str | None = None,
        street1: str | None = None,
        street2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        state_id: int | None = None,
        country: str | None = None,
        country_id: int | None = None,
        zipcode: str | None = None,
        postal: str | None = None,
        physical: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new address.

        Args:
            against_type: Object type (required) — 'company' or 'contact'
            against_id: Object ID (required)
            title: Name for the address, e.g. "Head Office"
            street1: First line of street address
            street2: Second line of street address
            city: City name
            state: State/province name (use if state_id unknown)
            state_id: State ID (preferred over state name)
            country: Country name (use if country_id unknown)
            country_id: Country ID (preferred over country name)
            zipcode: Postcode/zipcode
            postal: "yes" or "no" — is this a postal address?
            physical: "yes" or "no" — is this a physical address?
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "against_type": against_type,
            "against_id": against_id,
        }
        if title:
            data["title"] = title
        if street1:
            data["street1"] = street1
        if street2:
            data["street2"] = street2
        if city:
            data["city"] = city
        if state:
            data["state"] = state
        if state_id is not None:
            data["state_id"] = state_id
        if country:
            data["country"] = country
        if country_id is not None:
            data["country_id"] = country_id
        if zipcode:
            data["zipcode"] = zipcode
        if postal:
            data["postal"] = postal
        if physical:
            data["physical"] = physical
        if fields:
            data["_fields"] = fields
        return await client.post("/addresses", data=data)

    @server.tool()
    async def accelo_update_address(
        id: int,
        title: str | None = None,
        street1: str | None = None,
        street2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        state_id: int | None = None,
        country: str | None = None,
        country_id: int | None = None,
        zipcode: str | None = None,
        postal: str | None = None,
        physical: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing address.

        Args:
            id: Address ID (required)
            title: New title
            street1: New street line 1
            street2: New street line 2
            city: New city
            state: New state name
            state_id: New state ID
            country: New country name
            country_id: New country ID
            zipcode: New postcode/zipcode
            postal: "yes" or "no"
            physical: "yes" or "no"
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title is not None:
            data["title"] = title
        if street1 is not None:
            data["street1"] = street1
        if street2 is not None:
            data["street2"] = street2
        if city is not None:
            data["city"] = city
        if state is not None:
            data["state"] = state
        if state_id is not None:
            data["state_id"] = state_id
        if country is not None:
            data["country"] = country
        if country_id is not None:
            data["country_id"] = country_id
        if zipcode is not None:
            data["zipcode"] = zipcode
        if postal is not None:
            data["postal"] = postal
        if physical is not None:
            data["physical"] = physical
        if fields:
            data["_fields"] = fields
        return await client.put(f"/addresses/{id}", data=data)
