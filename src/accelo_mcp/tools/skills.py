"""Accelo Skills tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register skill tools with the MCP server."""

    @server.tool()
    async def accelo_list_skills(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List skills from Accelo.

        Skills are tags assigned to tasks or staff to match work with appropriate
        team members. Use the 'against' object filter to find skills on a
        specific task or staff member.

        Args:
            filters: Filter dict. Keys: id, title,
                against (object filter, e.g. {"task": [24]}),
                order_by_asc/desc
            search: Search over title
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, search=search, page=page, limit=limit)
        return await client.get("/skills", params=params)

    @server.tool()
    async def accelo_count_skills(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count skills matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/skills/count", params=params)

    @server.tool()
    async def accelo_create_skill(title: str, fields: str | None = None) -> dict:
        """Create a new skill.

        Args:
            title: Skill name (required)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {"title": title}
        if fields:
            data["_fields"] = fields
        return await client.post("/skills", data=data)
