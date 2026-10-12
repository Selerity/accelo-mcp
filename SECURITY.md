# Security policy

## Deployment scope and threat model

**This server is designed for single-user, single-operator use.** It holds one
set of Accelo credentials and acts with that single Accelo identity for every
request it serves. It has **no inbound authentication** of its own: it does not
authenticate the caller connecting to it, and it does not partition access by
user or by session. The OAuth flow (`web`, `public`, `installed`, `service`)
authenticates **the server to Accelo** — it does **not** authenticate anyone
*to the server*. A one-time browser login authorises the server to acquire a
token; it does not gate who may use that token afterwards.

As a result:

- **Treat the server as holding a live, shared Accelo credential.** Anyone able
  to reach its transport can invoke every tool with the server's full Accelo
  permissions (up to `write(all)` if so scoped). Grant the OAuth application the
  **least privilege** it needs — prefer `read(all)` over `write(all)` unless
  writes are genuinely required.
- **Prefer the default stdio transport.** Over stdio the server talks to a
  single local parent process, so operating-system process boundaries are the
  access control. This is the safe default and needs no extra hardening.
- **The HTTP / SSE transports are not multi-user.** If you run `--http` or
  `--sse`, it is **your responsibility as the operator** to ensure only the one
  intended user can reach it. At minimum:
  - keep the bind on loopback (`ACCELO_MCP_HOST=127.0.0.1`, the default) unless
    you have a specific reason not to;
  - if you must bind beyond loopback, restrict network access to the single
    permitted client (host firewall / security group / `127.0.0.1`-only Docker
    port publish, e.g. `-p 127.0.0.1:3000:3000`), and set
    `ACCELO_MCP_ALLOWED_HOSTS` / `ACCELO_MCP_ALLOWED_ORIGINS` so DNS-rebinding
    protection stays active;
  - never expose it directly to an untrusted network or the public internet.
- **An IP restriction alone does not stop DNS-rebinding.** That attack arrives
  through the authorised user's own browser, so the permitted client is the
  vector. Keep the Host/Origin allow-list set (or stay on loopback) in addition
  to any network restriction.

**Accidental exposure is refused at start-up.** Because binding beyond loopback
with no inbound authentication is a deliberate decision, the server refuses to
start on a non-loopback host unless you set `ACCELO_MCP_ALLOW_UNAUTHENTICATED=true`.
This prevents an *accidental* exposed bind (an empty `ACCELO_MCP_HOST=` value, or
a `0.0.0.0` example copied without thought); it does **not** prevent an *intended*
one — an operator who genuinely wants an exposed bind, and has their own network
controls, opts in explicitly with that variable and the server starts (logging a
warning). Loopback binds (the default) need no opt-in.

When the opt-in is used but no `ACCELO_MCP_ALLOWED_HOSTS` /
`ACCELO_MCP_ALLOWED_ORIGINS` allow-list is set, the server additionally logs a
warning that DNS-rebinding protection is off, because an exposed bind with no
allow-list leaves the permitted user's browser as an attack vector (see above).

Running the HTTP transport reachable by parties other than the single intended
user is outside the supported use of this project.

## Supported versions

Security fixes are made against the latest released version and the default branch.

## Reporting a vulnerability

Do not report security vulnerabilities in public issues. Email [security@selerity.com.au](mailto:security@selerity.com.au), or use GitHub's private vulnerability reporting on this repository (Security → Report a vulnerability). Include:

- the affected version or commit;
- a concise description of the issue;
- reproduction steps or a proof of concept;
- the potential impact.

Please do not include Accelo credentials, customer data, access tokens, refresh tokens, cookies, or other secrets in the report.

Allow reasonable time for investigation and remediation before publicly disclosing a vulnerability.
