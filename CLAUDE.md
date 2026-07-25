# hololive-ocg-wiki

A fan-made wiki for the Hololive Official Card Game — card database, search, and deck
builder. This repo is a ground-up v2 rebuild; see [`docs/v2-plan.md`](docs/v2-plan.md)
for the full design, every decision and its reasoning, and the phase plan.

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
