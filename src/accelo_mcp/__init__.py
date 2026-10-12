"""Accelo MCP Server — MCP interface to the Accelo CRM platform."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("accelo-mcp")
except PackageNotFoundError:  # package not installed (e.g. running from a raw checkout)
    __version__ = "0.0.0+unknown"
