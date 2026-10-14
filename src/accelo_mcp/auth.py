"""OAuth2 authentication management for Accelo API."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import logging
import os
import secrets
import tempfile
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


def _token_dir() -> Path:
    """Return the token directory, resolved at call time.

    Reads the module global so tests can monkeypatch TOKEN_DIR for isolation.
    """
    return TOKEN_DIR


def _token_file() -> Path:
    """Return the token file path, resolved at call time.

    Reads the module global so tests can monkeypatch TOKEN_FILE for isolation.
    """
    return TOKEN_FILE


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
        # Serialises the refresh/acquire path (issue #15). Created lazily on first
        # use inside the async get_token() so it binds to the running event loop,
        # not at import or construction time (which may run before a loop exists).
        self._refresh_lock: asyncio.Lock | None = None
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
                    # Escape the provider-supplied error so a malicious
                    # error/error_description cannot inject markup (CWE-79).
                    safe_error = html.escape(result["error"] or "")
                    self.wfile.write(
                        f"<html><body><h1>Error: {safe_error}</h1></body></html>".encode()
                    )
                else:
                    self.send_response(404)
                    self.end_headers()
                    return

                code_received.set()

            def log_message(self, format, *args):  # noqa: A002
                """Suppress default request logging."""

        # Bind in the calling thread so a bind failure (e.g. the port is still held
        # by a previous login) surfaces here as an AuthError instead of being lost
        # in the worker thread and leaving the caller to hang (issue #14).
        try:
            server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
        except OSError as e:
            raise AuthError(
                f"Could not bind callback listener on 127.0.0.1:{port}: {e}. "
                f"A previous login may still hold the port, or another process is using it."
            ) from e

        def _serve():
            server.serve_forever(poll_interval=0.5)

        server_thread = threading.Thread(target=_serve, daemon=True)
        server_thread.start()

        # Block until code received or timeout, then tear the listener down on every
        # exit path so the redirect port is freed for a retry and a late callback
        # cannot be served (and so falsely report success) after we stop waiting.
        try:
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
        finally:
            server.shutdown()  # thread-safe stop of serve_forever
            server.server_close()  # release the socket / free the port
            server_thread.join(timeout=5.0)

    def _port_from_redirect_uri(self) -> int:
        """Extract the port number from the configured redirect URI.

        Falls back to port 8080 if no explicit port is specified (avoids
        requiring root/elevated privileges that port 80 would need).
        """
        if not self.config.redirect_uri:
            raise AuthError("redirect_uri is required for auto-callback listener")
        parsed = urlparse(self.config.redirect_uri)
        return parsed.port or 8080

    def _get_refresh_lock(self) -> asyncio.Lock:
        """Return the refresh lock, creating it lazily under the running loop.

        Only ever called from within get_token() (under a running event loop), so
        the lock binds to the correct loop and no locking is needed around the
        idempotent lazy init.
        """
        if self._refresh_lock is None:
            self._refresh_lock = asyncio.Lock()
        return self._refresh_lock

    async def get_token(self) -> str:
        """Returns a valid Bearer token, refreshing/acquiring as needed."""
        if self._is_valid():
            return self._token  # type: ignore

        # Serialise refresh/acquire so concurrent callers trigger exactly one
        # network request; the re-check collapses the waiters onto the winner's
        # freshly stored token (issue #15).
        async with self._get_refresh_lock():
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
        # Dispatch the blocking callback wait off the event loop so other MCP
        # requests keep being served while we wait for the browser (issue #14).
        code = await asyncio.to_thread(self._wait_for_callback, redirect_port)

        await self._exchange_code(code, self.config.redirect_uri)
        logger.info("Acquired token via web authorization flow")

    # ─── Installed Application Flow ───────────────────────────────────────────

    async def _installed_authorization_flow(self):
        """Installed app flow: admin visits approval URL, gets PIN, user enters it."""
        import sys

        # Guard FIRST, before any side effects: the PIN prompt needs an interactive
        # terminal, so bail out on non-TTY stdin before the authorize POST, the
        # browser open, or any printing — otherwise we would open a browser and
        # emit PIN instructions for a prompt we can never read (issue #14).
        if not sys.stdin.isatty():
            raise AuthError(
                "Installed-application login needs an interactive terminal to read the "
                "approval PIN, but stdin is not a TTY (it is the MCP protocol stream on the "
                "stdio transport). Complete the login in a terminal, or use a 'service' "
                "auth type for unattended operation."
            )

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
        # Dispatch the blocking callback wait off the event loop so other MCP
        # requests keep being served while we wait for the browser (issue #14).
        code = await asyncio.to_thread(self._wait_for_callback, redirect_port)

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

        # Capture the token actually sent so we only clear/carry over against it,
        # never clobbering a newer token another caller may have stored (issue #15).
        sent_refresh_token = self._refresh_token
        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": sent_refresh_token,
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
            # Only a terminal invalid_grant means the refresh token is dead;
            # drop it (in memory and on disk) so the next call reauthenticates.
            # Transport/server errors and non-JSON bodies are non-terminal, so
            # the refresh token is kept for a later retry.
            try:
                error = response.json().get("error")
            except (json.JSONDecodeError, ValueError):
                error = None
            # Only clear when the token is terminally dead AND still the one we
            # sent, so a newer token stored meanwhile is never dropped.
            if error == "invalid_grant" and self._refresh_token == sent_refresh_token:
                self._refresh_token = None
                self._persist_tokens()
            raise AuthError(f"Token refresh failed ({response.status_code}): {response.text}")

        result = response.json()
        # Keep the refresh token we sent when the response does not issue a new one
        if not result.get("refresh_token"):
            result["refresh_token"] = sent_refresh_token
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
        """Save tokens to disk with secure permissions.

        Writes atomically via a temp file in the resolved target directory,
        fsyncs the file and the directory, then renames it over the old file so
        readers never see a partial write. The default token directory is
        created 0700; a WARNING is logged (but the write proceeds) when the
        resolved directory is group/world-writable. Orphaned temp files from a
        previous interrupted write are swept first. Failures are logged and
        swallowed so a persist error never crashes the caller.
        """
        # Path.resolve() raises RuntimeError for a symlink loop (Python 3.12+);
        # resolve first so a symlinked token file is updated at its target, not
        # replaced, and fail soft if the path cannot be resolved.
        try:
            target = _token_file().resolve()
        except RuntimeError as e:
            logger.warning("Failed to persist tokens: %s", e)
            return

        try:
            token_dir = _token_dir()
            token_dir.mkdir(parents=True, exist_ok=True)
            token_dir.chmod(0o700)

            # Warn (do not refuse) if the resolved write directory is readable
            # beyond the owner — the tokens could be exposed to other users.
            parent = target.parent
            if os.stat(parent).st_mode & 0o022:
                logger.warning(
                    "Token directory %s is writable by group/other; tokens may be exposed",
                    parent,
                )

            token_data = {
                "deployment": self.config.deployment,
                "access_token": self._token,
                "refresh_token": self._refresh_token,
                "expires_at": self._expires_at,
            }

            # Sweep orphaned temp files left by a previously interrupted write.
            for stale in parent.glob(".tokens-*.tmp"):
                try:
                    stale.unlink(missing_ok=True)
                except OSError:
                    pass

            # Write to a temp file and rename it over the old one, so readers never
            # see a partial file. mkstemp creates the file 0600, which keeps the
            # tokens private without a separate chmod.
            fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tokens-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(token_data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, target)
            except BaseException:
                # Covers OSError and async cancellation: never leave a temp file behind.
                Path(tmp_path).unlink(missing_ok=True)
                raise
            if os.name == "posix":
                # Directory fsync is POSIX-only; non-POSIX platforms rely on
                # best-effort OS flushing (Windows is not a supported platform).
                # The new file is already in place, so a failure here is not a
                # failed persist.
                try:
                    dir_fd = os.open(parent, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError as e:
                    logger.debug("Could not fsync %s: %s", parent, e)
            logger.debug("Tokens persisted to %s", target)
        except OSError as e:
            logger.warning("Failed to persist tokens: %s", e)

    def _load_cached_tokens(self):
        """Load previously persisted tokens if they exist and match deployment."""
        try:
            token_file = _token_file()
            if not token_file.exists():
                return

            data = json.loads(token_file.read_text())
            if data.get("deployment") != self.config.deployment:
                logger.debug("Cached tokens are for different deployment, ignoring")
                return

            self._token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            self._expires_at = data.get("expires_at", 0)
            logger.debug("Loaded cached tokens (expires_at=%.0f)", self._expires_at)
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Could not load cached tokens: %s", e)
