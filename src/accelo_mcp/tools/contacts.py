"""Accelo Contacts tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register contact tools with the MCP server."""

    @server.tool()
    async def accelo_list_contacts(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List contacts from Accelo.

        Args:
            filters: Filter dict. Keys: id, email, title, standing, affiliation, status,
                username, contact_number, date_created/modified_before/after,
                order_by_asc/desc (id, fullname, firstname, surname, date_modified, etc.)
            fields: Additional fields, e.g. "default_affiliation(),comments"
            search: Search over firstname, surname, email
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/contacts", params=params)

    @server.tool()
    async def accelo_get_contact(id: int, fields: str | None = None) -> dict:
        """Get a single contact by ID.

        Args:
            id: Contact ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/contacts/{id}", params=params)

    @server.tool()
    async def accelo_count_contacts(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count contacts matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/contacts/count", params=params)

    @server.tool()
    async def accelo_create_contact(
        firstname: str,
        surname: str,
        company_id: int,
        email: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        position: str | None = None,
        title: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new contact (also creates an affiliation to the company).

        Args:
            firstname: First name (required)
            surname: Surname (required)
            company_id: Company to affiliate with (required)
            email: Email address
            phone: Phone number
            mobile: Mobile number
            position: Job position/title at the company
            title: Honorific (Mr, Ms, etc.)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "firstname": firstname,
            "surname": surname,
            "company_id": company_id,
        }
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if mobile:
            data["mobile"] = mobile
        if position:
            data["position"] = position
        if title:
            data["title"] = title
        if fields:
            data["_fields"] = fields
        return await client.post("/contacts", data=data)

    @server.tool()
    async def accelo_update_contact(
        id: int,
        firstname: str | None = None,
        surname: str | None = None,
        title: str | None = None,
        comments: str | None = None,
        status: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing contact.

        Args:
            id: Contact ID (required)
            firstname: New first name
            surname: New surname
            title: New honorific
            comments: New comments
            status: New status ID
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if firstname:
            data["firstname"] = firstname
        if surname:
            data["surname"] = surname
        if title is not None:
            data["title"] = title
        if comments is not None:
            data["comments"] = comments
        if status is not None:
            data["status"] = status
        if fields:
            data["_fields"] = fields
        return await client.put(f"/contacts/{id}", data=data)

    @server.tool()
    async def accelo_deactivate_contact(id: int) -> dict:
        """Deactivate a contact (set standing to inactive).

        This does NOT delete the contact — the Accelo API has no contact-delete
        operation; it only sets the contact's standing to "inactive". Takes no
        other parameters.

        Args:
            id: Contact ID to deactivate
        """
        return await client.delete(f"/contacts/{id}")
