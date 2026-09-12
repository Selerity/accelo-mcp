"""Accelo Companies tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register company tools with the MCP server."""

    @server.tool()
    async def accelo_list_companies(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List companies from Accelo with optional filtering, field selection, and search.

        Args:
            filters: Filter dict. Supported keys: id, status, standing, manager_id,
                custom_id, website, contact_number, postal_address, default_affiliation,
                date_created_before/after, date_modified_before/after,
                order_by_asc/desc (id, name, date_created, date_modified, standing, status)
            fields: Additional fields to return, e.g. "website,phone,postal_address(city)", "_ALL"
            search: Search over website, name, phone, fax
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/companies", params=params)

    @server.tool()
    async def accelo_get_company(id: int, fields: str | None = None) -> dict:
        """Get a single company by ID.

        Args:
            id: Company ID
            fields: Additional fields to return, e.g. "website,phone,postal_address(city)"
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/companies/{id}", params=params)

    @server.tool()
    async def accelo_count_companies(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count companies matching the given filters.

        Args:
            filters: Same filters as accelo_list_companies
            search: Search over website, name, phone, fax
        """
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/companies/count", params=params)

    @server.tool()
    async def accelo_create_company(
        name: str,
        website: str | None = None,
        phone: str | None = None,
        fax: str | None = None,
        comments: str | None = None,
        status_id: int | None = None,
        standing: str | None = None,
        parent_id: int | None = None,
        custom_id: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new company in Accelo.

        Args:
            name: Company name (required)
            website: Company website URL
            phone: Phone number
            fax: Fax number
            comments: Notes about the company
            status_id: Initial status ID
            standing: Initial standing (overridden by status_id if both provided)
            parent_id: Parent company ID
            custom_id: Custom identifier
            fields: Additional fields to return in response
        """
        data: dict[str, Any] = {"name": name}
        if website:
            data["website"] = website
        if phone:
            data["phone"] = phone
        if fax:
            data["fax"] = fax
        if comments:
            data["comments"] = comments
        if status_id is not None:
            data["status_id"] = status_id
        if standing:
            data["standing"] = standing
        if parent_id is not None:
            data["parent_id"] = parent_id
        if custom_id:
            data["custom_id"] = custom_id
        if fields:
            data["_fields"] = fields
        return await client.post("/companies", data=data)

    @server.tool()
    async def accelo_update_company(
        id: int,
        name: str | None = None,
        website: str | None = None,
        phone: str | None = None,
        fax: str | None = None,
        comments: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing company.

        Args:
            id: Company ID (required)
            name: New company name
            website: New website URL
            phone: New phone number
            fax: New fax number
            comments: New comments
            fields: Additional fields to return in response
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if website is not None:
            data["website"] = website
        if phone is not None:
            data["phone"] = phone
        if fax is not None:
            data["fax"] = fax
        if comments is not None:
            data["comments"] = comments
        if fields:
            data["_fields"] = fields
        return await client.put(f"/companies/{id}", data=data)

    @server.tool()
    async def accelo_delete_company(id: int) -> dict:
        """Delete a company from Accelo.

        Args:
            id: Company ID to delete
        """
        return await client.delete(f"/companies/{id}")

    @server.tool()
    async def accelo_list_company_managers(
        company_id: int,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List the managers (staff) of a company.

        Args:
            company_id: Company ID
            fields: Additional fields on the returned staff objects
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(fields=fields, page=page, limit=limit)
        return await client.get(f"/companies/{company_id}/managers", params=params)

    @server.tool()
    async def accelo_add_company_manager(
        company_id: int,
        manager_id: int,
        nature: str | None = None,
    ) -> dict:
        """Add a staff member as a manager of a company.

        Args:
            company_id: Company ID
            manager_id: staff_id of the staff member to set as manager (required)
            nature: Relationship nature — "professional" (default), "confidential",
                or "private"
        """
        data: dict[str, Any] = {"manager_id": manager_id}
        if nature:
            data["nature"] = nature
        return await client.post(f"/companies/{company_id}/managers/add", data=data)

    @server.tool()
    async def accelo_remove_company_manager(
        company_id: int,
        relationship_id: int,
    ) -> dict:
        """Remove a manager from a company.

        Identified by the manager relationship's `relationship_id` (NOT the staff_id),
        because a staff member can have multiple manager relationships with one company.
        Get the relationship_id from accelo_list_company_managers.

        Args:
            company_id: Company ID
            relationship_id: The relationship_id of the manager record to remove
        """
        # The Accelo endpoint is DELETE /companies/{id}/managers/delete with
        # relationship_id as a form param. Our client.delete() carries no body,
        # so use the documented method-override (POST + _method=delete) to send it.
        data: dict[str, Any] = {"relationship_id": relationship_id, "_method": "delete"}
        return await client.post(f"/companies/{company_id}/managers/delete", data=data)
