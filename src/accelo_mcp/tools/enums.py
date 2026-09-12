"""Composite enumeration-list tools for Accelo status/type/class/priority sub-resources.

Many Accelo objects expose small enumeration sub-resources — statuses, types,
classes, priorities, resolutions, probabilities — that an LLM needs in order to
discover valid filter IDs (e.g. "what issue statuses exist?" before filtering
issues by ``status``). Rather than ~30 near-identical ``list_<object>_<enum>``
tools, this module exposes THREE composite tools (list / get / count) that
dispatch to ``GET /{object}/{enum}`` via an explicit registry, keeping the tool
count low and the full surface documented in one place.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params

# Registry of enumeration sub-resources.
# Key: (object, enum_type) -> {"path": <resource path>, "count": bool, "get": bool}
# path is the collection path; get appends /{id}; count appends /count.
# Flags reflect what the Accelo API actually offers (verified against the docs).
ENUM_REGISTRY: dict[tuple[str, str], dict[str, Any]] = {
    # --- Statuses ---
    ("companies", "statuses"): {"path": "/companies/statuses", "count": True, "get": True},
    ("contacts", "statuses"): {"path": "/contacts/statuses", "count": True, "get": True},
    ("affiliations", "statuses"): {"path": "/affiliations/statuses", "count": True, "get": True},
    ("jobs", "statuses"): {"path": "/jobs/statuses", "count": True, "get": True},
    ("issues", "statuses"): {"path": "/issues/statuses", "count": False, "get": False},
    ("milestones", "statuses"): {"path": "/milestones/statuses", "count": True, "get": True},
    ("quotes", "statuses"): {"path": "/quotes/statuses", "count": True, "get": True},
    ("contracts", "statuses"): {"path": "/contracts/statuses", "count": True, "get": True},
    ("prospects", "statuses"): {"path": "/prospects/statuses", "count": False, "get": False},
    # --- Types ---
    ("jobs", "types"): {"path": "/jobs/types", "count": False, "get": True},
    ("issues", "types"): {"path": "/issues/types", "count": False, "get": True},
    ("expenses", "types"): {"path": "/expenses/types", "count": True, "get": True},
    ("contracts", "types"): {"path": "/contracts/types", "count": True, "get": True},
    ("contributors", "types"): {"path": "/contributors/types", "count": True, "get": True},
    ("requests", "types"): {"path": "/requests/types", "count": False, "get": False},
    ("prospects", "types"): {"path": "/prospects/types", "count": False, "get": False},
    # --- Issue-specific enums ---
    ("issues", "classes"): {"path": "/issues/classes", "count": False, "get": False},
    ("issues", "priorities"): {"path": "/issues/priorities", "count": True, "get": True},
    ("issues", "resolutions"): {"path": "/issues/resolutions", "count": True, "get": True},
    # --- Other ---
    ("tasks", "priorities"): {"path": "/tasks/priorities", "count": False, "get": False},
    ("activities", "classes"): {"path": "/activities/classes", "count": True, "get": True},
    ("prospects", "probabilities"): {
        "path": "/prospects/probabilities",
        "count": True,
        "get": True,
    },
}


def _valid_pairs() -> str:
    """Human-readable list of valid object/enum_type combinations for error messages."""
    return ", ".join(f"{obj}/{enum}" for (obj, enum) in sorted(ENUM_REGISTRY))


def register(server: MCPServer, client: AcceloClient):
    """Register the composite enumeration tools with the MCP server."""

    @server.tool()
    async def accelo_list_enum(
        object: str,
        enum_type: str,
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List an object's enumeration values (statuses, types, classes, etc.).

        Use this to DISCOVER valid IDs before filtering a list endpoint — e.g. call
        accelo_list_enum("issues", "statuses") to learn the status_id values, then
        pass one to accelo_list_issues(filters={"status": <id>}).

        Valid (object, enum_type) combinations:
          Statuses: companies, contacts, affiliations, jobs, issues, milestones,
                    quotes, contracts, prospects  -> enum_type="statuses"
          Types:    jobs, issues, expenses, contracts, contributors, requests,
                    prospects  -> enum_type="types"
          Issues:   enum_type in "classes", "priorities", "resolutions"
          Other:    tasks/"priorities", activities/"classes",
                    prospects/"probabilities"

        Args:
            object: Object name, e.g. "issues", "jobs", "companies"
            enum_type: Enumeration kind, e.g. "statuses", "types", "classes",
                "priorities", "resolutions", "probabilities"
            filters: Filter dict (most enums support id/title/standing + order_by_*)
            fields: Additional fields (most enums support _fields)
            search: Search over title (where supported)
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        entry = ENUM_REGISTRY.get((object, enum_type))
        if entry is None:
            return {
                "error": "invalid_enum",
                "message": (
                    f"No enumeration '{enum_type}' for object '{object}'. "
                    f"Valid combinations: {_valid_pairs()}"
                ),
            }
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get(entry["path"], params=params)

    @server.tool()
    async def accelo_get_enum(
        object: str,
        enum_type: str,
        id: int,
        fields: str | None = None,
    ) -> dict:
        """Get a single enumeration value by ID (e.g. one issue status).

        Only some enumerations expose a get-by-id endpoint; if the combination does
        not, a structured error is returned naming the valid combinations. See
        accelo_list_enum for the full list of (object, enum_type) pairs.

        Args:
            object: Object name, e.g. "issues"
            enum_type: Enumeration kind, e.g. "statuses"
            id: The enumeration value's ID
            fields: Additional fields to return
        """
        entry = ENUM_REGISTRY.get((object, enum_type))
        if entry is None:
            return {
                "error": "invalid_enum",
                "message": (
                    f"No enumeration '{enum_type}' for object '{object}'. "
                    f"Valid combinations: {_valid_pairs()}"
                ),
            }
        if not entry["get"]:
            return {
                "error": "unsupported_operation",
                "message": (
                    f"The Accelo API does not offer get-by-id for {object}/{enum_type}. "
                    "Use accelo_list_enum and filter by id instead."
                ),
            }
        params = {"_fields": fields} if fields else {}
        return await client.get(f"{entry['path']}/{id}", params=params)

    @server.tool()
    async def accelo_count_enum(
        object: str,
        enum_type: str,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count an object's enumeration values matching the given filters.

        Only some enumerations expose a count endpoint; if the combination does not,
        a structured error is returned. See accelo_list_enum for valid pairs.

        Args:
            object: Object name, e.g. "issues"
            enum_type: Enumeration kind, e.g. "statuses"
            filters: Filter dict
            search: Search over title (where supported)
        """
        entry = ENUM_REGISTRY.get((object, enum_type))
        if entry is None:
            return {
                "error": "invalid_enum",
                "message": (
                    f"No enumeration '{enum_type}' for object '{object}'. "
                    f"Valid combinations: {_valid_pairs()}"
                ),
            }
        if not entry["count"]:
            return {
                "error": "unsupported_operation",
                "message": (
                    f"The Accelo API does not offer a count endpoint for "
                    f"{object}/{enum_type}. Use accelo_list_enum instead."
                ),
            }
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get(f"{entry['path']}/count", params=params)
