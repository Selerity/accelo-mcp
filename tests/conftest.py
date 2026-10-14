"""Shared test fixtures for accelo-mcp tests."""

from __future__ import annotations

import pytest

from accelo_mcp import auth as auth_module
from accelo_mcp.config import AcceloConfig


@pytest.fixture(autouse=True)
def isolated_token_file(tmp_path, monkeypatch):
    """Point token storage at a temp directory so tests never touch ~/.accelo-mcp.

    The auth module resolves paths via _token_dir()/_token_file(), which read
    these globals at call time, so patching the globals is enough for isolation.
    """
    token_dir = tmp_path / ".accelo-mcp"
    monkeypatch.setattr(auth_module, "TOKEN_DIR", token_dir)
    monkeypatch.setattr(auth_module, "TOKEN_FILE", token_dir / "tokens.json")


@pytest.fixture
def mock_config() -> AcceloConfig:
    """A valid AcceloConfig for testing."""
    return AcceloConfig(
        deployment="test-deployment",
        client_id="test-client-id@test-deployment.accelo.com",
        client_secret="test-client-secret",
        auth_type="service",
        scope="read(all)",
        redirect_uri=None,
    )


@pytest.fixture
def mock_web_config() -> AcceloConfig:
    """A valid AcceloConfig for web auth type testing."""
    return AcceloConfig(
        deployment="test-deployment",
        client_id="test-client-id@test-deployment.accelo.com",
        client_secret="test-client-secret",
        auth_type="web",
        scope="read(all)",
        redirect_uri="http://localhost:8080/oauth/callback",
    )


@pytest.fixture
def mock_installed_config() -> AcceloConfig:
    """A valid AcceloConfig for installed auth type testing."""
    return AcceloConfig(
        deployment="test-deployment",
        client_id="test-client-id@test-deployment.accelo.com",
        client_secret="test-client-secret",
        auth_type="installed",
        scope="read(all)",
        redirect_uri=None,
    )


@pytest.fixture
def mock_public_config() -> AcceloConfig:
    """A valid AcceloConfig for public (PKCE) auth type testing."""
    return AcceloConfig(
        deployment="test-deployment",
        client_id="test-client-id@test-deployment.accelo.com",
        client_secret=None,
        auth_type="public",
        scope="read(all)",
        redirect_uri="http://localhost:8080/oauth/callback",
    )
