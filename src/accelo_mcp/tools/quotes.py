"""Accelo Quotes tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register quote tools with the MCP server."""

    @server.tool()
    async def accelo_list_quotes(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List quotes (proposals) from Accelo.

        Quotes are proposals typically created against a prospect (sale). They contain
        service and material line items with pricing. Use fields="manager(),affiliation()"
        to expand linked objects.

        Args:
            filters: Filter dict. Keys: id, standing, affiliation, manager, status,
                against_type, against_id, created_by,
                date_created/expiry_before/after, order_by_asc/desc
            fields: Additional fields, e.g. "manager(),affiliation(),introduction"
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/quotes", params=params)

    @server.tool()
    async def accelo_get_quote(id: int, fields: str | None = None) -> dict:
        """Get a single quote by ID.

        Args:
            id: Quote ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/quotes/{id}", params=params)

    @server.tool()
    async def accelo_count_quotes(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count quotes matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/quotes/count", params=params)

    @server.tool()
    async def accelo_create_quote(
        title: str,
        against_type: str,
        against_id: int,
        affiliation_id: int | None = None,
        manager_id: int | None = None,
        date_expiry: int | None = None,
        notes: str | None = None,
        introduction: str | None = None,
        conclusion: str | None = None,
        terms_and_conditions: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new quote (proposal).

        Args:
            title: Quote title (required)
            against_type: Object type (required) — typically 'prospect'
            against_id: Object ID (required)
            affiliation_id: Affiliation ID for the client contact
            manager_id: Staff ID for the quote manager
            date_expiry: Expiry date (unix timestamp)
            notes: Additional notes
            introduction: HTML introduction for the published quote
            conclusion: HTML conclusion for the published quote
            terms_and_conditions: HTML terms and conditions
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "title": title,
            "against_type": against_type,
            "against_id": against_id,
        }
        if affiliation_id is not None:
            data["affiliation_id"] = affiliation_id
        if manager_id is not None:
            data["manager_id"] = manager_id
        if date_expiry is not None:
            data["date_expiry"] = date_expiry
        if notes:
            data["notes"] = notes
        if introduction:
            data["introduction"] = introduction
        if conclusion:
            data["conclusion"] = conclusion
        if terms_and_conditions:
            data["terms_and_conditions"] = terms_and_conditions
        if fields:
            data["_fields"] = fields
        return await client.post("/quotes", data=data)

    @server.tool()
    async def accelo_update_quote(
        id: int,
        title: str | None = None,
        affiliation_id: int | None = None,
        manager_id: int | None = None,
        date_expiry: int | None = None,
        notes: str | None = None,
        introduction: str | None = None,
        conclusion: str | None = None,
        terms_and_conditions: str | None = None,
        client_portal_access: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing quote.

        Args:
            id: Quote ID (required)
            title: New title
            affiliation_id: New affiliation ID
            manager_id: New manager staff ID
            date_expiry: New expiry date (unix timestamp)
            notes: New notes
            introduction: New HTML introduction
            conclusion: New HTML conclusion
            terms_and_conditions: New HTML terms
            client_portal_access: "1" or "0" for portal access
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if title:
            data["title"] = title
        if affiliation_id is not None:
            data["affiliation_id"] = affiliation_id
        if manager_id is not None:
            data["manager_id"] = manager_id
        if date_expiry is not None:
            data["date_expiry"] = date_expiry
        if notes is not None:
            data["notes"] = notes
        if introduction is not None:
            data["introduction"] = introduction
        if conclusion is not None:
            data["conclusion"] = conclusion
        if terms_and_conditions is not None:
            data["terms_and_conditions"] = terms_and_conditions
        if client_portal_access is not None:
            data["client_portal_access"] = client_portal_access
        if fields:
            data["_fields"] = fields
        return await client.put(f"/quotes/{id}", data=data)
