"""Guard against the package version and `__version__` drifting apart.

`src/accelo_mcp/__init__.py` derives `__version__` from installed package metadata,
which is itself built from `pyproject.toml`. This test pins the invariant so a future
version bump in one place but not the other fails loudly instead of shipping silently.
"""

import tomllib
from pathlib import Path

import accelo_mcp

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _pyproject_version() -> str:
    with _PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_dunder_version_matches_pyproject() -> None:
    assert accelo_mcp.__version__ == _pyproject_version()
