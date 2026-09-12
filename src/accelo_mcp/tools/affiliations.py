"""Accelo Affiliations tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register affiliation tools with the MCP server."""

    @server.tool()
    async def accelo_list_affiliations(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List affiliations (contact-company links) from Accelo.

        An affiliation links a Contact to a Company and holds contact details (email,
        phone, position) for that relationship. A contact can have multiple affiliations
        (one per company they work with). Affiliations are referenced by issues, prospects,
        and invoices to identify the client contact. affiliation.company_id → Company,
        affiliation.contact_id → Contact.

        Args:
            filters: Filter dict. Keys: id, email, standing, status, company, contact,
                postal_address, physical_address, contact_number, invoice_method,
                date_created/modified/last_interacted_before/after,
                order_by_asc/desc
            fields: Additional fields, e.g. "company(),contact(),position"
            search: Search over firstname, surname, fax, phone, mobile, email
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/affiliations", params=params)

    @server.tool()
    async def accelo_get_affiliation(id: int, fields: str | None = None) -> dict:
        """Get a single affiliation by ID.

        Args:
            id: Affiliation ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/affiliations/{id}", params=params)

    @server.tool()
    async def accelo_count_affiliations(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count affiliations matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/affiliations/count", params=params)

    @server.tool()
    async def accelo_create_affiliation(
        company_id: int,
        contact_id: int,
        email: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        position: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new affiliation (link a contact to a company).

        Args:
            company_id: Company ID (required)
            contact_id: Contact ID (required)
            email: Email for this affiliation
            phone: Phone for this affiliation
            mobile: Mobile for this affiliation
            position: Position at the company
            fields: Additional fields to return
        """
        data: dict[str, Any] = {"company_id": company_id, "contact_id": contact_id}
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if mobile:
            data["mobile"] = mobile
        if position:
            data["position"] = position
        if fields:
            data["_fields"] = fields
        return await client.post("/affiliations", data=data)

    @server.tool()
    async def accelo_update_affiliation(
        id: int,
        email: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        position: str | None = None,
        standing: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing affiliation.

        Args:
            id: Affiliation ID (required)
            email: New email
            phone: New phone
            mobile: New mobile
            position: New position
            standing: New standing
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if email is not None:
            data["email"] = email
        if phone is not None:
            data["phone"] = phone
        if mobile is not None:
            data["mobile"] = mobile
        if position is not None:
            data["position"] = position
        if standing:
            data["standing"] = standing
        if fields:
            data["_fields"] = fields
        return await client.put(f"/affiliations/{id}", data=data)

    @server.tool()
    async def accelo_delete_affiliation(id: int) -> dict:
        """Delete an affiliation.

        Args:
            id: Affiliation ID to delete
        """
        return await client.delete(f"/affiliations/{id}")
