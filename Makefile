# hololive-ocg-wiki — task runner.
#
# `make check` is the single verification entry point. It is what the pre-commit hook
# runs and what you should run before pushing.
#
# There is deliberately no CI: verification is local, by decision. Run `make hooks`
# once per clone to have `make check` run automatically before each commit.

.DEFAULT_GOAL := help
.PHONY: help setup hooks generate golden fixtures check check-schema check-py check-ts check-api typecheck clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python and Node dependencies
	uv sync
	npm install
	@echo ""
	@echo "Run 'make hooks' to enable the pre-commit check."

hooks: ## Enable the pre-commit hook (run once per clone)
	git config core.hooksPath scripts/hooks
	@echo "✓ pre-commit hook enabled — 'make check' now runs before each commit"
	@echo "  disable with: git config --unset core.hooksPath"

generate: ## Regenerate JSON Schema, TypeScript, D1 DDL and fixtures.sql
	uv run python packages/schema/scripts/generate.py
	uv run python packages/schema/scripts/generate_ddl.py
	uv run python packages/schema/scripts/generate_fixtures_sql.py

fixtures: ## Re-select the fixture card set (needs v1 data — see script docstring)
	uv run python packages/schema/scripts/build_fixtures.py

golden: ## Regenerate the localize() golden files from the Python reference
	uv run python packages/schema/scripts/golden.py

check: check-schema check-py check-ts check-api typecheck ## Run every verification
	@echo ""
	@echo "✓ all checks passed"

check-schema: ## Fail if the committed generated files are stale
	@uv run python packages/schema/scripts/generate.py --check
	@uv run python packages/schema/scripts/generate_ddl.py --check
	@uv run python packages/schema/scripts/generate_fixtures_sql.py --check

check-py: ## Run the Python tests (schema + pipeline)
	@uv run pytest packages/schema/tests pipeline/tests -q

check-ts: ## Run the TypeScript parity tests
	@npm test --workspace @holo/schema --silent

check-api: ## Run the Worker's unit tests and the endpoint smoke test
	@npm test --workspace @holo/api --silent
	@apps/api/tests/smoke.sh

typecheck: ## Typecheck the generated TypeScript and the Worker
	@npm run typecheck --workspace @holo/schema --silent
	@npm run typecheck --workspace @holo/api --silent

clean: ## Remove caches and build artifacts (not generated output — that is committed)
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv node_modules packages/schema/node_modules
