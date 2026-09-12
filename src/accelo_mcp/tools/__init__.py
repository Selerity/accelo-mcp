"""Accelo MCP tool modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..client import AcceloClient

# All tool modules to register
TOOL_MODULES = [
    "context",
    "companies",
    "contacts",
    "affiliations",
    "activities",
    "issues",
    "jobs",
    "tasks",
    "contracts",
    "contract_periods",
    "prospects",
    "staff",
    "invoices",
    "expenses",
    "requests",
    "milestones",
    "timers",
    "quotes",
    "addresses",
    "object_budgets",
    "assets",
    "checklists",
    "tags",
    "rates",
    "webhooks",
    "referrals",
    "segmentations",
    "skills",
    "taxes",
    "ledgers",
    "payments",
    "divisions",
    "groups",
    "holidays",
    "contributors",
    "signoffs",
    "purchases",
    "time_externals",
    "profiles",
    "extensions",
    "progressions",
    "resources",
    "enums",
    "filters",
    "schema",
    "meta",
]


def register_all_tools(server: "MCPServer", client: "AcceloClient"):
    """Register all tool modules with the MCP server."""
    import importlib

    for module_name in TOOL_MODULES:
        try:
            module = importlib.import_module(f".{module_name}", package=__name__)
            if hasattr(module, "register"):
                module.register(server, client)
        except ImportError:
            # Module not yet implemented — skip silently during development
            pass
