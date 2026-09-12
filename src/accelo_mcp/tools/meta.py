"""Accelo Meta tools (rate limits, deployment info)."""

from __future__ import annotations

import time

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient


def register(server: MCPServer, client: AcceloClient):
    """Register meta/utility tools with the MCP server."""

    @server.tool()
    async def accelo_rate_limit_status() -> dict:
        """Get current API rate limit status.

        Returns the remaining requests, total limit, and reset time.
        Accelo allows 5000 requests per hour per deployment.
        """
        reset_time = (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(client.rate_reset))
            if client.rate_reset > 0
            else "unknown"
        )

        return {
            "remaining": client.rate_remaining,
            "limit": client.rate_limit,
            "reset_at_unix": client.rate_reset,
            "reset_at_human": reset_time,
            "usage_percent": round((1 - client.rate_remaining / client.rate_limit) * 100, 1)
            if client.rate_limit > 0
            else 0,
        }
