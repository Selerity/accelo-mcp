"""OAuth2 authentication management for Accelo API."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .config import AcceloConfig

logger = logging.getLogger(__name__)

TOKEN_DIR = Path.home() / ".accelo-mcp"
TOKEN_FILE = TOKEN_DIR / "tokens.json"


class AuthError(Exception):
    """Raised when authentication fails."""


class AuthManager:
    """Manages OAuth2 tokens for all Accelo application types.

    Supports:
    - Service Application: client_credentials grant (no user interaction)
    - Web Application: authorization_code + refresh_token
    - Installed Application: authorization_code via PIN + refresh_token
    - Public Application: authorization_code + PKCE (no client secret)
    """

    def __init__(self, config: AcceloConfig):
        self.config = config
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0
        self._http = httpx.AsyncClient(timeout=30.0)
        self._load_cached_tokens()

    @property
    def _token_url(self) -> str:
        return f"{self.config.oauth2_url}/token"

    @property
    def _authorize_url(self) -> str:
        return f"{self.config.oauth2_url}/authorize"

    @property
    def _basic_auth(self) -> str:
        """HTTP Basic auth header value (base64 encoded client_id:client_secret)."""
        credentials = f"{self.config.client_id}:{self.config.client_secret or ''}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    # ─── OAuth2 Callback Listener ─────────────────────────────────────────────

    @staticmethod
    def _wait_for_callback(port: int, timeout: float = 120.0) -> str:
        """Start a local HTTP server and wait for the OAuth2 redirect callback.

        Returns the authorization code from the callback query parameters.
        Raises AuthError if the callback carries an error or times out.
        """
        result: dict[str, str | None] = {"code": None, "error": None}
        server_ready = threading.Event()
        code_received = threading.Event()

        class _CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if "code" in params:
                    result["code"] = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body>"
                        b"<h1>&#10004; Authorization successful!</h1>"
                        b"<p>You can close this tab and return to the terminal.</p>"
                        b"</body></html>"
                    )
                elif "error" in params:
                    desc = params.get("error_description", params["error"])
                    result["error"] = desc[0] if desc else "Unknown error"
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        f"<html><body><h1>Error: {result['error']}</h1></body></html>".encode()
                    )
                else:
                    self.send_response(404)
                    self.end_headers()
                    return

                code_received.set()

            def log_message(self, format, *args):  # noqa: A002
                """Suppress default request logging."""

        def _serve():
            server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
            server.timeout = 1.0
            server_ready.set()
            while not code_received.is_set():
                server.handle_request()
            server.server_close()

        server_thread = threading.Thread(target=_serve, daemon=True)
        server_thread.start()
        server_ready.wait()

        # Block until code received or timeout
        if not code_received.wait(timeout=timeout):
            raise AuthError(
                f"Timed out waiting for authorization callback on port {port} "
                f"(waited {timeout:.0f}s)"
            )

        if result["error"]:
            raise AuthError(f"Authorization denied: {result['error']}")

        if not result["code"]:
            raise AuthError("No authorization code received in callback")

        return result["code"]

    def _port_from_redirect_uri(self) -> int:
        """Extract the port number from the configured redirect URI.

        Falls back to port 8080 if no explicit port is specified (avoids
        requiring root/elevated privileges that port 80 would need).
        """
        if not self.config.redirect_uri:
            raise AuthError("redirect_uri is required for auto-callback listener")
        parsed = urlparse(self.config.redirect_uri)
        return parsed.port or 8080

    async def get_token(self) -> str:
        """Returns a valid Bearer token, refreshing/acquiring as needed."""
        if self._is_valid():
            return self._token  # type: ignore

        if self._refresh_token and self.config.auth_type != "service":
            try:
                await self._refresh_token_flow()
                return self._token  # type: ignore
            except AuthError:
                logger.warning("Token refresh failed, re-authenticating")

        await self._acquire_token()
        return self._token  # type: ignore

    async def close(self):
        """Close the HTTP client."""
        await self._http.aclose()

    def _is_valid(self) -> bool:
        """Check if current token is valid (exists and not expired with 60s buffer)."""
        return self._token is not None and time.time() < (self._expires_at - 60)

    async def _acquire_token(self):
        """Acquire a new token based on auth_type."""
        match self.config.auth_type:
            case "service":
                await self._client_credentials_flow()
            case "web":
                await self._web_authorization_flow()
            case "installed":
                await self._installed_authorization_flow()
            case "public":
                await self._pkce_authorization_flow()
            case _:
                raise AuthError(f"Unknown auth type: {self.config.auth_type}")

    # ─── Service Application Flow ─────────────────────────────────────────────

    async def _client_credentials_flow(self):
        """Acquire token via client_credentials grant (Service Applications)."""
        response = await self._http.post(
            self._token_url,
            headers={
                "Authorization": self._basic_auth,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": self.config.scope,
            },
        )

        if response.status_code != 200:
            raise AuthError(f"Token acquisition failed ({response.status_code}): {response.text}")

        data = response.json()
        self._set_token(data)
        logger.info("Acquired token via client_credentials flow")

    # ─── Web Application Flow ─────────────────────────────────────────────────

    async def _web_authorization_flow(self):
        """Web app flow: open browser, listen for redirect callback, exchange code.

        Starts a local HTTP server on the redirect URI port, opens the browser
        to the authorization URL, and automatically catches the callback.
        """
        import sys

        redirect_port = self._port_from_redirect_uri()

        params = urlencode(
            {
                "client_id": self.config.client_id,
                "response_type": "code",
                "scope": self.config.scope,
                "redirect_uri": self.config.redirect_uri,
            }
        )
        auth_url = f"{self._authorize_url}?{params}"

        print(  # noqa: T201
            f"\n{'=' * 60}\n"
            f"AUTHORIZATION REQUIRED (Web Application)\n"
            f"{'=' * 60}\n"
            f"Opening browser for authorization...\n"
            f"(listening for callback on port {redirect_port})\n",
            file=sys.stderr,
        )

        webbrowser.open(auth_url)
        code = self._wait_for_callback(redirect_port)

        await self._exchange_code(code, self.config.redirect_uri)
        logger.info("Acquired token via web authorization flow")

    # ─── Installed Application Flow ───────────────────────────────────────────

    async def _installed_authorization_flow(self):
        """Installed app flow: admin visits approval URL, gets PIN, user enters it."""
        import sys

        # Request authorization — Accelo returns a 302 redirect to the approval page
        response = await self._http.post(
            self._authorize_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": self.config.client_id,
                "response_type": "code",
                "scope": self.config.scope,
            },
            follow_redirects=False,
        )

        # Extract the approval URL from the Location header
        if response.status_code not in (200, 302):
            raise AuthError(
                f"Authorization request failed ({response.status_code}): {response.text}"
            )

        approval_url = response.headers.get("location")

        print(  # noqa: T201
            f"\n{'=' * 60}\nAUTHORIZATION REQUIRED (Installed Application)\n{'=' * 60}\n",
            file=sys.stderr,
        )

        if approval_url:
            print(  # noqa: T201
                "An admin must approve this application.\n"
                "Opening approval page in browser...\n\n"
                f"  {approval_url}\n\n"
                "After approving, Accelo will display a PIN.\n"
                "Enter the PIN below:\n",
                file=sys.stderr,
            )
            try:
                webbrowser.open(approval_url)
            except Exception as e:
                logger.warning("Failed to open browser: %s", e)
                print("  (Could not open browser automatically)\n", file=sys.stderr)  # noqa: T201
        else:
            print(  # noqa: T201
                "A PIN has been sent to an admin of your Accelo deployment.\n"
                "Enter the PIN below to complete authorization:\n",
                file=sys.stderr,
            )

        pin = input("PIN: ").strip()
        if not pin:
            raise AuthError("No PIN provided")

        await self._exchange_code(pin, self.config.redirect_uri)
        logger.info("Acquired token via installed application flow")

    # ─── Token Exchange & Refresh ─────────────────────────────────────────────

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a cryptographically random PKCE code verifier (43-128 chars, URL-safe)."""
        return secrets.token_urlsafe(64)[:128]

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Generate S256 code challenge from a code verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    # ─── Public Application (PKCE) Flow ───────────────────────────────────────

    async def _pkce_authorization_flow(self):
        """Public app flow: open browser with PKCE challenge, listen for callback.

        For native, CLI or SPA clients that can't keep a secret. Starts a local
        HTTP server, opens the browser with code_challenge, and catches the callback.
        """
        import sys

        redirect_port = self._port_from_redirect_uri()

        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)

        params = urlencode(
            {
                "client_id": self.config.client_id,
                "response_type": "code",
                "scope": self.config.scope,
                "redirect_uri": self.config.redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        auth_url = f"{self._authorize_url}?{params}"

        print(  # noqa: T201
            f"\n{'=' * 60}\n"
            f"AUTHORIZATION REQUIRED (Public Application — PKCE)\n"
            f"{'=' * 60}\n"
            f"Opening browser for authorization...\n"
            f"(listening for callback on port {redirect_port})\n",
            file=sys.stderr,
        )

        webbrowser.open(auth_url)
        code = self._wait_for_callback(redirect_port)

        await self._exchange_code_pkce(code, code_verifier)
        logger.info("Acquired token via PKCE authorization flow")

    async def _exchange_code_pkce(self, code: str, code_verifier: str):
        """Exchange an authorization code for tokens using PKCE (no client secret)."""
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.client_id,
            "code_verifier": code_verifier,
        }
        if self.config.redirect_uri:
            data["redirect_uri"] = self.config.redirect_uri

        response = await self._http.post(
            self._token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
        )

        if response.status_code != 200:
            raise AuthError(f"PKCE code exchange failed ({response.status_code}): {response.text}")

        result = response.json()
        self._set_token(result)

    # ─── Standard Token Exchange & Refresh ────────────────────────────────────

    async def _exchange_code(self, code: str, redirect_uri: str | None):
        """Exchange an authorization code for access + refresh tokens."""
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
        }
        if redirect_uri:
            data["redirect_uri"] = redirect_uri

        response = await self._http.post(
            self._token_url,
            headers={
                "Authorization": self._basic_auth,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=data,
        )

        if response.status_code != 200:
            raise AuthError(f"Code exchange failed ({response.status_code}): {response.text}")

        result = response.json()
        self._set_token(result)

    async def _refresh_token_flow(self):
        """Refresh an expired token using the refresh_token."""
        if not self._refresh_token:
            raise AuthError("No refresh token available")

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }

        if self.config.auth_type == "public":
            # PKCE/public clients don't have a secret — identify via client_id in body
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data["client_id"] = self.config.client_id
        else:
            headers = {
                "Authorization": self._basic_auth,
                "Content-Type": "application/x-www-form-urlencoded",
            }

        response = await self._http.post(
            self._token_url,
            headers=headers,
            data=data,
        )

        if response.status_code != 200:
            self._refresh_token = None
            raise AuthError(f"Token refresh failed ({response.status_code}): {response.text}")

        result = response.json()
        self._set_token(result)
        logger.info("Token refreshed successfully")

    # ─── Token Storage ────────────────────────────────────────────────────────

    def _set_token(self, data: dict[str, Any]):
        """Store token data from API response and persist to disk."""
        self._token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        expires_in = int(data.get("expires_in", 2592000))  # default 30 days
        self._expires_at = time.time() + expires_in
        self._persist_tokens()

    def _persist_tokens(self):
        """Save tokens to disk with secure permissions."""
        try:
            TOKEN_DIR.mkdir(parents=True, exist_ok=True)
            TOKEN_DIR.chmod(0o700)

            token_data = {
                "deployment": self.config.deployment,
                "access_token": self._token,
                "refresh_token": self._refresh_token,
                "expires_at": self._expires_at,
            }

            TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
            TOKEN_FILE.chmod(0o600)
            logger.debug("Tokens persisted to %s", TOKEN_FILE)
        except OSError as e:
            logger.warning("Failed to persist tokens: %s", e)

    def _load_cached_tokens(self):
        """Load previously persisted tokens if they exist and match deployment."""
        try:
            if not TOKEN_FILE.exists():
                return

            data = json.loads(TOKEN_FILE.read_text())
            if data.get("deployment") != self.config.deployment:
                logger.debug("Cached tokens are for different deployment, ignoring")
                return

            self._token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            self._expires_at = data.get("expires_at", 0)
            logger.debug("Loaded cached tokens (expires_at=%.0f)", self._expires_at)
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Could not load cached tokens: %s", e)
