# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

Neither file exists yet — this repo is pre-implementation. That's expected.

## File structure

This is a **single-context** repo:

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-….md
│   └── 0002-….md
├── apps/web/          Nuxt SPA
├── apps/api/          Cloudflare Worker: Hono API + static assets
├── packages/schema/   the card contract
└── pipeline/          Python data pipeline
```

The workspaces above are separate deployables, but they share one domain vocabulary —
cards, locales, translations, decks — so there is one root glossary and one ADR log
rather than one per workspace. Split into contexts only if a workspace grows language
that genuinely conflicts with the root glossary; that would mean adding a
`CONTEXT-MAP.md` at the root and per-context `CONTEXT.md` files.

Note that `docs/v2-plan.md` currently carries much of the architectural reasoning that
would otherwise live in ADRs. Treat it as a source when checking for prior decisions,
but record *new* decisions as ADRs under `docs/adr/`.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
