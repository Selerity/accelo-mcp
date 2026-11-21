"""Accelo Progressions tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register progression tools with the MCP server."""

    @server.tool()
    async def accelo_list_progressions(
        object_type: str,
        object_id: int,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List available progressions for an object (possible status transitions).

        Args:
            object_type: The object type — tasks, companies, jobs, prospects,
                issues, milestones, affiliations, contracts, contacts, expenses
            object_id: The object's ID
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(page=page, limit=limit)
        return await client.get(f"/{object_type}/{object_id}/progressions", params=params)

    @server.tool()
    async def accelo_run_progression(
        object_type: str,
        object_id: int,
        progression_id: int,
    ) -> dict:
        """Auto-run a progression to advance an object's status.

        Use accelo_list_progressions first to find available progression IDs.

        Args:
            object_type: The object type
            object_id: The object's ID
            progression_id: The progression ID to execute
        """
        return await client.post(f"/{object_type}/{object_id}/progressions/{progression_id}/auto")
