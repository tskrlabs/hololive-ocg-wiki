# hololive-ocg-wiki

A fan-made wiki for the Hololive Official Card Game — card database, search, and deck
builder. This repo is a ground-up v2 rebuild.

**Read [`docs/progress.md`](docs/progress.md) first** — it says where the rebuild is, what
is next, and the working agreement. Then [`docs/v2-plan.md`](docs/v2-plan.md) for the full
design, and `docs/adr/` for decisions made during execution.

Data anomalies that need a human eye are logged in [`docs/findings.md`](docs/findings.md)
rather than fixed on the spot. Add to it rather than working around a surprise silently.

Verification is local — `make check`. **Never add GitHub Actions**; see progress.md.

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues in `tskrlabs/hololive-ocg-wiki`, driven by the
`gh` CLI. External PRs are also a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings, unmodified —
`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`.
See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` plus `docs/adr/` at the repo root, shared across all
workspaces. See `docs/agents/domain.md`.
