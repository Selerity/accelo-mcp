# Contributing

Thank you for contributing to `accelo-mcp`.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

Run the pre-push checks before opening a pull request:

```bash
make check
```

## Pull requests

- Keep changes focused and explain the user-facing impact.
- Add or update tests for behavioural changes.
- Do not include real Accelo data, customer identifiers, credentials, tokens, cookies, or deployment-specific material.
- Do not add internal documentation or configuration files to the public repository.
- Update the README when installation, configuration, or development commands change.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md) when participating in the project.
