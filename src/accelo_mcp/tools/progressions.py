"""Accelo Progressions tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient


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

        The result has a top-level has_more flag: true when another page exists.
        With limit=100 it is true whenever the page is full, so the next page
        may be empty.
        """
        return await client.get_page(
            f"/{object_type}/{object_id}/progressions", page=page, limit=limit
        )

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
