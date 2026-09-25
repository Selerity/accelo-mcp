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
| `ACCELO_MCP_PORT` | No | `3000` | Port used by the SSE transport |

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

The server also supports SSE transport:

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
2. On merge, the **Release** workflow (`.github/workflows/release.yml`) detects the
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
Trusted Publisher registered for this repository's `release.yml` workflow.

## Security

Please report suspected vulnerabilities privately. See [SECURITY.md](SECURITY.md) for the reporting process. Do not include credentials, customer data, or access tokens in an issue.

## License

MIT. See [LICENSE](LICENSE).
