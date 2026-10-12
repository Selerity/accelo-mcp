"""Tests for transport selection and HTTP transport settings."""

from __future__ import annotations

import pytest

from accelo_mcp.server import HttpTransportSettings, select_transport


class TestSelectTransport:
    def test_defaults_to_stdio(self):
        assert select_transport(["accelo-mcp"]) == "stdio"

    def test_http_flag(self):
        assert select_transport(["accelo-mcp", "--http"]) == "http"

    def test_streamable_http_alias(self):
        assert select_transport(["accelo-mcp", "--streamable-http"]) == "http"

    def test_sse_flag(self):
        assert select_transport(["accelo-mcp", "--sse"]) == "sse"

    def test_http_wins_over_sse(self):
        assert select_transport(["accelo-mcp", "--sse", "--http"]) == "http"


class TestHttpTransportSettings:
    def test_defaults_bind_localhost(self, monkeypatch):
        for var in (
            "ACCELO_MCP_HOST",
            "ACCELO_MCP_PORT",
            "ACCELO_MCP_PATH",
            "ACCELO_MCP_JSON_RESPONSE",
            "ACCELO_MCP_STATELESS",
            "ACCELO_MCP_ALLOWED_HOSTS",
            "ACCELO_MCP_ALLOWED_ORIGINS",
            "ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION",
            "ACCELO_MCP_ALLOW_UNAUTHENTICATED",
        ):
            monkeypatch.delenv(var, raising=False)

        settings = HttpTransportSettings.from_env()

        assert settings.host == "127.0.0.1"
        assert settings.port == 3000
        assert settings.path == "/mcp"
        assert settings.json_response is False
        assert settings.stateless is False
        assert settings.allowed_hosts is None
        assert settings.allowed_origins is None
        assert settings.disable_dns_rebinding_protection is False
        assert settings.allow_unauthenticated is False

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("ACCELO_MCP_PORT", "8080")
        monkeypatch.setenv("ACCELO_MCP_PATH", "/accelo")
        monkeypatch.setenv("ACCELO_MCP_JSON_RESPONSE", "true")
        monkeypatch.setenv("ACCELO_MCP_STATELESS", "yes")

        settings = HttpTransportSettings.from_env()

        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.path == "/accelo"
        assert settings.json_response is True
        assert settings.stateless is True

    def test_allow_lists_parse_csv(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_ALLOWED_HOSTS", "mcp.example.com, example.com")
        monkeypatch.setenv("ACCELO_MCP_ALLOWED_ORIGINS", "https://example.com")

        settings = HttpTransportSettings.from_env()

        assert settings.allowed_hosts == ["mcp.example.com", "example.com"]
        assert settings.allowed_origins == ["https://example.com"]

    def test_empty_allow_list_is_none(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_ALLOWED_HOSTS", " , ")
        settings = HttpTransportSettings.from_env()
        assert settings.allowed_hosts is None

    def test_invalid_port_raises(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_PORT", "not-a-number")
        with pytest.raises(ValueError, match="ACCELO_MCP_PORT"):
            HttpTransportSettings.from_env()

    def test_out_of_range_port_raises(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_PORT", "70000")
        with pytest.raises(ValueError, match="between 1 and 65535"):
            HttpTransportSettings.from_env()

    def test_unset_port_uses_default(self, monkeypatch):
        monkeypatch.delenv("ACCELO_MCP_PORT", raising=False)
        assert HttpTransportSettings.from_env().port == 3000


class TestTransportSecurity:
    def test_none_when_all_defaults(self):
        settings = HttpTransportSettings()
        assert settings.transport_security() is None

    def test_built_when_allow_hosts_set(self):
        settings = HttpTransportSettings(allowed_hosts=["mcp.example.com"])
        security = settings.transport_security()
        assert security is not None
        assert security.enable_dns_rebinding_protection is True
        assert security.allowed_hosts == ["mcp.example.com"]

    def test_built_when_protection_disabled(self):
        settings = HttpTransportSettings(disable_dns_rebinding_protection=True)
        security = settings.transport_security()
        assert security is not None
        assert security.enable_dns_rebinding_protection is False

    @pytest.mark.parametrize("value,expected", [("1", True), ("0", False), ("TRUE", True)])
    def test_bool_parsing(self, monkeypatch, value, expected):
        monkeypatch.setenv("ACCELO_MCP_STATELESS", value)
        assert HttpTransportSettings.from_env().stateless is expected


class TestLoopbackDetection:
    @pytest.mark.parametrize(
        "host,expected",
        [
            ("127.0.0.1", True),
            ("127.0.0.5", True),
            ("::1", True),
            ("localhost", True),
            ("0.0.0.0", False),
            ("::", False),
            ("192.168.1.10", False),
            ("10.0.0.3", False),
            ("mcp.example.com", False),
        ],
    )
    def test_is_loopback_bind(self, host, expected):
        assert HttpTransportSettings(host=host).is_loopback_bind() is expected


class TestExposureGate:
    def test_loopback_without_optin_is_allowed(self):
        # Default bind is loopback — no opt-in required, no error.
        HttpTransportSettings(host="127.0.0.1").check_exposure_allowed()

    def test_ipv6_loopback_without_optin_is_allowed(self):
        HttpTransportSettings(host="::1").check_exposure_allowed()

    def test_non_loopback_without_optin_refuses(self):
        settings = HttpTransportSettings(host="0.0.0.0")
        with pytest.raises(RuntimeError, match="Refusing to start"):
            settings.check_exposure_allowed()

    def test_non_loopback_error_names_the_optin_var(self):
        settings = HttpTransportSettings(host="0.0.0.0")
        with pytest.raises(RuntimeError, match="ACCELO_MCP_ALLOW_UNAUTHENTICATED"):
            settings.check_exposure_allowed()

    def test_non_loopback_with_optin_is_allowed(self):
        # Intentional exposed bind: opt-in present, so startup proceeds.
        HttpTransportSettings(host="0.0.0.0", allow_unauthenticated=True).check_exposure_allowed()

    def test_hostname_without_optin_refuses(self):
        # A non-IP hostname is treated as non-loopback (fail safe).
        settings = HttpTransportSettings(host="mcp.example.com")
        with pytest.raises(RuntimeError):
            settings.check_exposure_allowed()

    def test_optin_loaded_from_env(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_ALLOW_UNAUTHENTICATED", "true")
        assert HttpTransportSettings.from_env().allow_unauthenticated is True
