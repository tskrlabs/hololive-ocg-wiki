# v2 rebuild — progress

**Where we are:** Phases 0 and 1 done. **Phase 2 (Cloudflare resources + R2 publish) is
next.**

This file is the resume point for a new session. Read it, then
[`v2-plan.md`](./v2-plan.md) for the design, then the ADRs for decisions made during
execution. Progress is mirrored to GitHub issue
[#2](https://github.com/tskrlabs/hololive-ocg-wiki/issues/2); this file is the offline
copy and is authoritative if they disagree.

## Phases

| # | Phase | Status | Record |
|---|---|---|---|
| 0 | Repo skeleton + `packages/schema` | ✅ done | [ADR 0001](adr/0001-card-contract-generation.md) · `2d23999` |
| 1 | Pipeline migration | ✅ done | [ADR 0002](adr/0002-field-level-translation-cache.md) · `6be38ff` |
| 2 | CF resources + R2 publish | 🔜 **next** | |
| 3 | D1 redesign + seeder | ⬜ | |
| 4 | Worker rewrite (Hono + Zod) | ⬜ | |
| 5 | Website (new API/R2, 4 refactors) | ⬜ | |
| 6 | Workers Builds + fixtures + docs | ⬜ | |
| 7 | Launch | ⬜ | |

## Working agreement

- Work on **`develop`**, not `main`. Push is fine.
- **Never use GitHub Actions** — the maintainer has had an account banned over Actions
  usage. Verification is local: `make check`, plus an opt-in pre-commit hook
  (`make hooks`). Workers Builds (Phase 6) is unaffected; it runs on Cloudflare and
  GitHub only sends a webhook.
- Free Cloudflare tiers only. A paid service is a decision, not an assumption.
- Each phase is grilled before it is built. The decisions in `v2-plan.md` §4 are settled;
  if implementing one shows it was wrong, say so and propose the change.
- Data anomalies that need a human eye go in [`findings.md`](./findings.md), not into a
  fix. Anything unambiguously broken with an obvious fix gets fixed and logged.

## What exists now

```
packages/schema/   the card contract — pydantic → JSON Schema → TS types
pipeline/          holo-data CLI: scrape, images, translate, build, verify
fixtures/          34 cards covering every enum member and edge case
docs/adr/          decisions made during execution
docs/findings.md   data anomalies awaiting maintainer review
Makefile           `make check` — the single verification entry point
```

```bash
make setup     # uv sync + npm install
make hooks     # opt-in pre-commit check (once per clone)
make check     # 83 tests: schema, pipeline, TS parity, typecheck
make help
```

## Phase 0 — the card contract

The card shape was written out in four places in v1 and had measurably drifted. It is now
defined **once**, as pydantic models; the JSON Schema, TypeScript types, enum arrays, and
(from Phase 3) the D1 DDL are generated from them.

Key decisions — full reasoning in [ADR 0001](adr/0001-card-contract-generation.md):

- Two shapes: `Card` (canonical, all 7 locales) and `LocalizedCard` (API, one locale),
  with `localize()` as the single projection between them
- `localize()` exists in Python **and** TypeScript, because the pipeline is Python (D3)
  while the Worker projects at request time (D8). Golden files pin them together; the TS
  test asserts byte identity across 34 cards × 7 locales
- Generated output is **committed**, so a frontend contributor needs no Python toolchain.
  `make check` fails if it is stale
- Closed enums, collect-and-report validation, `--allow-unknown-enums` escape hatch
- snake_case everywhere
- Colours modelled **as-is** — see [F-007](./findings.md#f-007)
- Storage annotations (`Column`/`Blob`/`FullText`) recorded now, DDL emitted in Phase 3

Drift this removed: `HR` rarity missing from the TS union (24 cards unfilterable in the
live UI), `unknown` card type missing, `oshi_skill.cost` declared in three files but never
present in data, `special_values` typed `string[]` when it is `number[]`, and
`CARD_BLOOM_LEVELS` using `1st`/`2nd` against the data's `first`/`second`.

## Phase 1 — the pipeline

v1's 9 numbered scripts are now a `pipeline/` module with one `holo-data` CLI.

```
holo-data scrape / images / translate / build / verify / status   ← working
holo-data publish                                                  ← Phase 2 stub
holo-data seed                                                     ← Phase 3 stub
```

Key decisions — full reasoning in
[ADR 0002](adr/0002-field-level-translation-cache.md):

- **Parsing moved verbatim.** The BeautifulSoup selectors and HTTP/retry logic are
  character-for-character from v1 (D3). Everything around them was rewritten
- **Field-level translation caching** replaces v1's whole-card `_source_hash`. Measured
  across v1's dated snapshots, a card's printed text does not change once published —
  Q&A is the only real churn — so v1 re-translated ~50× more than needed
- **Manual corrections are cache entries** marked `source: "manual"`, superseding D14's
  overlay. The whole card still goes to the model; only *stale* fields are read back, so
  a correction survives even when the card is re-sent
- `holo-data images` — PNG → WebP at q90 (~425 MB for the full set, 4.3% of the R2 free
  tier). New: nothing in v1 produced WebP
- `holo-data verify` is permanent, with a `--baseline` path argument

**Verified:** `verify` reports zero base-field differences against v1's 2,448-card
published data. With the cache seeded from v1 (`python -m holo_data.import_v1`, 81,124
entries), `translate --dry-run` reports **2,228 of 2,448 cards already current**.

Three bugs were caught by diffing against real data, all in the rewritten plumbing: the
特攻 icon also appearing in `cost_icons` (482 cards got `unknown` cost types), a keyword's
type being its icon's `alt` rather than its `name` (1,124 cards lost their keyword), and
the 特攻 alt being `紫+50` rather than `紫` (every special art lost its targets). None
would have been visible without a known-good baseline.

## Amendments to `v2-plan.md`

Recorded in the ADRs; listed here so they are not missed.

| Decision | Change |
|---|---|
| **D5** | "pydantic → JSON Schema → TS types **+ SQL**" — SQL moves to Phase 3, where the D1 schema is actually designed |
| **D11** | `status.json` moves from `publish` to the **seeder (Phase 3)**. It is written by v1's `migrate.js`, not the pipeline, and describes a *database diff* — knowledge `publish` cannot have |
| **D14** | The `corrections/` overlay is superseded by field-level caching. Same goal, no separate merge layer. Scripts 7/8 dropped (never used) |
| **Phase 1 done-when** | "reproduces today's `cards.json` **shape**" → reproduces today's **data**. The artifact is snake_case now, so a byte-diff would show every key renamed |

## Starting Phase 2

**Goal (from `v2-plan.md`):** images live at `img.hololive-ocg-wiki.tskrlabs.com`;
`publish` is idempotent.

What it needs to build:

- `holo-data publish` — upload `pipeline/images/webp/` and `build/cards.json` to R2.
  Currently a stub that explains itself and exits 1
- The R2 bucket, its custom domain, and a committed `wrangler.jsonc` (v1's `wrangler.toml`
  was gitignored — the infra config was not in version control at all)

Facts worth having before starting:

- The image key scheme is `{set}/{filename}`, e.g. `hBP08/hBP01-028_C_02`. `Card.image_url()`
  and the TS `cardImage()` compose the URL; **nothing stores a URL** (D9)
- `CardCollection` already rejects duplicate image keys, so the reprint collision in
  [F-006](./findings.md#f-006) cannot ship silently
- Full set ≈ 425 MB of WebP, comfortably inside R2's 10 GB free tier. Egress is free
- `status.json` is **not** Phase 2 — see the D11 amendment above
- ⚠️ Never enable Workers "Smart Caching" — it makes static asset requests billable
  (`v2-plan.md` §6)

Open questions for the Phase 2 grilling: whether `publish` diffs against what is already
in R2 or re-uploads blindly; whether `info.json` (D11) is written by `publish` or by hand;
and whether the bucket gets a custom domain now or an `r2.dev` URL until launch.
