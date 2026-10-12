## ⚠️ Security release — action required for networked (`--http` / `--sse`) deployments

This release closes two issues in the HTTP/SSE transports. **If you only use the
default stdio transport, or bind to loopback (`127.0.0.1` / `localhost` / `::1`),
nothing changes and no action is needed.** If you bind a non-loopback host, the
server now refuses to start until you complete the migration below.

A GitHub Security Advisory accompanies this release — see the Security tab.

### What was wrong
- **No inbound authentication on an exposed bind.** The HTTP/SSE transport serves
  every caller with the server's single shared Accelo `write(all)` identity, so
  anyone who could reach a non-loopback port had full Accelo access. The previous
  README example recommended `ACCELO_MCP_HOST=0.0.0.0`, so this could happen without
  the operator realising. (CWE-306)
- **DNS-rebinding exposure.** Even a loopback-*published* deployment (container port
  mapped to `127.0.0.1` on the host) could be driven by a malicious web page in the
  operator's own browser, because Host/Origin rebinding protection was silently off
  for anything other than the exact hosts `127.0.0.1` / `localhost` / `::1`. (CWE-350)

### What changed
- A non-loopback bind now **refuses to start** without an explicit opt-in.
- `transport_security()` always enables explicit Host/Origin protection, so
  non-standard loopback binds (e.g. `127.0.0.5`) are covered too — no more silent-off.
- Refused starts print a clean remediation message (no traceback).

## 🔧 Migration — non-loopback (`--http` / `--sse`) deployments only

A deployment that binds a non-loopback host (e.g. `ACCELO_MCP_HOST=0.0.0.0`, including
a container that publishes its port to `127.0.0.1` on the host) must now set **both**:

1. `ACCELO_MCP_ALLOW_UNAUTHENTICATED=true`
   — acknowledge the transport has no inbound authentication.
2. `ACCELO_MCP_ALLOWED_HOSTS=<host:*>`
   — a Host allow-list so DNS-rebinding protection stays on. Matching is **exact**
   unless an entry ends in `:*`, and clients send the port, so use the `host:*` form:
   - loopback-published container: `ACCELO_MCP_ALLOWED_HOSTS=127.0.0.1:*,localhost:*`
   - behind a proxy forwarding a hostname: `ACCELO_MCP_ALLOWED_HOSTS=your-host:*`
   - non-standard loopback bind (`127.0.0.5`): `ACCELO_MCP_ALLOWED_HOSTS=127.0.0.5:*`

   An `ACCELO_MCP_ALLOWED_ORIGINS` list **alone does not satisfy** this — rebinding is
   a Host-header attack.

If you genuinely want no Host/Origin check and rely on your own network controls, set
`ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION=true` instead of step 2.

**Loopback (default) deployments need none of this.** See `SECURITY.md` for the full
deployment model and threat description.

## What's Changed
* feat(server)!: gate accidental unauthenticated and DNS-rebinding-exposed HTTP binds by @SelerityMichael in https://github.com/Selerity/accelo-mcp/pull/17

**Full Changelog**: https://github.com/Selerity/accelo-mcp/compare/v0.3.0...v0.4.0
