"""Tests for transport selection and HTTP transport settings."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock

import pytest
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

from accelo_mcp import server as server_module
from accelo_mcp.server import (
    HttpTransportSettings,
    _env_bool,
    main,
    run_sse,
    run_streamable_http,
    select_transport,
)


class TestSelectTransport:
    def test_defaults_to_stdio(self):
        assert select_transport(["accelo-mcp"]) == "stdio"

    def test_http_flag(self):
        assert select_transport(["accelo-mcp", "--http"]) == "http"

    def test_streamable_http_alias(self):
        assert select_transport(["accelo-mcp", "--streamable-http"]) == "http"

    def test_sse_flag(self):
        assert select_transport(["accelo-mcp", "--sse"]) == "sse"

    def test_conflicting_flags_exit(self):
        # --sse --http is now an error (mutually-exclusive group), not "http wins".
        with pytest.raises(SystemExit) as exc:
            select_transport(["accelo-mcp", "--sse", "--http"])
        assert exc.value.code == 2

    def test_unknown_flag_exits(self):
        with pytest.raises(SystemExit) as exc:
            select_transport(["accelo-mcp", "--htpp"])
        assert exc.value.code == 2

    def test_unknown_positional_exits(self):
        # parse_args (not parse_known_args) rejects a stray positional.
        with pytest.raises(SystemExit) as exc:
            select_transport(["accelo-mcp", "foo"])
        assert exc.value.code == 2

    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as exc:
            select_transport(["accelo-mcp", "--help"])
        assert exc.value.code == 0


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

    def test_host_is_stripped_in_from_env(self, monkeypatch):
        # Whitespace must be stripped once in from_env so the checked value
        # equals the value handed to the bind (otherwise " 127.0.0.1" passes
        # the loopback check then fails at bind, after create_server()).
        monkeypatch.setenv("ACCELO_MCP_HOST", "  127.0.0.1  ")
        assert HttpTransportSettings.from_env().host == "127.0.0.1"

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

    # --- Strict boolean parsing (moved from TestTransportSecurity + extended) ---

    @pytest.mark.parametrize("value,expected", [("1", True), ("0", False), ("TRUE", True)])
    def test_bool_parsing(self, monkeypatch, value, expected):
        monkeypatch.setenv("ACCELO_MCP_STATELESS", value)
        assert HttpTransportSettings.from_env().stateless is expected

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", "on", "ON"])
    def test_full_true_vocabulary(self, monkeypatch, value):
        monkeypatch.setenv("ACCELO_MCP_STATELESS", value)
        assert HttpTransportSettings.from_env().stateless is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "No", "off", "OFF"])
    def test_full_false_vocabulary(self, monkeypatch, value):
        monkeypatch.setenv("ACCELO_MCP_STATELESS", value)
        assert HttpTransportSettings.from_env().stateless is False

    def test_bool_typo_rejected(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_STATELESS", "ture")
        with pytest.raises(ValueError, match="ACCELO_MCP_STATELESS"):
            HttpTransportSettings.from_env()

    def test_blank_bool_rejected_on_stateless(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_STATELESS", "")
        with pytest.raises(ValueError, match="ACCELO_MCP_STATELESS"):
            HttpTransportSettings.from_env()

    def test_blank_bool_rejected_on_json_response(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_JSON_RESPONSE", "")
        with pytest.raises(ValueError, match="ACCELO_MCP_JSON_RESPONSE"):
            HttpTransportSettings.from_env()

    def test_env_bool_unset_uses_default(self, monkeypatch):
        monkeypatch.delenv("ACCELO_MCP_STATELESS", raising=False)
        assert _env_bool("ACCELO_MCP_STATELESS") is False
        assert _env_bool("ACCELO_MCP_STATELESS", default=True) is True

    # --- Path validation (ACCELO_MCP_PATH) ---

    def test_path_without_leading_slash_rejected(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_PATH", "mcp")
        with pytest.raises(ValueError, match="ACCELO_MCP_PATH"):
            HttpTransportSettings.from_env()

    def test_empty_path_rejected(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_PATH", "")
        with pytest.raises(ValueError, match="ACCELO_MCP_PATH"):
            HttpTransportSettings.from_env()

    def test_valid_path_accepted(self, monkeypatch):
        monkeypatch.setenv("ACCELO_MCP_PATH", "/accelo")
        assert HttpTransportSettings.from_env().path == "/accelo"


class TestTransportSecurity:
    def test_defaults_to_explicit_loopback_allow_list(self):
        # Never None: a default (loopback) bind gets explicit settings with the
        # loopback allow-list, so protection does not depend on the library
        # matching a hard-coded host string.
        settings = HttpTransportSettings()
        security = settings.transport_security()
        assert security is not None
        assert security.enable_dns_rebinding_protection is True
        assert security.allowed_hosts == ["127.0.0.1:*", "localhost:*", "[::1]:*"]
        assert security.allowed_origins == [
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ]

    def test_non_standard_loopback_still_gets_protection(self):
        # 127.0.0.5 is loopback but NOT one of the library's three auto-enable
        # strings — our explicit settings keep protection on for it.
        security = HttpTransportSettings(host="127.0.0.5").transport_security()
        assert security.enable_dns_rebinding_protection is True
        assert security.allowed_hosts == ["127.0.0.1:*", "localhost:*", "[::1]:*"]

    def test_built_when_allow_hosts_set(self):
        settings = HttpTransportSettings(allowed_hosts=["mcp.example.com"])
        security = settings.transport_security()
        assert security is not None
        assert security.enable_dns_rebinding_protection is True
        assert security.allowed_hosts == ["mcp.example.com"]

    def test_origins_only_defaults_hosts_to_loopback(self):
        # Setting ONLY origins must not leave allowed_hosts empty (which would
        # 421 every request) — it defaults to the loopback host allow-list.
        settings = HttpTransportSettings(allowed_origins=["https://mcp.example.com"])
        security = settings.transport_security()
        assert security.enable_dns_rebinding_protection is True
        assert security.allowed_hosts == ["127.0.0.1:*", "localhost:*", "[::1]:*"]
        assert security.allowed_origins == ["https://mcp.example.com"]

    def test_hosts_only_defaults_origins_to_loopback(self):
        settings = HttpTransportSettings(allowed_hosts=["mcp.example.com:*"])
        security = settings.transport_security()
        assert security.allowed_hosts == ["mcp.example.com:*"]
        assert security.allowed_origins == [
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ]

    def test_built_when_protection_disabled(self):
        settings = HttpTransportSettings(disable_dns_rebinding_protection=True)
        security = settings.transport_security()
        assert security is not None
        assert security.enable_dns_rebinding_protection is False


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


class TestRebindingGap:
    def test_loopback_has_no_gap(self):
        assert HttpTransportSettings(host="127.0.0.1").has_rebinding_gap() is False

    def test_non_loopback_no_allow_list_has_gap(self):
        settings = HttpTransportSettings(host="0.0.0.0", allow_unauthenticated=True)
        assert settings.has_rebinding_gap() is True

    def test_non_loopback_with_allow_hosts_has_no_gap(self):
        settings = HttpTransportSettings(
            host="0.0.0.0",
            allow_unauthenticated=True,
            allowed_hosts=["mcp.example.com"],
        )
        assert settings.has_rebinding_gap() is False

    def test_non_loopback_origins_only_still_has_gap(self):
        # DNS-rebinding is a Host-header attack; an Origin allow-list alone does
        # not close it (and would 421 everything), so the gap persists.
        settings = HttpTransportSettings(
            host="0.0.0.0",
            allow_unauthenticated=True,
            allowed_origins=["https://mcp.example.com"],
        )
        assert settings.has_rebinding_gap() is True

    def test_non_loopback_origins_only_refuses_at_startup(self):
        settings = HttpTransportSettings(
            host="0.0.0.0",
            allow_unauthenticated=True,
            allowed_origins=["https://mcp.example.com"],
        )
        with pytest.raises(RuntimeError, match="ACCELO_MCP_ALLOWED_HOSTS"):
            settings.enforce_startup_safety("Streamable HTTP")

    def test_non_loopback_protection_disabled_has_no_gap(self):
        # Operator explicitly turned the check off — a deliberate choice, not a gap.
        settings = HttpTransportSettings(
            host="0.0.0.0",
            allow_unauthenticated=True,
            disable_dns_rebinding_protection=True,
        )
        assert settings.has_rebinding_gap() is False

    def test_warns_unauth_but_refuses_on_empty_allow_list_when_opted_in(self):
        # Exposed bind, opt-in present, but no allow-list -> now a REFUSAL
        # (DNS-rebinding gap), not a warning.
        settings = HttpTransportSettings(host="0.0.0.0", allow_unauthenticated=True)
        with pytest.raises(RuntimeError, match="DNS-rebinding protection"):
            settings.enforce_startup_safety("Streamable HTTP")

    def test_rebinding_refusal_names_the_allow_list_and_disable_vars(self):
        settings = HttpTransportSettings(host="0.0.0.0", allow_unauthenticated=True)
        with pytest.raises(RuntimeError) as exc:
            settings.enforce_startup_safety("Streamable HTTP")
        message = str(exc.value)
        assert "ACCELO_MCP_ALLOWED_HOSTS" in message
        assert "ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION" in message

    def test_allow_list_set_starts_and_warns_unauthenticated(self, caplog):
        settings = HttpTransportSettings(
            host="0.0.0.0",
            allow_unauthenticated=True,
            allowed_hosts=["mcp.example.com"],
        )
        with caplog.at_level("WARNING"):
            settings.enforce_startup_safety("Streamable HTTP")
        # No rebinding refusal; unauthenticated warning still fires.
        assert any("NO inbound authentication" in r.message for r in caplog.records)
        assert not any("DNS-rebinding" in r.message for r in caplog.records)

    def test_explicit_disable_starts_despite_no_allow_list(self, caplog):
        # Operator deliberately turned the check off — allowed, not refused.
        settings = HttpTransportSettings(
            host="0.0.0.0",
            allow_unauthenticated=True,
            disable_dns_rebinding_protection=True,
        )
        with caplog.at_level("WARNING"):
            settings.enforce_startup_safety("Streamable HTTP")
        assert any("NO inbound authentication" in r.message for r in caplog.records)


class TestEnforceStartupSafety:
    def test_refuses_non_loopback_without_optin(self):
        settings = HttpTransportSettings(host="0.0.0.0")
        with pytest.raises(RuntimeError, match="Refusing to start"):
            settings.enforce_startup_safety("Streamable HTTP")

    def test_loopback_is_quiet(self, caplog):
        settings = HttpTransportSettings(host="127.0.0.1")
        with caplog.at_level("WARNING"):
            settings.enforce_startup_safety("Streamable HTTP")
        assert caplog.records == []


class TestMainRefusesBeforeAuth:
    """The exposure gate must run before create_server() on both HTTP paths.

    Pins the "refuse before auth" ordering: an accidental 0.0.0.0 bind must be
    rejected without ever constructing the server (which would trigger an
    interactive auth flow / network calls). create_server is monkeypatched to
    fail loudly if it is reached.
    """

    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        for var in (
            "ACCELO_MCP_HOST",
            "ACCELO_MCP_PORT",
            "ACCELO_MCP_ALLOW_UNAUTHENTICATED",
            "ACCELO_MCP_ALLOWED_HOSTS",
            "ACCELO_MCP_ALLOWED_ORIGINS",
            "ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION",
        ):
            monkeypatch.delenv(var, raising=False)

    def _boom(self, *args, **kwargs):
        raise AssertionError("create_server() must not be reached when the bind is refused")

    @pytest.mark.parametrize("flag", ["--http", "--sse"])
    def test_main_refuses_exposed_bind_before_create_server(self, monkeypatch, flag):
        monkeypatch.setenv("ACCELO_MCP_HOST", "0.0.0.0")
        monkeypatch.setattr(server_module, "create_server", self._boom)
        monkeypatch.setattr(sys, "argv", ["accelo-mcp", flag])

        # main() converts the refusal to a clean SystemExit (no traceback).
        with pytest.raises(SystemExit, match="Refusing to start"):
            main()

    @pytest.mark.parametrize("flag", ["--http", "--sse"])
    def test_main_refuses_rebinding_gap_before_create_server(self, monkeypatch, flag):
        # Opted in but no allow-list -> rebinding-gap refusal, still before auth.
        monkeypatch.setenv("ACCELO_MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("ACCELO_MCP_ALLOW_UNAUTHENTICATED", "true")
        monkeypatch.setattr(server_module, "create_server", self._boom)
        monkeypatch.setattr(sys, "argv", ["accelo-mcp", flag])

        with pytest.raises(SystemExit, match="DNS-rebinding protection"):
            main()

    def test_main_bad_port_exits_cleanly(self, monkeypatch):
        # The bad-port misconfiguration surfaces as a clean SystemExit too.
        monkeypatch.setenv("ACCELO_MCP_PORT", "not-a-number")
        monkeypatch.setattr(server_module, "create_server", self._boom)
        monkeypatch.setattr(sys, "argv", ["accelo-mcp", "--http"])

        with pytest.raises(SystemExit, match="ACCELO_MCP_PORT"):
            main()


def _build_healthz_app(transport_security=None):
    """Build a Streamable HTTP app carrying the /healthz route for testing.

    Registers the route the same way create_server() does (via custom_route),
    then builds the app — this exercises the real registration path without
    constructing a client or touching Accelo.
    """
    from mcp.server.mcpserver import MCPServer
    from starlette.responses import JSONResponse

    server = MCPServer("accelo-mcp-test")

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(request):
        return JSONResponse({"status": "ok"})

    return server.streamable_http_app(transport_security=transport_security)


class TestHealthz:
    def test_healthz_returns_200_json(self):
        client = TestClient(_build_healthz_app())
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["content-type"].startswith("application/json")

    def test_healthz_exempt_from_host_check(self):
        # A Host the allow-list would reject still reaches /healthz (it is a
        # sibling route, not wrapped by the session manager's Host check).
        ts = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*"],
            allowed_origins=["http://127.0.0.1:*"],
        )
        client = TestClient(_build_healthz_app(transport_security=ts))
        response = client.get("/healthz", headers={"Host": "10.0.0.3"})
        assert response.status_code == 200


class _DummyClient:
    async def close(self):
        return None


class TestMainStartupLog:
    """main() logs the effective HTTP security settings on startup."""

    @pytest.fixture(autouse=True)
    def _loopback_env(self, monkeypatch):
        for var in (
            "ACCELO_MCP_PATH",
            "ACCELO_MCP_JSON_RESPONSE",
            "ACCELO_MCP_STATELESS",
            "ACCELO_MCP_ALLOWED_HOSTS",
            "ACCELO_MCP_ALLOWED_ORIGINS",
            "ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION",
            "ACCELO_MCP_ALLOW_UNAUTHENTICATED",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ACCELO_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("ACCELO_MCP_PORT", "3000")
        # Neither serve nor construct a real server.
        monkeypatch.setattr(server_module.asyncio, "run", lambda coro: coro.close())
        monkeypatch.setattr(
            server_module,
            "create_server",
            lambda: (object(), _DummyClient()),
        )

    def test_http_log_includes_security_settings(self, monkeypatch, caplog):
        monkeypatch.setattr(sys, "argv", ["accelo-mcp", "--http"])
        with caplog.at_level("INFO"):
            main()
        matches = [
            r.message
            for r in caplog.records
            if "Streamable HTTP" in r.message and r.levelname == "INFO"
        ]
        assert matches, "expected an INFO startup record for Streamable HTTP"
        message = matches[0]
        assert "dns_rebinding_protection=True" in message
        assert "allowed_hosts=" in message
        assert "allowed_origins=" in message

    def test_sse_log_includes_security_settings(self, monkeypatch, caplog):
        monkeypatch.setattr(sys, "argv", ["accelo-mcp", "--sse"])
        with caplog.at_level("WARNING"):
            main()
        matches = [
            r.message for r in caplog.records if "SSE" in r.message and r.levelname == "WARNING"
        ]
        assert matches, "expected a WARNING startup record for SSE"
        message = matches[0]
        assert "dns_rebinding_protection=" in message
        assert "allowed_hosts=" in message
        assert "allowed_origins=" in message
        assert "127.0.0.1:3000" in message


class TestRunTransports:
    """Pins the kwargs each transport passes to the MCP library."""

    async def test_streamable_http_passes_full_kwargs(self, monkeypatch):
        mock_run = AsyncMock()
        monkeypatch.setattr(server_module.MCPServer, "run_streamable_http_async", mock_run)
        monkeypatch.setattr(
            server_module,
            "create_server",
            lambda: (server_module.MCPServer("t"), _DummyClient()),
        )
        settings = HttpTransportSettings(
            host="127.0.0.5",
            port=8081,
            path="/accelo",
            stateless=True,
            json_response=True,
        )

        await run_streamable_http(settings)

        kwargs = mock_run.call_args.kwargs
        assert kwargs["host"] == "127.0.0.5"
        assert kwargs["port"] == 8081
        assert kwargs["streamable_http_path"] == "/accelo"
        assert kwargs["json_response"] is True
        assert kwargs["stateless_http"] is True
        ts = settings.transport_security()
        assert kwargs["transport_security"].allowed_hosts == ts.allowed_hosts
        assert (
            kwargs["transport_security"].enable_dns_rebinding_protection
            is ts.enable_dns_rebinding_protection
        )

    async def test_sse_passes_security_only(self, monkeypatch):
        mock_run = AsyncMock()
        monkeypatch.setattr(server_module.MCPServer, "run_sse_async", mock_run)
        monkeypatch.setattr(
            server_module,
            "create_server",
            lambda: (server_module.MCPServer("t"), _DummyClient()),
        )
        settings = HttpTransportSettings(host="127.0.0.1", port=3000, path="/accelo")

        await run_sse(settings)

        kwargs = mock_run.call_args.kwargs
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 3000
        assert "transport_security" in kwargs
        assert "streamable_http_path" not in kwargs
        assert "json_response" not in kwargs
        assert "stateless_http" not in kwargs
