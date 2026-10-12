# accelo-mcp

An unofficial [Model Context Protocol](https://modelcontextprotocol.io/) server for the [Accelo](https://www.accelo.com) CRM platform. It exposes Accelo data and operations to MCP-compatible AI assistants through the documented Accelo REST API.

> This project is not affiliated with or endorsed by Accelo. Users are responsible for their Accelo account, OAuth application, permissions, and data handling.

## Installation

### With `uvx`

The recommended installation for MCP hosts is:

```json
{
  "mcpServers": {
    "accelo": {
      "command": "uvx",
      "args": ["accelo-mcp"],
      "env": {
        "ACCELO_DEPLOYMENT": "your-deployment",
        "ACCELO_CLIENT_ID": "your-client-id",
        "ACCELO_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

To pin a release:

```json
"args": ["accelo-mcp==0.1.0"]
```

`uvx` installs the package into an isolated environment and runs the `accelo-mcp` command.

### With `pip`

```bash
python3 -m pip install accelo-mcp
accelo-mcp
```

### From source

```bash
git clone <repository-url>
cd accelo-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env`, or provide these variables through the MCP host:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ACCELO_DEPLOYMENT` | Yes | — | Deployment prefix, such as `example` for `example.accelo.com` |
| `ACCELO_CLIENT_ID` | Yes | — | OAuth2 client ID from an Accelo application |
| `ACCELO_CLIENT_SECRET` | Depends on auth type | — | OAuth2 client secret; not required for public PKCE applications |
| `ACCELO_AUTH_TYPE` | No | `web` | `web`, `service`, `installed`, or `public` |
| `ACCELO_SCOPE` | No | `read(all)` | OAuth2 scope; defaults to read-only. Add write access explicitly, e.g. `read(all),write(all)`, only if you need the write tools |
| `ACCELO_REDIRECT_URI` | For `web` and `public` | `http://localhost:9876/callback` (`web` only) | Local OAuth callback URL. Optional for `web` (defaults as shown); **required for `public`** with no default. Must exactly match the redirect URI registered on the Accelo application. |

HTTP transport variables (only used with `--http` or `--sse`):

> **Single-user scope.** The HTTP / SSE transports have **no inbound
> authentication** and act with one shared Accelo identity for every caller.
> This server is for a single operator; when running over HTTP it is your
> responsibility to ensure only the one intended user can reach it. See the
> fuller note under [Usage](#usage) and [`SECURITY.md`](SECURITY.md).

| Variable | Default | Description |
|----------|---------|-------------|
| `ACCELO_MCP_HOST` | `127.0.0.1` | Interface to bind. `127.0.0.1` keeps it local-only (recommended). Only set `0.0.0.0` inside a container, and publish the port to loopback on the host — see the single-user scope note above and [`SECURITY.md`](SECURITY.md). |
| `ACCELO_MCP_PORT` | `3000` | TCP port to listen on. |
| `ACCELO_MCP_PATH` | `/mcp` | Streamable HTTP endpoint path. |
| `ACCELO_MCP_JSON_RESPONSE` | `false` | Return a single JSON response instead of an SSE stream. |
| `ACCELO_MCP_STATELESS` | `false` | Run without per-session MCP protocol state. This only affects the transport-level session the MCP library tracks; it does **not** add per-user credentials — every request still uses the one shared Accelo identity (see the single-user scope note above). |
| `ACCELO_MCP_ALLOWED_HOSTS` | — | Comma-separated `Host` header allow-list for DNS-rebinding protection, e.g. your public hostname. Required when the server is reached through any hostname other than `localhost`. |
| `ACCELO_MCP_ALLOWED_ORIGINS` | — | Comma-separated `Origin` header allow-list. |
| `ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION` | `false` | Disable the `Host`/`Origin` check entirely. Prefer setting the allow-lists above instead. On a non-loopback bind, this is the explicit override that lets the server start with no allow-list (otherwise it refuses — see below). |
| `ACCELO_MCP_ALLOW_UNAUTHENTICATED` | `false` | Acknowledge that the HTTP transport has no inbound authentication. **Required to start on a non-loopback bind** (e.g. `0.0.0.0`); the server refuses to start on a non-loopback host without it, to prevent accidental exposure. On a non-loopback bind the server **also** requires `ACCELO_MCP_ALLOWED_HOSTS`/`ACCELO_MCP_ALLOWED_ORIGINS` (or an explicit `ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION=true`), otherwise it refuses because DNS-rebinding protection would be off. See [`SECURITY.md`](SECURITY.md). |

Create or obtain an OAuth application for the Accelo deployment you intend to access. Never commit client secrets, refresh tokens, access tokens, cookies, or webhook secrets.

### Authentication types

All four authentication types use OAuth 2.0. They differ in whether a person authorises interactively in a browser and whether a client secret is required.

| Auth type | OAuth 2.0 grant | Interactive browser login | Client secret | Typical use |
|-----------|-----------------|---------------------------|---------------|-------------|
| `web` | Authorisation Code + refresh token | Yes, once | Required | Individual users; the recommended default |
| `public` | Authorisation Code with PKCE + refresh token | **Yes, once** | **Not required** | Publicly distributed clients that cannot keep a secret |
| `installed` | Authorisation Code via PIN + refresh token | Yes (approve, then enter a PIN) | Required | Installed clients using Accelo's PIN approval |
| `service` | Client Credentials | **No** | Required | Server-to-server automation under a shared service identity |

Key points:

- **`public` still requires OAuth.** "Public" means no client secret is distributed, not that authentication is skipped. On first run the server opens your browser, you log in to Accelo and authorise, Accelo redirects back to a local `127.0.0.1` callback listener, and the server exchanges the authorisation code (using a PKCE `code_verifier`) for tokens. No client secret is ever sent.
- **`service` is the only non-interactive flow.** It authenticates as a service identity via the Client Credentials grant and never opens a browser. Every other type requires a one-time interactive authorisation.
- **After the first authorisation**, `web`, `public`, and `installed` cache a refresh token and reauthorise silently, so the browser step is not repeated on later runs.
- **The redirect URI must line up in three places** for `web` and `public`: the `ACCELO_REDIRECT_URI` you set, the port the local callback listener binds (derived from that URI, or `8080` if the URI has no explicit port), and the redirect URI registered on the Accelo application. Accelo rejects the authorisation request if its registered value does not match. For `public`, `ACCELO_REDIRECT_URI` is mandatory and has no default.

Tokens are cached locally at `~/.accelo-mcp/tokens.json` with restrictive file permissions. The local callback listener binds to `127.0.0.1` only.

## Usage

The default transport is stdio, which is suitable for Claude Desktop, Kiro, and other local MCP hosts:

```bash
accelo-mcp
```

For remote or networked hosts, run the server over **Streamable HTTP** (the current MCP HTTP transport):

```bash
accelo-mcp --http
```

This listens on `http://127.0.0.1:3000/mcp` by default.

> **Single-user scope.** This server has no inbound authentication and acts with
> one shared Accelo identity for every caller (see [`SECURITY.md`](SECURITY.md)).
> It is intended for a single operator. When running over HTTP, it is your
> responsibility to ensure only the one intended user can reach it — keep the
> bind on loopback, or restrict network access to that single client and set the
> Host/Origin allow-lists below. Do not expose the HTTP transport to an untrusted
> network.

If you must serve from inside a container or behind a reverse proxy, bind beyond
loopback **only** behind a network restriction that admits the single permitted
client, and allow-list the expected hostname so DNS-rebinding protection stays
active and does not reject proxied requests:

```bash
# Publish the container port to loopback on the host, not to all interfaces:
#   docker run -p 127.0.0.1:8080:8080 ...
# The allow-list below assumes a host-side reverse proxy that forwards with
# Host: mcp.internal.example; the 127.0.0.1:* / localhost:* entries keep a
# direct loopback request working (a custom allow-list REPLACES the library's
# loopback defaults, and matching is exact unless an entry ends in ":*").
ACCELO_MCP_HOST=0.0.0.0 \
ACCELO_MCP_PORT=8080 \
ACCELO_MCP_ALLOWED_HOSTS=mcp.internal.example,127.0.0.1:*,localhost:* \
ACCELO_MCP_ALLOWED_ORIGINS=https://mcp.internal.example \
ACCELO_MCP_ALLOW_UNAUTHENTICATED=true \
accelo-mcp --http
```

The server refuses to start on a non-loopback host unless you set
`ACCELO_MCP_ALLOW_UNAUTHENTICATED=true`, acknowledging that it has no inbound
authentication. This stops *accidental* exposure (an empty `ACCELO_MCP_HOST=`
value or a copied example); it does not block an intended exposed bind — you opt
in explicitly. On a non-loopback bind the server **also** requires a Host/Origin
allow-list (`ACCELO_MCP_ALLOWED_HOSTS`/`ACCELO_MCP_ALLOWED_ORIGINS`), as in the
example above — without one it refuses, because DNS-rebinding protection would
otherwise be off and the permitted user's browser becomes an attack vector. If
you truly want no `Host`/`Origin` check, set
`ACCELO_MCP_DISABLE_DNS_REBINDING_PROTECTION=true` explicitly. Here
`ACCELO_MCP_HOST=0.0.0.0` only binds all interfaces *inside* the container; the
`-p 127.0.0.1:8080:8080` publish is what keeps it reachable only from the host.
An IP restriction alone does not stop DNS-rebinding, so keep the Host/Origin
allow-list set regardless.

`ACCELO_MCP_STATELESS=true` runs the transport without per-session MCP protocol
state. This only affects the protocol-level session the MCP library tracks for
stream resumption; it does **not** add per-user credentials or make the server
multi-user — every request still uses the same single Accelo identity, so the
single-user scope in [`SECURITY.md`](SECURITY.md) still applies.

The older **SSE** transport is still available but deprecated; prefer `--http`
for new deployments:

```bash
accelo-mcp --sse
```

The server provides 219 tools covering companies, contacts, affiliations, activities, projects, tickets, tasks, retainers, sales, billing, time tracking, custom fields, resources, workflow progressions, and related Accelo objects.

For complex queries, call `accelo_get_context` first. It describes the Accelo object model, relationships, filtering conventions, pagination, and field selection syntax.

## Filtering and field selection

All list tools accept structured filters:

```python
{"standing": "active"}
{"date_created_after": 1690000000}
{"status": [1, 2, 3]}
{"order_by_desc": "date_modified"}
```

Request linked or optional fields with `fields`:

```text
website,phone
postal_address(city,state)
_ALL
```

## Development

```bash
make install  # install the package and development dependencies
make test     # run tests
make lint     # run Ruff checks
make audit    # audit Python dependencies for known vulnerabilities
make check    # run lint, tests, and dependency audit
make build    # build a wheel and source distribution
```

## Releasing

Releases are driven by the version in `pyproject.toml`. Bumping that version on
`main` is the only manual step; validation, tagging, the GitHub Release, and the
PyPI publish are automated by a single workflow.

1. Bump `version` in `pyproject.toml` (for example `0.1.0` to `0.2.0`) on a branch
   and merge it to `main` through a pull request. Follow semantic versioning.
2. On merge, the **Release** workflow (`.github/workflows/publish.yml`) detects the
   changed version and, in one run:
   - runs `make check` (lint, tests, and dependency audit),
   - creates the matching `v<version>` tag and a GitHub Release with generated
     notes, and
   - builds the wheel and source distribution and publishes them to PyPI via
     OIDC Trusted Publishing (no stored API token).

   The workflow is idempotent: if the version is unchanged since the previous
   commit, or the tag already exists on the remote, it does nothing.

Tagging and publishing live in the **same** workflow on purpose. A tag pushed by
the built-in `GITHUB_TOKEN` does not trigger a second workflow, so a separate
tag-triggered publish job would never run. Folding both into one push-triggered
workflow avoids that loop-guard.

To cut a release by hand, bump the version and push the tag yourself:

```bash
git tag v0.2.0   # must equal "v" + the pyproject.toml version
git push origin v0.2.0
```

Note that a hand-pushed tag alone does not publish (nothing is triggered by a tag
push); publishing happens through the version bump on `main`. The Release workflow
still verifies the tag equals `v` + the `pyproject.toml` version and fails if they
differ, so the tag and the package version cannot drift.

Publishing to PyPI requires a configured `pypi` GitHub environment and a PyPI
Trusted Publisher registered for this repository's `publish.yml` workflow. The
workflow file must stay named `publish.yml`: PyPI matches the trusted publisher on
the exact workflow filename, so renaming it breaks publishing even though the
workflow's display name is "Release".

## Security

Please report suspected vulnerabilities privately. See [SECURITY.md](SECURITY.md) for the reporting process. Do not include credentials, customer data, or access tokens in an issue.

## License

MIT. See [LICENSE](LICENSE).
