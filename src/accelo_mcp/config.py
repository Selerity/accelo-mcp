"""Configuration management for Accelo MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AcceloConfig:
    """Accelo API configuration loaded from environment variables."""

    deployment: str
    client_id: str
    client_secret: str | None = None
    auth_type: str = "web"
    scope: str = "read(all)"
    redirect_uri: str | None = None

    @property
    def base_url(self) -> str:
        """REST API base URL."""
        return f"https://{self.deployment}.api.accelo.com/api/v0"

    @property
    def oauth2_url(self) -> str:
        """OAuth2 base URL."""
        return f"https://{self.deployment}.api.accelo.com/oauth2/v0"

    @classmethod
    def from_env(cls) -> AcceloConfig:
        """Load configuration from environment variables.

        Required:
            ACCELO_DEPLOYMENT - deployment hostname prefix
            ACCELO_CLIENT_ID - OAuth2 client ID
            ACCELO_CLIENT_SECRET - OAuth2 client secret (not required for 'public' auth type)

        Optional:
            ACCELO_AUTH_TYPE - service|web|installed|public (default: web)
            ACCELO_SCOPE - OAuth2 scope (default: read(all))
            ACCELO_REDIRECT_URI - redirect URI (required for web and public auth types)
        """
        deployment = os.environ.get("ACCELO_DEPLOYMENT")
        if not deployment:
            raise ValueError("ACCELO_DEPLOYMENT environment variable is required")

        client_id = os.environ.get("ACCELO_CLIENT_ID")
        if not client_id:
            raise ValueError("ACCELO_CLIENT_ID environment variable is required")

        auth_type = os.environ.get("ACCELO_AUTH_TYPE", "web")
        if auth_type not in ("service", "web", "installed", "public"):
            raise ValueError(
                f"ACCELO_AUTH_TYPE must be 'service', 'web', 'installed', or 'public', "
                f"got '{auth_type}'"
            )

        client_secret = os.environ.get("ACCELO_CLIENT_SECRET")
        if not client_secret and auth_type != "public":
            raise ValueError(
                "ACCELO_CLIENT_SECRET environment variable is required "
                "(not required for 'public' auth type)"
            )

        scope = os.environ.get("ACCELO_SCOPE", "read(all)")

        redirect_uri = os.environ.get("ACCELO_REDIRECT_URI")
        if auth_type == "web" and not redirect_uri:
            redirect_uri = "http://localhost:9876/callback"
        if auth_type == "public" and not redirect_uri:
            raise ValueError("ACCELO_REDIRECT_URI is required when ACCELO_AUTH_TYPE is 'public'")

        return cls(
            deployment=deployment,
            client_id=client_id,
            client_secret=client_secret,
            auth_type=auth_type,
            scope=scope,
            redirect_uri=redirect_uri,
        )
