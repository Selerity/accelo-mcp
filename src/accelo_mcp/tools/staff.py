"""Accelo Staff tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register staff tools with the MCP server."""

    @server.tool()
    async def accelo_list_staff(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List staff members from Accelo.

        Args:
            filters: Filter dict. Keys: id, email, standing, username
            fields: Additional fields, e.g. "email,title,mobile"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/staff", params=params)

    @server.tool()
    async def accelo_get_staff(id: int, fields: str | None = None) -> dict:
        """Get a single staff member by ID.

        Args:
            id: Staff ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/staff/{id}", params=params)

    @server.tool()
    async def accelo_get_current_staff(fields: str | None = None) -> dict:
        """Get the currently authenticated staff member (whoami).

        Useful for verifying authentication is working. Returns the staff
        member associated with the current OAuth token.

        Args:
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get("/staff/whoami", params=params)

    @server.tool()
    async def accelo_count_staff(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count staff members matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/staff/count", params=params)

    @server.tool()
    async def accelo_list_staff_memberships(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List staff group memberships from Accelo.

        Each membership links a staff member to a group.

        Args:
            filters: Filter dict. Keys: id, staff_id, group_id, order_by_asc/desc
            fields: Additional fields, e.g. "staff()"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/staff/memberships", params=params)

    @server.tool()
    async def accelo_create_staff(
        username: str,
        password: str,
        firstname: str,
        surname: str,
        email: str,
        title: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        fax: str | None = None,
        position: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new staff member (user) on the Accelo deployment.

        ADMINISTRATIVE WRITE — this provisions a new user account and consumes a
        licence seat. Confirm with the user before calling. The `password` is a
        secret: never echo it back in a response or log it.

        Args:
            username: Login username (required)
            password: Initial password for the new account (required, secret)
            firstname: First name (required)
            surname: Surname (required)
            email: Email address (required)
            title: Title, e.g. "Mr", "Ms"
            phone: Phone number
            mobile: Mobile number
            fax: Fax number
            position: Position in the company
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "username": username,
            "password": password,
            "firstname": firstname,
            "surname": surname,
            "email": email,
        }
        if title:
            data["title"] = title
        if phone:
            data["phone"] = phone
        if mobile:
            data["mobile"] = mobile
        if fax:
            data["fax"] = fax
        if position:
            data["position"] = position
        if fields:
            data["_fields"] = fields
        return await client.post("/staff", data=data)

    @server.tool()
    async def accelo_update_staff(
        id: int,
        firstname: str | None = None,
        surname: str | None = None,
        title: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        fax: str | None = None,
        position: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update a staff member's descriptive details.

        ADMINISTRATIVE WRITE — edits another user's record. Only the descriptive
        fields below are updatable via this endpoint (the API does not expose
        standing/financial_level/username here). Only non-None fields are sent.

        Args:
            id: Staff ID (required)
            firstname: New first name
            surname: New surname
            title: New title
            email: New email address
            phone: New phone number
            mobile: New mobile number
            fax: New fax number
            position: New position
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if firstname:
            data["firstname"] = firstname
        if surname:
            data["surname"] = surname
        if title:
            data["title"] = title
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if mobile:
            data["mobile"] = mobile
        if fax:
            data["fax"] = fax
        if position:
            data["position"] = position
        if fields:
            data["_fields"] = fields
        return await client.put(f"/staff/{id}", data=data)
