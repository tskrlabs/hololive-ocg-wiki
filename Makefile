# hololive-ocg-wiki — task runner.
#
# `make check` is the single verification entry point. It is what the pre-commit hook
# runs and what you should run before pushing.
#
# There is deliberately no CI: verification is local, by decision. Run `make hooks`
# once per clone to have `make check` run automatically before each commit.

.DEFAULT_GOAL := help
.PHONY: help setup hooks generate golden fixtures check check-schema check-py check-ts check-api check-web typecheck dev dev-api dev-web preview clean

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

check: check-schema check-py check-ts check-api check-web typecheck ## Run every verification
	@echo ""
	@echo "✓ all checks passed"

dev: ## Run the site and the API together (two processes, Ctrl-C stops both)
	@echo "→ API on :8787 (local D1 + fixtures), site on :3000"
	@echo "  the site proxies /api to the Worker — see apps/web/nuxt.config.ts"
	@trap 'kill 0' INT TERM; \
	 $(MAKE) --no-print-directory dev-api & \
	 $(MAKE) --no-print-directory dev-web & \
	 wait

dev-api: ## Just the Worker, on local D1 + R2 fixtures (no credentials)
	@cd apps/api && npm run db:local >/dev/null && ./scripts/seed-local-r2.sh
	@cd apps/api && npx wrangler dev --local --port 8787

dev-web: ## Just the site, with HMR
	@npm run dev --workspace @holo/web

preview: ## Rehearse production: generate the site and serve it from the Worker on one port
	@# The only thing that exercises the real SPA fallback and same-origin requests.
	@# `make dev` proxies /api, which is Nuxt's behaviour, not the Worker's — this is.
	@npm run generate --workspace @holo/web
	@cd apps/api && npm run db:local >/dev/null && ./scripts/seed-local-r2.sh
	@cd apps/api && npx wrangler dev --local --port 8787

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

check-web: ## Run the site's unit tests (the pure modules — ADR 0006)
	@npm test --workspace @holo/web --silent

typecheck: ## Typecheck the generated TypeScript, the Worker and the site
	@npm run typecheck --workspace @holo/schema --silent
	@npm run typecheck --workspace @holo/api --silent
	@# vue-tsc probes for `vue-router/volar/sfc-route-blocks`, which vue-router 5 no
	@# longer exports, and prints a full ERR_PACKAGE_PATH_NOT_EXPORTED stack before
	@# exiting 0 with no type errors. The plugin supports `<route>` blocks in SFCs, which
	@# Nuxt does not use — it derives routing from the file system. The trace is dropped
	@# so it cannot be mistaken for a failure; real errors still print, and a non-zero
	@# exit still fails the target.
	@npm run typecheck --workspace @holo/web --silent 2>&1 \
		| grep -v -e '^\[Vue\] Resolve plugin path failed' -e '^ *at ' -e "^ *code: 'ERR_PACKAGE_PATH_NOT_EXPORTED'" -e '^}$$' \
		; exit $${PIPESTATUS[0]}

clean: ## Remove caches and build artifacts (not generated output — that is committed)
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv node_modules packages/schema/node_modules
