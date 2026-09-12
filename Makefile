.PHONY: help test lint audit format build clean dev install check ci-test ci-lint ci-audit

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Setup ---

install: ## Install package in editable mode with dev dependencies
	pip install -e ".[dev]"

# --- Development ---

dev: ## Run MCP server in stdio mode (for local testing)
	accelo-mcp

dev-sse: ## Run the MCP server in SSE mode on port 8080
	ACCELO_MCP_PORT=8080 accelo-mcp --sse

# --- Quality ---

test: ## Run all tests
	pytest -q --tb=short

lint: ## Run linting checks (ruff check + format check)
	ruff check src/ tests/
	ruff format --check src/ tests/

audit: ## Audit Python dependencies for known vulnerabilities
	pip-audit --local --skip-editable

format: ## Auto-format code with ruff
	ruff check --fix src/ tests/
	ruff format src/ tests/

check: lint test audit ## Run lint, tests, and dependency audit (pre-push gate)

# --- Build & Package ---

build: clean ## Build wheel and sdist
	python3 -m build

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true

# --- CI ---

ci-test: ## Run tests with strict exit codes (CI)
	pytest -q --tb=short --strict-markers

ci-lint: ## Run lint checks (CI)
	ruff check src/ tests/
	ruff format --check src/ tests/

ci-audit: ## Run dependency vulnerability audit (CI)
	pip-audit --local --skip-editable
