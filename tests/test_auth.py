"""Tests for accelo_mcp.auth module."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from accelo_mcp import auth as auth_module
from accelo_mcp.auth import AuthError, AuthManager
from accelo_mcp.config import AcceloConfig


class TestServiceFlow:
    """Tests for client_credentials (Service Application) flow."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_acquires_token(self, mock_config):
        """Successfully acquires a token via client_credentials."""
        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test-token-123",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_config)
        token = await auth.get_token()
        await auth.close()

        assert token == "test-token-123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_caches_valid_token(self, mock_config):
        """Does not re-request a valid token."""
        route = respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "cached-token",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_config)
        token1 = await auth.get_token()
        token2 = await auth.get_token()
        await auth.close()

        assert token1 == token2 == "cached-token"
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_error_on_failure(self, mock_config):
        """Raises AuthError on failed token request."""
        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                401,
                json={"error": "invalid_client"},
            )
        )

        auth = AuthManager(mock_config)
        with pytest.raises(AuthError, match="Token acquisition failed"):
            await auth.get_token()
        await auth.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_re_acquires_expired_token(self, mock_config):
        """Re-acquires token when expired."""
        route = respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new-token",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_config)
        auth._token = "old-token"
        auth._expires_at = time.time() - 100  # expired

        token = await auth.get_token()
        await auth.close()

        assert token == "new-token"
        assert route.call_count == 1


class TestRefreshFlow:
    """Tests for refresh_token flow (Web/Installed applications)."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_refreshes_expired_token(self, mock_web_config):
        """Uses refresh token when access token is expired."""
        respx.post(f"{mock_web_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "refreshed-token",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_web_config)
        auth._token = "old-token"
        auth._refresh_token = "old-refresh"
        auth._expires_at = time.time() - 100  # expired

        token = await auth.get_token()
        await auth.close()

        assert token == "refreshed-token"
        assert auth._refresh_token == "new-refresh"

    @respx.mock
    @pytest.mark.asyncio
    async def test_keeps_refresh_token_when_response_omits_it(self, mock_web_config):
        """A refresh response without refresh_token keeps the existing one."""
        respx.post(f"{mock_web_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "refreshed-token", "expires_in": 3600},
            )
        )

        auth = AuthManager(mock_web_config)
        auth._token = "old-token"
        auth._refresh_token = "old-refresh"
        auth._expires_at = time.time() - 100  # expired

        token = await auth.get_token()
        await auth.close()

        assert token == "refreshed-token"
        assert auth._refresh_token == "old-refresh"
        assert json.loads(auth_module.TOKEN_FILE.read_text())["refresh_token"] == "old-refresh"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fresh_grant_does_not_carry_over_refresh_token(self, mock_config):
        """A new grant without refresh_token clears any previously stored one."""
        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "service-token", "expires_in": 3600},
            )
        )

        auth = AuthManager(mock_config)
        auth._refresh_token = "stale-web-refresh"
        auth._expires_at = 0
        await auth.get_token()
        await auth.close()

        assert auth._refresh_token is None
        assert json.loads(auth_module.TOKEN_FILE.read_text())["refresh_token"] is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_refresh_failure_triggers_reauth(self, mock_web_config):
        """Falls back to full reauth when refresh fails."""
        # First call: refresh fails
        # Second call: would be the interactive auth (we'll mock the exchange)
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Refresh fails
                return httpx.Response(400, json={"error": "invalid_grant"})
            else:
                # Code exchange succeeds
                return httpx.Response(
                    200,
                    json={
                        "access_token": "new-token",
                        "refresh_token": "new-refresh",
                        "expires_in": 3600,
                    },
                )

        respx.post(f"{mock_web_config.oauth2_url}/token").mock(side_effect=side_effect)

        auth = AuthManager(mock_web_config)
        auth._token = "expired"
        auth._refresh_token = "bad-refresh"
        auth._expires_at = time.time() - 100

        # Mock the callback listener for web flow
        with patch.object(AuthManager, "_wait_for_callback", return_value="auth-code-123"):
            token = await auth.get_token()
        await auth.close()

        assert token == "new-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_chained_refresh_reuses_original_refresh_token(self, mock_web_config):
        """Across two refreshes where the first omits refresh_token, the second
        request still sends the originally stored refresh token."""
        import urllib.parse

        captured_requests = []

        def side_effect(request):
            captured_requests.append(request)
            # First refresh omits refresh_token; second issues a new one.
            if len(captured_requests) == 1:
                return httpx.Response(
                    200,
                    json={"access_token": "access-1", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "access_token": "access-2",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )

        respx.post(f"{mock_web_config.oauth2_url}/token").mock(side_effect=side_effect)

        auth = AuthManager(mock_web_config)
        auth._token = "old-token"
        auth._refresh_token = "original-refresh"
        auth._expires_at = time.time() - 100  # expired

        token1 = await auth.get_token()
        assert token1 == "access-1"

        # Force a second refresh.
        auth._expires_at = time.time() - 100
        token2 = await auth.get_token()
        assert token2 == "access-2"
        await auth.close()

        assert len(captured_requests) == 2
        second_body = urllib.parse.parse_qs(captured_requests[1].content.decode())
        assert second_body["refresh_token"] == ["original-refresh"]


class TestTokenPersistence:
    """Tests for token persistence to disk."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_persists_tokens(self, mock_config):
        """Tokens are saved to disk after acquisition."""
        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "persisted-token",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_config)
        await auth.get_token()
        await auth.close()

        assert auth_module.TOKEN_FILE.exists()
        data = json.loads(auth_module.TOKEN_FILE.read_text())
        assert data["access_token"] == "persisted-token"
        assert data["deployment"] == "test-deployment"

    @respx.mock
    @pytest.mark.asyncio
    async def test_loads_cached_tokens(self, mock_config):
        """Loads valid cached tokens on startup."""
        # Pre-write token file
        auth_module.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        auth_module.TOKEN_FILE.write_text(
            json.dumps(
                {
                    "deployment": "test-deployment",
                    "access_token": "cached-from-disk",
                    "refresh_token": None,
                    "expires_at": time.time() + 3600,
                }
            )
        )

        auth = AuthManager(mock_config)
        token = await auth.get_token()
        await auth.close()

        assert token == "cached-from-disk"

    @respx.mock
    @pytest.mark.asyncio
    async def test_ignores_different_deployment(self, mock_config):
        """Ignores cached tokens from a different deployment."""
        auth_module.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        auth_module.TOKEN_FILE.write_text(
            json.dumps(
                {
                    "deployment": "other-deployment",
                    "access_token": "wrong-token",
                    "expires_at": time.time() + 3600,
                }
            )
        )

        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "correct-token", "expires_in": 3600},
            )
        )

        auth = AuthManager(mock_config)
        token = await auth.get_token()
        await auth.close()

        assert token == "correct-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_token_file_permissions(self, mock_config):
        """Token file is created with 0600 permissions."""
        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        auth = AuthManager(mock_config)
        await auth.get_token()
        await auth.close()

        assert auth_module.TOKEN_FILE.exists()
        mode = auth_module.TOKEN_FILE.stat().st_mode & 0o777
        assert mode == 0o600

    @pytest.mark.asyncio
    async def test_failed_write_keeps_existing_token_file(self, mock_config, caplog):
        """A write that fails part-way leaves the previous token file intact."""
        token_file = auth_module.TOKEN_FILE
        token_file.parent.mkdir(parents=True, exist_ok=True)
        original = json.dumps({"deployment": "test-deployment", "access_token": "old"})
        token_file.write_text(original)
        before = set(token_file.parent.iterdir())

        auth = AuthManager(mock_config)
        with patch.object(os, "replace", side_effect=OSError("disk full")):
            auth._set_token({"access_token": "new", "expires_in": 3600})
        await auth.close()

        assert token_file.read_text() == original
        assert set(token_file.parent.iterdir()) == before
        assert "Failed to persist tokens: disk full" in caplog.text

    @pytest.mark.asyncio
    async def test_rewrite_tightens_existing_file_permissions(self, mock_config):
        """Rewriting a pre-existing 0644 token file leaves it 0600."""
        token_file = auth_module.TOKEN_FILE
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text("{}")
        token_file.chmod(0o644)

        auth = AuthManager(mock_config)
        auth._set_token({"access_token": "new", "expires_in": 3600})
        await auth.close()

        assert token_file.stat().st_mode & 0o777 == 0o600

    @pytest.mark.asyncio
    async def test_symlinked_token_file_is_written_through(self, mock_config, tmp_path):
        """A symlinked token file stays a symlink and its target is updated."""
        target = tmp_path / "elsewhere" / "tokens.json"
        target.parent.mkdir()
        target.write_text("{}")
        token_file = auth_module.TOKEN_FILE
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.symlink_to(target)

        auth = AuthManager(mock_config)
        auth._set_token({"access_token": "new", "expires_in": 3600})
        await auth.close()

        assert token_file.is_symlink()
        assert json.loads(target.read_text())["access_token"] == "new"
        assert list(target.parent.glob(".tokens-*.tmp")) == []

    @pytest.mark.asyncio
    async def test_symlink_loop_does_not_raise(self, mock_config, caplog):
        """A path that cannot be resolved (e.g. symlink loop) fails soft with a warning.

        Path.resolve() only raises RuntimeError for symlink loops on Python 3.12+,
        so patch it directly to exercise the fail-soft handler on any interpreter.
        """
        auth = AuthManager(mock_config)
        with patch.object(Path, "resolve", side_effect=RuntimeError("Symlink loop")):
            auth._set_token({"access_token": "new", "expires_in": 3600})
        await auth.close()

        assert auth._token == "new"
        assert "Failed to persist tokens" in caplog.text

    @pytest.mark.asyncio
    async def test_directory_fsync_failure_is_not_a_failed_persist(self, mock_config, caplog):
        """If only the directory fsync fails, the new file is kept and no warning is logged."""
        token_file = auth_module.TOKEN_FILE
        real_open = os.open

        def open_failing_on_dirs(path, flags, *args, **kwargs):
            if os.path.isdir(path):
                raise OSError("EINVAL")
            return real_open(path, flags, *args, **kwargs)

        auth = AuthManager(mock_config)
        with patch.object(os, "open", side_effect=open_failing_on_dirs):
            auth._set_token({"access_token": "new", "expires_in": 3600})
        await auth.close()

        assert json.loads(token_file.read_text())["access_token"] == "new"
        assert "Failed to persist tokens" not in caplog.text


class TestPKCEFlow:
    """Tests for public application (PKCE) flow."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_pkce_acquires_token(self, mock_public_config):
        """Successfully acquires a token via PKCE flow."""
        respx.post(f"{mock_public_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "pkce-token-123",
                    "refresh_token": "pkce-refresh-456",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_public_config)
        with patch.object(AuthManager, "_wait_for_callback", return_value="auth-code-pkce"):
            token = await auth.get_token()
        await auth.close()

        assert token == "pkce-token-123"
        assert auth._refresh_token == "pkce-refresh-456"

    @respx.mock
    @pytest.mark.asyncio
    async def test_pkce_sends_code_verifier(self, mock_public_config):
        """Token exchange includes code_verifier and client_id, no Authorization header."""
        captured_request = None

        def capture_request(request):
            nonlocal captured_request
            captured_request = request
            return httpx.Response(
                200,
                json={
                    "access_token": "pkce-token",
                    "refresh_token": "pkce-refresh",
                    "expires_in": 3600,
                },
            )

        respx.post(f"{mock_public_config.oauth2_url}/token").mock(side_effect=capture_request)

        auth = AuthManager(mock_public_config)
        with patch.object(AuthManager, "_wait_for_callback", return_value="test-code"):
            await auth.get_token()
        await auth.close()

        assert captured_request is not None
        body = captured_request.content.decode()
        assert "code_verifier=" in body
        assert "client_id=" in body
        assert "grant_type=authorization_code" in body
        # No Authorization header for PKCE
        assert "Authorization" not in captured_request.headers

    @respx.mock
    @pytest.mark.asyncio
    async def test_pkce_callback_error_raises(self, mock_public_config):
        """Raises AuthError when callback carries an error."""
        auth = AuthManager(mock_public_config)
        error = AuthError("Authorization denied: access_denied")
        with patch.object(AuthManager, "_wait_for_callback", side_effect=error):
            with pytest.raises(AuthError, match="Authorization denied"):
                await auth.get_token()
        await auth.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_pkce_token_exchange_failure(self, mock_public_config):
        """Raises AuthError when PKCE code exchange fails."""
        respx.post(f"{mock_public_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                400,
                json={"error": "invalid_grant"},
            )
        )

        auth = AuthManager(mock_public_config)
        with patch.object(AuthManager, "_wait_for_callback", return_value="bad-code"):
            with pytest.raises(AuthError, match="PKCE code exchange failed"):
                await auth.get_token()
        await auth.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_pkce_refresh_uses_client_id_not_basic_auth(self, mock_public_config):
        """Refresh token flow for public type sends client_id, not Basic auth."""
        captured_request = None

        def capture_request(request):
            nonlocal captured_request
            captured_request = request
            return httpx.Response(
                200,
                json={
                    "access_token": "refreshed-pkce-token",
                    "refresh_token": "new-pkce-refresh",
                    "expires_in": 3600,
                },
            )

        respx.post(f"{mock_public_config.oauth2_url}/token").mock(side_effect=capture_request)

        auth = AuthManager(mock_public_config)
        auth._token = "expired-token"
        auth._refresh_token = "old-refresh"
        auth._expires_at = time.time() - 100  # expired

        token = await auth.get_token()
        await auth.close()

        assert token == "refreshed-pkce-token"
        assert captured_request is not None
        body = captured_request.content.decode()
        assert "client_id=" in body
        assert "grant_type=refresh_token" in body
        assert "Authorization" not in captured_request.headers


class TestPKCEHelpers:
    """Tests for PKCE helper methods (code_verifier, code_challenge)."""

    def test_code_verifier_length(self):
        """Code verifier is between 43 and 128 characters."""
        verifier = AuthManager._generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_code_verifier_url_safe(self):
        """Code verifier only contains URL-safe characters."""
        import re

        verifier = AuthManager._generate_code_verifier()
        assert re.match(r"^[A-Za-z0-9_\-]+$", verifier)

    def test_code_verifier_randomness(self):
        """Each call produces a different verifier."""
        v1 = AuthManager._generate_code_verifier()
        v2 = AuthManager._generate_code_verifier()
        assert v1 != v2

    def test_code_challenge_is_s256(self):
        """Code challenge is the base64url-encoded SHA256 of the verifier."""
        import base64
        import hashlib

        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")

        challenge = AuthManager._generate_code_challenge(verifier)
        assert challenge == expected_challenge

    def test_code_challenge_no_padding(self):
        """Code challenge does not contain base64 padding characters."""
        verifier = AuthManager._generate_code_verifier()
        challenge = AuthManager._generate_code_challenge(verifier)
        assert "=" not in challenge


class TestCallbackListener:
    """Tests for the OAuth2 auto-callback listener."""

    @pytest.mark.asyncio
    async def test_captures_code_from_callback(self, mock_web_config):
        """Listener captures authorization code from redirect."""
        import threading
        import urllib.request

        auth = AuthManager(mock_web_config)

        # Start the listener in a thread (simulating the real flow)
        result = {}

        def run_listener():
            result["code"] = auth._wait_for_callback(19876, timeout=5.0)

        listener_thread = threading.Thread(target=run_listener)
        listener_thread.start()

        # Give the server a moment to start
        import time

        time.sleep(0.2)

        # Simulate Accelo redirecting back with a code
        urllib.request.urlopen("http://127.0.0.1:19876/callback?code=test-auth-code-xyz")

        listener_thread.join(timeout=5.0)
        await auth.close()

        assert result["code"] == "test-auth-code-xyz"

    @pytest.mark.asyncio
    async def test_raises_on_error_callback(self, mock_web_config):
        """Listener raises AuthError when callback carries an error."""
        import threading
        import urllib.error
        import urllib.request

        auth = AuthManager(mock_web_config)
        result = {"error": None}

        def run_listener():
            try:
                auth._wait_for_callback(19877, timeout=5.0)
            except AuthError as e:
                result["error"] = str(e)

        listener_thread = threading.Thread(target=run_listener)
        listener_thread.start()

        import time

        time.sleep(0.2)

        try:
            urllib.request.urlopen(
                "http://127.0.0.1:19877/callback?error=access_denied&error_description=User+denied"
            )
        except urllib.error.HTTPError:
            pass  # Expected — server returns 400 for error callbacks

        listener_thread.join(timeout=5.0)
        await auth.close()

        assert "Authorization denied" in result["error"]
        assert "User denied" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, mock_web_config):
        """Listener raises AuthError on timeout."""
        auth = AuthManager(mock_web_config)
        with pytest.raises(AuthError, match="Timed out"):
            auth._wait_for_callback(19878, timeout=0.5)
        await auth.close()

    def test_port_from_redirect_uri(self, mock_web_config):
        """Extracts port from redirect URI."""
        auth = AuthManager(mock_web_config)
        # mock_web_config has redirect_uri=http://localhost:8080/oauth/callback
        assert auth._port_from_redirect_uri() == 8080

    def test_port_from_redirect_uri_default(self):
        """Falls back to port 8080 when no port specified."""
        config = AcceloConfig(
            deployment="test",
            client_id="id",
            client_secret="secret",
            auth_type="web",
            scope="read(all)",
            redirect_uri="http://localhost/callback",
        )
        auth = AuthManager(config)
        assert auth._port_from_redirect_uri() == 8080

    @pytest.mark.asyncio
    async def test_port_from_redirect_uri_missing(self, mock_installed_config):
        """Raises AuthError when no redirect_uri configured."""
        auth = AuthManager(mock_installed_config)
        with pytest.raises(AuthError, match="redirect_uri is required"):
            auth._port_from_redirect_uri()
        await auth.close()


class TestWebFlowAutoCallback:
    """Tests for web application flow with auto-callback."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_web_flow_uses_callback_listener(self, mock_web_config):
        """Web flow opens browser and listens for callback."""
        respx.post(f"{mock_web_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "web-callback-token",
                    "refresh_token": "web-refresh",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_web_config)
        with patch.object(AuthManager, "_wait_for_callback", return_value="callback-code"):
            with patch("accelo_mcp.auth.webbrowser.open") as mock_browser:
                token = await auth.get_token()

        await auth.close()

        assert token == "web-callback-token"
        mock_browser.assert_called_once()
        # Verify the auth URL was opened
        opened_url = mock_browser.call_args[0][0]
        assert "client_id=" in opened_url
        assert "response_type=code" in opened_url


class TestCallbackListenerLifecycle:
    """Tests for the #14 listener lifecycle: port freeing, bind failure, late callback."""

    @pytest.mark.asyncio
    async def test_port_is_freed_after_timeout(self, mock_web_config):
        """A timed-out wait releases the redirect port so it can be rebound."""
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        port = 19881
        auth = AuthManager(mock_web_config)
        result = {"error": None}

        def run_listener():
            try:
                auth._wait_for_callback(port, timeout=0.3)
            except AuthError as e:
                result["error"] = str(e)

        listener_thread = threading.Thread(target=run_listener)
        listener_thread.start()
        listener_thread.join(timeout=5.0)
        await auth.close()

        assert listener_thread.is_alive() is False
        assert "Timed out" in result["error"]

        # The port must now be free to rebind.
        server = HTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
        server.server_close()

    @pytest.mark.asyncio
    async def test_second_attempt_after_timeout_succeeds(self, mock_web_config):
        """A retry on the same port after a timeout captures a code without hanging."""
        import threading
        import time
        import urllib.request

        port = 19882
        auth = AuthManager(mock_web_config)

        # First attempt times out.
        with pytest.raises(AuthError, match="Timed out"):
            auth._wait_for_callback(port, timeout=0.3)

        # Second attempt on the same port must start and capture a code.
        result = {}

        def run_listener():
            result["code"] = auth._wait_for_callback(port, timeout=5.0)

        listener_thread = threading.Thread(target=run_listener)
        listener_thread.start()
        time.sleep(0.2)
        urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?code=retry-code")
        listener_thread.join(timeout=5.0)
        await auth.close()

        assert result["code"] == "retry-code"

    @pytest.mark.asyncio
    async def test_bind_failure_raises_autherror_not_hang(self, mock_web_config):
        """A pre-bound port surfaces as AuthError within a bounded time, never hangs."""
        from http.server import BaseHTTPRequestHandler, HTTPServer

        port = 19883
        blocker = HTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
        auth = AuthManager(mock_web_config)
        try:
            with pytest.raises(AuthError, match="bind|in use|still hold"):
                await asyncio.wait_for(
                    asyncio.to_thread(auth._wait_for_callback, port, 5.0),
                    timeout=3.0,
                )
        finally:
            blocker.server_close()
            await auth.close()

    @pytest.mark.asyncio
    async def test_late_callback_not_reported_as_success(self, mock_web_config):
        """A callback arriving after the timeout hits a closed port, not a success page."""
        import urllib.error
        import urllib.request

        port = 19884
        auth = AuthManager(mock_web_config)

        with pytest.raises(AuthError, match="Timed out"):
            auth._wait_for_callback(port, timeout=0.3)

        # The listener is gone, so a late callback cannot connect.
        with pytest.raises((urllib.error.URLError, ConnectionError)):
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/callback?code=late", timeout=2.0
            )
        await auth.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_web_flow_dispatches_wait_off_event_loop(self, mock_web_config):
        """The web flow awaits the blocking wait via asyncio.to_thread (issue #14)."""
        respx.post(f"{mock_web_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "offloop-token", "expires_in": 3600},
            )
        )

        auth = AuthManager(mock_web_config)
        real_to_thread = asyncio.to_thread
        observed = {}

        async def spy_to_thread(func, *args, **kwargs):
            observed["func"] = func
            return await real_to_thread(func, *args, **kwargs)

        with patch.object(AuthManager, "_wait_for_callback", return_value="code") as m:
            with patch("accelo_mcp.auth.webbrowser.open"):
                with patch("accelo_mcp.auth.asyncio.to_thread", side_effect=spy_to_thread):
                    token = await auth.get_token()
        await auth.close()

        assert token == "offloop-token"
        assert observed["func"] == m


class TestInstalledFlowTTY:
    """Tests for the #14 installed/TTY PIN-prompt guard."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_installed_flow_refuses_when_stdin_not_tty(self, mock_installed_config):
        """A non-TTY stdin raises AuthError and never reads the protocol stream."""
        import builtins
        import sys

        respx.post(f"{mock_installed_config.oauth2_url}/authorize").mock(
            return_value=httpx.Response(302, headers={"location": "https://approve.example"})
        )

        def boom(*args, **kwargs):
            raise AssertionError("input() must not be called when stdin is not a TTY")

        auth = AuthManager(mock_installed_config)
        with patch.object(sys.stdin, "isatty", return_value=False):
            with patch("accelo_mcp.auth.webbrowser.open"):
                with patch.object(builtins, "input", side_effect=boom):
                    with pytest.raises(AuthError, match="TTY|stdin"):
                        await auth.get_token()
        await auth.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_installed_flow_prompts_when_stdin_is_tty(self, mock_installed_config):
        """A TTY stdin prompts for the PIN once and exchanges it for a token."""
        import builtins
        import sys

        def side_effect(request):
            if str(request.url).endswith("/authorize"):
                return httpx.Response(302, headers={"location": "https://approve.example"})
            return httpx.Response(
                200, json={"access_token": "installed-token", "expires_in": 3600}
            )

        respx.post(f"{mock_installed_config.oauth2_url}/authorize").mock(side_effect=side_effect)
        respx.post(f"{mock_installed_config.oauth2_url}/token").mock(side_effect=side_effect)

        auth = AuthManager(mock_installed_config)
        with patch.object(sys.stdin, "isatty", return_value=True):
            with patch("accelo_mcp.auth.webbrowser.open"):
                with patch.object(builtins, "input", return_value="1234") as mock_input:
                    token = await auth.get_token()
        await auth.close()

        assert token == "installed-token"
        mock_input.assert_called_once()


class TestRefreshConcurrency:
    """Tests for the #15 refresh/acquire serialisation."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_concurrent_get_token_refreshes_once(self, mock_web_config):
        """Ten concurrent get_token() calls on an expired token refresh exactly once."""
        route = respx.post(f"{mock_web_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "concurrent-refreshed",
                    "refresh_token": "rotated-refresh",
                    "expires_in": 3600,
                },
            )
        )

        auth = AuthManager(mock_web_config)
        auth._token = "old-token"
        auth._refresh_token = "old-refresh"
        auth._expires_at = time.time() - 100  # expired

        results = await asyncio.gather(*[auth.get_token() for _ in range(10)])
        await auth.close()

        assert all(r == "concurrent-refreshed" for r in results)
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_concurrent_first_acquire_calls_token_endpoint_once(self, mock_config):
        """Ten concurrent first-acquire calls hit the token endpoint exactly once."""
        route = respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "acquired-once", "expires_in": 3600},
            )
        )

        auth = AuthManager(mock_config)
        results = await asyncio.gather(*[auth.get_token() for _ in range(10)])
        await auth.close()

        assert all(r == "acquired-once" for r in results)
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_refresh_lock_is_created_lazily(self, mock_config):
        """The refresh lock is None until the first get_token, an asyncio.Lock after."""
        respx.post(f"{mock_config.oauth2_url}/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        auth = AuthManager(mock_config)
        assert auth._refresh_lock is None
        await auth.get_token()
        await auth.close()

        assert isinstance(auth._refresh_lock, asyncio.Lock)

    @respx.mock
    @pytest.mark.asyncio
    async def test_refresh_keeps_token_when_concurrent_winner_rotated(self, mock_web_config):
        """invalid_grant only clears the refresh token when it still equals the sent one.

        Drives _refresh_token_flow directly: a non-invalid_grant failure never clears,
        and an invalid_grant failure after the stored token has been rotated by another
        caller does not clobber the newer token.
        """
        # Non-invalid_grant failure must never clear the token.
        respx.post(f"{mock_web_config.oauth2_url}/token").mock(
            return_value=httpx.Response(503, json={"error": "temporarily_unavailable"})
        )
        auth = AuthManager(mock_web_config)
        auth._refresh_token = "live-refresh"
        with pytest.raises(AuthError, match="Token refresh failed"):
            await auth._refresh_token_flow()
        assert auth._refresh_token == "live-refresh"
        await auth.close()

        # invalid_grant while the stored token has been rotated to a newer value
        # must leave the newer token untouched.
        def rotate_then_fail(request):
            auth2._refresh_token = "newer-refresh"
            return httpx.Response(400, json={"error": "invalid_grant"})

        respx.post(f"{mock_web_config.oauth2_url}/token").mock(side_effect=rotate_then_fail)
        auth2 = AuthManager(mock_web_config)
        auth2._refresh_token = "sent-refresh"
        with pytest.raises(AuthError, match="Token refresh failed"):
            await auth2._refresh_token_flow()
        assert auth2._refresh_token == "newer-refresh"
        await auth2.close()
