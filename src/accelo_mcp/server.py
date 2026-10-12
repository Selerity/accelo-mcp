"""MCP server setup and entrypoint for Accelo MCP."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import sys
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

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


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean from the environment ('1', 'true', 'yes' are truthy)."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str) -> list[str] | None:
    """Read a comma-separated list from the environment, or None if unset/empty."""
    value = os.environ.get(name)
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _env_port(name: str, default: int) -> int:
    """Read a TCP port from the environment, with a clear error on bad input.

    A misconfigured port is an operator mistake we want surfaced, not hidden by
    a silent fallback to the default (which would leave the server listening on
    the wrong port). We raise a descriptive ValueError instead of letting the
    bare int() conversion crash with an opaque message.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        port = int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer port number, got {value!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535, got {port}")
    return port


@dataclass(frozen=True)
class HttpTransportSettings:
    """Settings for the HTTP transports (Streamable HTTP and SSE).

    Loaded from environment variables so the server can be deployed behind a
    reverse proxy or load balancer without code changes.
    """

    host: str = "127.0.0.1"
    port: int = 3000
    path: str = "/mcp"
    json_response: bool = False
    stateless: bool = False
    allowed_hosts: list[str] | None = None
    allowed_origins: list[str] | None = None
    disable_dns_rebinding_protection: bool = False
    allow_unauthenticated: bool = False

    @classmethod
    def from_env(cls) -> HttpTransportSettings:
        """Load HTTP transport settings from environment variables.

        Environment variables:
            ACCELO_MCP_HOST - interface to bind (default 127.0.0.1; set to
                0.0.0.0 to accept connections from outside the container)
            ACCELO_MCP_PORT - TCP port (default 3000)
            ACCELO_MCP_PATH - Streamable HTTP endpoint path (default /mcp)
            ACCELO_MCP_JSON_RESPONSE - return a single JSON response instead of
                an SSE stream (default false)
            ACCELO_MCP_STATELESS - run without per-session state, so any node
                can serve any request (default false)
            ACCELO_MCP_ALLOWED_HOSTS - comma-separated Host header allow-list
                for DNS-rebinding protection (e.g. the public hostname)
            ACCELO_MCP_ALLOWED_ORIGINS - comma-separated Origin header allow-list
            ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION - disable the Host/Origin
                check entirely (default false; prefer setting the allow-lists)
            ACCELO_MCP_ALLOW_UNAUTHENTICATED - explicitly acknowledge that the
                HTTP transport has no inbound authentication and may be bound to
                a non-loopback interface (default false). Required to start on a
                non-loopback bind; see SECURITY.md.
        """
        return cls(
            host=os.environ.get("ACCELO_MCP_HOST", "127.0.0.1"),
            port=_env_port("ACCELO_MCP_PORT", 3000),
            path=os.environ.get("ACCELO_MCP_PATH", "/mcp"),
            json_response=_env_bool("ACCELO_MCP_JSON_RESPONSE"),
            stateless=_env_bool("ACCELO_MCP_STATELESS"),
            allowed_hosts=_env_list("ACCELO_MCP_ALLOWED_HOSTS"),
            allowed_origins=_env_list("ACCELO_MCP_ALLOWED_ORIGINS"),
            disable_dns_rebinding_protection=_env_bool(
                "ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION"
            ),
            allow_unauthenticated=_env_bool("ACCELO_MCP_ALLOW_UNAUTHENTICATED"),
        )

    def transport_security(self) -> TransportSecuritySettings | None:
        """Build TransportSecuritySettings, or None to keep library defaults.

        DNS-rebinding protection is on by default in the MCP library. When the
        server is reached through a hostname other than localhost (behind a
        proxy or load balancer), that check rejects every request unless the
        expected Host/Origin values are allow-listed here, or the check is
        explicitly disabled.
        """
        if (
            not self.disable_dns_rebinding_protection
            and self.allowed_hosts is None
            and self.allowed_origins is None
        ):
            return None

        return TransportSecuritySettings(
            enable_dns_rebinding_protection=not self.disable_dns_rebinding_protection,
            allowed_hosts=self.allowed_hosts or [],
            allowed_origins=self.allowed_origins or [],
        )

    def is_loopback_bind(self) -> bool:
        """Whether the configured host binds to a loopback interface only.

        ``127.0.0.1``/``::1`` (and the rest of ``127.0.0.0/8``) are loopback and
        reachable only from the local machine. ``0.0.0.0``/``::`` bind every
        interface and are therefore NOT loopback. A hostname we cannot parse as
        an IP address is treated as non-loopback (fail safe) unless it is the
        literal ``localhost``.
        """
        host = self.host.strip()
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            # Not an IP literal (e.g. a hostname) — treat as non-loopback so the
            # exposure gate errs on the side of requiring the explicit opt-in.
            return False

    def check_exposure_allowed(self) -> None:
        """Refuse an *accidental* unauthenticated non-loopback bind.

        The HTTP/SSE transports have no inbound authentication: every caller is
        served with the server's single shared Accelo identity (see SECURITY.md).
        Binding beyond loopback therefore exposes full Accelo access to anyone
        who can reach the port.

        This is a legitimate choice for an operator who has their own network
        controls and genuinely intends it — so it is NOT forbidden. It must only
        be *deliberate*: starting on a non-loopback host requires the operator to
        set ``ACCELO_MCP_ALLOW_UNAUTHENTICATED=true``. The check exists solely to
        stop the accidental exposure (an empty config or a copied ``0.0.0.0``
        example), never to block an intended deployment.

        Raises:
            RuntimeError: if bound to a non-loopback host without the opt-in.
        """
        if self.is_loopback_bind() or self.allow_unauthenticated:
            return

        raise RuntimeError(
            f"Refusing to start: the HTTP transport has no inbound authentication "
            f"and is bound to a non-loopback host ({self.host!r}), which exposes "
            f"full Accelo access to anyone who can reach the port.\n"
            f"  - To keep it local-only, set ACCELO_MCP_HOST=127.0.0.1 (the default).\n"
            f"  - If you intend an exposed bind and have your own network controls "
            f"(firewall, VPN, loopback-only container publish), acknowledge it "
            f"explicitly with ACCELO_MCP_ALLOW_UNAUTHENTICATED=true.\n"
            f"See SECURITY.md for the single-user deployment model."
        )


async def run_stdio() -> None:
    """Run the server with stdio transport."""
    server, client = create_server()

    try:
        await server.run_stdio_async()
    finally:
        await client.close()


async def run_streamable_http(settings: HttpTransportSettings) -> None:
    """Run the server with the Streamable HTTP transport."""
    server, client = create_server()

    try:
        await server.run_streamable_http_async(
            host=settings.host,
            port=settings.port,
            streamable_http_path=settings.path,
            json_response=settings.json_response,
            stateless_http=settings.stateless,
            transport_security=settings.transport_security(),
        )
    finally:
        await client.close()


async def run_sse(settings: HttpTransportSettings) -> None:
    """Run the server with the deprecated SSE transport.

    SSE is retained for backward compatibility. New HTTP deployments should use
    the Streamable HTTP transport (``--http``).
    """
    server, client = create_server()

    try:
        await server.run_sse_async(
            host=settings.host,
            port=settings.port,
            transport_security=settings.transport_security(),
        )
    finally:
        await client.close()


def select_transport(argv: list[str]) -> str:
    """Choose the transport from command-line arguments.

    Returns one of ``"stdio"``, ``"http"``, or ``"sse"``. stdio is the default.
    """
    if "--http" in argv or "--streamable-http" in argv:
        return "http"
    if "--sse" in argv:
        return "sse"
    return "stdio"


def main() -> None:
    """CLI entrypoint for accelo-mcp server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    transport = select_transport(sys.argv)

    if transport == "http":
        settings = HttpTransportSettings.from_env()
        settings.check_exposure_allowed()
        if not settings.is_loopback_bind():
            logger.warning(
                "Accelo MCP HTTP transport is bound to a non-loopback host (%s) "
                "with NO inbound authentication (ACCELO_MCP_ALLOW_UNAUTHENTICATED "
                "is set). Every caller that reaches this port acts with the "
                "server's full Accelo identity. Ensure your own network controls "
                "restrict access to the single intended user. See SECURITY.md.",
                settings.host,
            )
        logger.info(
            "Starting Accelo MCP server (Streamable HTTP on %s:%d%s, "
            "stateless=%s, json_response=%s)",
            settings.host,
            settings.port,
            settings.path,
            settings.stateless,
            settings.json_response,
        )
        asyncio.run(run_streamable_http(settings))
    elif transport == "sse":
        settings = HttpTransportSettings.from_env()
        settings.check_exposure_allowed()
        if not settings.is_loopback_bind():
            logger.warning(
                "Accelo MCP SSE transport is bound to a non-loopback host (%s) "
                "with NO inbound authentication (ACCELO_MCP_ALLOW_UNAUTHENTICATED "
                "is set). Every caller that reaches this port acts with the "
                "server's full Accelo identity. Ensure your own network controls "
                "restrict access to the single intended user. See SECURITY.md.",
                settings.host,
            )
        logger.warning(
            "The SSE transport is deprecated; prefer --http (Streamable HTTP). "
            "Starting Accelo MCP server (SSE on %s:%d)",
            settings.host,
            settings.port,
        )
        asyncio.run(run_sse(settings))
    else:
        logger.info("Starting Accelo MCP server (stdio transport)")
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
