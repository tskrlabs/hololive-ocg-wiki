# hololive-ocg-wiki

A fan-made wiki for the Hololive Official Card Game — card database, search, and deck
builder. This repo is a ground-up v2 rebuild.

**Read [`docs/progress.md`](docs/progress.md) first** — it says where the rebuild is, what
is next, and the working agreement. Then [`docs/v2-plan.md`](docs/v2-plan.md) for the full
design, and `docs/adr/` for decisions made during execution.

Surprises are logged, not worked around silently — but **not into a file**. Something
needing a maintainer judgement becomes a GitHub issue (`needs-triage`); something that
broke while you were fixing something else becomes an issue too (`ready-for-agent`);
something you now *understand* goes into the code comment, test docstring, or ADR it
explains. [`docs/archive/findings.md`](docs/archive/findings.md) is the **closed** record
of phases 0–6 — code comments cite its IDs, so it stays, but nothing is appended to it.

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

### Code knowledge graph

GitNexus indexes symbols and call edges into a local, gitignored `.gitnexus/`, queried via
MCP. Note that `impact` under-reports on the Python pipeline — it misses
`from . import transform` style calls. See `docs/agents/gitnexus.md`.
