"""MCP server setup and entrypoint for Accelo MCP."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from mcp.server.mcpserver import MCPServer

from .auth import AuthManager
from .client import AcceloClient
from .config import AcceloConfig
from .tools import register_all_tools

logger = logging.getLogger(__name__)


def create_server() -> tuple[MCPServer, AcceloClient]:
    """Create and configure the MCP server with all tools registered.

    Returns:
        Tuple of (server, client) — client must be closed on shutdown.
    """
    config = AcceloConfig.from_env()
    auth = AuthManager(config)
    client = AcceloClient(auth, config)

    server = MCPServer("accelo-mcp")
    register_all_tools(server, client)

    logger.info(
        "Accelo MCP server configured for deployment '%s' (auth_type=%s)",
        config.deployment,
        config.auth_type,
    )

    return server, client


async def run_stdio():
    """Run the server with stdio transport."""
    server, client = create_server()

    try:
        await server.run_stdio_async()
    finally:
        await client.close()


async def run_sse(port: int):
    """Run the server with SSE transport."""
    server, client = create_server()

    try:
        await server.run_sse_async(host="127.0.0.1", port=port)
    finally:
        await client.close()


def main():
    """CLI entrypoint for accelo-mcp server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if "--sse" in sys.argv:
        port = int(os.environ.get("ACCELO_MCP_PORT", "3000"))
        logger.info("Starting Accelo MCP server (SSE transport on port %d)", port)
        asyncio.run(run_sse(port))
    else:
        logger.info("Starting Accelo MCP server (stdio transport)")
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
