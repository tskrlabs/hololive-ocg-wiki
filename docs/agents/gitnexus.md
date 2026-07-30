# GitNexus

A local code knowledge graph — symbols, call edges, and execution flows — queried through
MCP tools. It answers "what calls this" and "what breaks if I change this" without grepping.

The index is **local and gitignored**. It is not a build artifact and no CI depends on it;
nothing in `make check` reads it.

## Setup

The MCP server is configured at **user scope** (`~/.claude.json`), not per-repo, so it is
already available. What is repo-local is the index itself, under `.gitnexus/`:

```bash
gitnexus analyze --embeddings --skip-agents-md
```

`--skip-agents-md` is not optional here. Without it, `analyze` appends a generated stanza
to `CLAUDE.md` and creates an `AGENTS.md`. `CLAUDE.md` is hand-curated and reviewed as a
diff; a tool that rewrites it on every re-index makes that diff meaningless.

`--embeddings` enables semantic ranking in `query`, so natural-language searches work.
Embeddings are generated on-device — no API key, no network.

Re-run after any substantial change. Check freshness with `gitnexus status`, which compares
the indexed commit against `HEAD`.

## Known gap: module-attribute calls are not edges

This repo uses two import styles, and GitNexus only resolves one of them.

```python
from .paths import ensure_dirs     # ensure_dirs(...)      -> CALLS edge  ✅
from . import transform            # transform.is_notice() -> no edge     ❌
```

Calls made through a module object produce no `CALLS` edge. As of the first index this
affects **34 call sites across 8 files** in `pipeline/src/holo_data/` — `build.py`,
`cli.py`, `d1.py`, `seed.py`, `publish.py`, `import_v1.py`, `verify_images.py`, and
`transform.py`.

The practical consequence: **`impact` under-reports on the Python pipeline.** Asking for
the blast radius of `is_notice` returns `impactedCount: 0` and `risk: LOW`, while
`build.py:120-121` calls it twice. A zero here means "no *direct-import* callers found",
not "safe to change".

So: treat a low-impact result on pipeline code as a prompt to grep, not as a clearance.
Cross-file edges do resolve normally for direct-symbol imports, and the TypeScript side is
unaffected.

## Tools

`query` finds execution flows by concept. `context` gives a symbol's callers and callees.
`impact` estimates blast radius — subject to the gap above. `cypher` runs raw graph
queries when the shaped tools do not fit.

The `gitnexus-*` skills wrap these for exploring, debugging, refactoring, and PR review.
