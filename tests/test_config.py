"""Tests for accelo_mcp.config module."""

from __future__ import annotations

import pytest

from accelo_mcp.config import AcceloConfig


class TestAcceloConfig:
    """Tests for AcceloConfig.from_env()."""

    def test_from_env_minimal(self, monkeypatch):
        """Loads with only required variables set (defaults to web auth)."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "planet-express")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "abc123@planet-express.accelo.com")
        monkeypatch.setenv("ACCELO_CLIENT_SECRET", "secret123")

        config = AcceloConfig.from_env()

        assert config.deployment == "planet-express"
        assert config.client_id == "abc123@planet-express.accelo.com"
        assert config.client_secret == "secret123"
        assert config.auth_type == "web"
        assert config.scope == "read(all)"
        assert config.redirect_uri == "http://localhost:9876/callback"

    def test_from_env_all_options(self, monkeypatch):
        """Loads with all variables set."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "planet-express")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "abc123@planet-express.accelo.com")
        monkeypatch.setenv("ACCELO_CLIENT_SECRET", "secret123")
        monkeypatch.setenv("ACCELO_AUTH_TYPE", "web")
        monkeypatch.setenv("ACCELO_SCOPE", "write(all)")
        monkeypatch.setenv("ACCELO_REDIRECT_URI", "http://localhost:8080/callback")

        config = AcceloConfig.from_env()

        assert config.auth_type == "web"
        assert config.scope == "write(all)"
        assert config.redirect_uri == "http://localhost:8080/callback"

    def test_missing_deployment(self, monkeypatch):
        """Raises ValueError when ACCELO_DEPLOYMENT is missing."""
        monkeypatch.delenv("ACCELO_DEPLOYMENT", raising=False)
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.setenv("ACCELO_CLIENT_SECRET", "secret")

        with pytest.raises(ValueError, match="ACCELO_DEPLOYMENT"):
            AcceloConfig.from_env()

    def test_missing_client_id(self, monkeypatch):
        """Raises ValueError when ACCELO_CLIENT_ID is missing."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.delenv("ACCELO_CLIENT_ID", raising=False)
        monkeypatch.setenv("ACCELO_CLIENT_SECRET", "secret")

        with pytest.raises(ValueError, match="ACCELO_CLIENT_ID"):
            AcceloConfig.from_env()

    def test_missing_client_secret(self, monkeypatch):
        """Raises ValueError when ACCELO_CLIENT_SECRET is missing."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.delenv("ACCELO_CLIENT_SECRET", raising=False)

        with pytest.raises(ValueError, match="ACCELO_CLIENT_SECRET"):
            AcceloConfig.from_env()

    def test_invalid_auth_type(self, monkeypatch):
        """Raises ValueError for invalid auth type."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.setenv("ACCELO_CLIENT_SECRET", "secret")
        monkeypatch.setenv("ACCELO_AUTH_TYPE", "invalid")

        with pytest.raises(ValueError, match="ACCELO_AUTH_TYPE must be"):
            AcceloConfig.from_env()

    def test_web_auth_defaults_redirect_uri(self, monkeypatch):
        """Web auth type auto-defaults redirect URI when not explicitly set."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.setenv("ACCELO_CLIENT_SECRET", "secret")
        monkeypatch.setenv("ACCELO_AUTH_TYPE", "web")
        monkeypatch.delenv("ACCELO_REDIRECT_URI", raising=False)

        config = AcceloConfig.from_env()
        assert config.redirect_uri == "http://localhost:9876/callback"

    def test_installed_auth_no_redirect_uri_ok(self, monkeypatch):
        """Installed auth type works without redirect URI."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.setenv("ACCELO_CLIENT_SECRET", "secret")
        monkeypatch.setenv("ACCELO_AUTH_TYPE", "installed")
        monkeypatch.delenv("ACCELO_REDIRECT_URI", raising=False)

        config = AcceloConfig.from_env()
        assert config.auth_type == "installed"
        assert config.redirect_uri is None

    def test_public_auth_no_secret_required(self, monkeypatch):
        """Public auth type works without client secret."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.delenv("ACCELO_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("ACCELO_AUTH_TYPE", "public")
        monkeypatch.setenv("ACCELO_REDIRECT_URI", "http://localhost:8080/callback")

        config = AcceloConfig.from_env()
        assert config.auth_type == "public"
        assert config.client_secret is None
        assert config.redirect_uri == "http://localhost:8080/callback"

    def test_public_auth_requires_redirect_uri(self, monkeypatch):
        """Raises ValueError when public auth type lacks redirect URI."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.delenv("ACCELO_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("ACCELO_AUTH_TYPE", "public")
        monkeypatch.delenv("ACCELO_REDIRECT_URI", raising=False)

        with pytest.raises(ValueError, match="ACCELO_REDIRECT_URI is required"):
            AcceloConfig.from_env()

    def test_missing_client_secret_non_public(self, monkeypatch):
        """Raises ValueError when client_secret is missing for non-public types."""
        monkeypatch.setenv("ACCELO_DEPLOYMENT", "test")
        monkeypatch.setenv("ACCELO_CLIENT_ID", "id")
        monkeypatch.delenv("ACCELO_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("ACCELO_AUTH_TYPE", "service")

        with pytest.raises(ValueError, match="ACCELO_CLIENT_SECRET"):
            AcceloConfig.from_env()


class TestAcceloConfigProperties:
    """Tests for computed properties."""

    def test_base_url(self, mock_config):
        assert mock_config.base_url == "https://test-deployment.api.accelo.com/api/v0"

    def test_oauth2_url(self, mock_config):
        assert mock_config.oauth2_url == "https://test-deployment.api.accelo.com/oauth2/v0"
