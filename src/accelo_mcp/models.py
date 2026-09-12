"""Shared models and helper functions for Accelo MCP tools."""

from __future__ import annotations

from typing import Any

from .client import build_params  # re-export for tool modules


def format_response(result: dict[str, Any]) -> dict[str, Any]:
    """Format an Accelo API response for MCP tool output.

    Returns the response data with metadata included.
    """
    meta = result.get("meta", {})
    response = result.get("response")

    output: dict[str, Any] = {"data": response}

    # Include pagination info if present
    if "more_info" in meta:
        output["more_info"] = meta["more_info"]

    return output


def format_error(error: Exception) -> dict[str, Any]:
    """Format an error for MCP tool output."""
    from .client import AcceloAPIError

    if isinstance(error, AcceloAPIError):
        return {
            "error": True,
            "status": error.status,
            "message": error.message,
            "http_code": error.http_code,
            "more_info": error.more_info,
        }
    return {
        "error": True,
        "status": "internal_error",
        "message": str(error),
    }


__all__ = ["build_params", "format_response", "format_error"]
