"""Tests for accelo_mcp.auth module."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import httpx
import pytest
import respx

from accelo_mcp.auth import TOKEN_FILE, AuthError, AuthManager
from accelo_mcp.config import AcceloConfig


@pytest.fixture(autouse=True)
def clean_token_file():
    """Remove token file before and after each test."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    yield
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


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

        assert TOKEN_FILE.exists()
        data = json.loads(TOKEN_FILE.read_text())
        assert data["access_token"] == "persisted-token"
        assert data["deployment"] == "test-deployment"

    @respx.mock
    @pytest.mark.asyncio
    async def test_loads_cached_tokens(self, mock_config):
        """Loads valid cached tokens on startup."""
        # Pre-write token file
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(
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
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(
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

        assert TOKEN_FILE.exists()
        mode = TOKEN_FILE.stat().st_mode & 0o777
        assert mode == 0o600


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
