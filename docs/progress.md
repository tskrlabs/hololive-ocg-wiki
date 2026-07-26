# v2 rebuild — progress

**Where we are:** Phases 0, 1 and 2 built. **Phase 2 needs the Cloudflare resources
created before it can be verified end-to-end** — see "Finishing Phase 2" below. Phase 3
(D1 redesign + seeder) is next.

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
| 2 | CF resources + R2 publish | 🟡 built, awaiting CF resources | [ADR 0003](adr/0003-r2-publish.md) |
| 3 | D1 redesign + seeder | 🔜 **next** | |
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
pipeline/          holo-data CLI: scrape, images, translate, build, verify, publish
apps/api/          wrangler.jsonc — R2 bindings (Worker itself arrives in Phase 4)
content/           info.json — editorial site copy, uploaded by publish
fixtures/          34 cards covering every enum member and edge case
docs/adr/          decisions made during execution
docs/infra.md      the Cloudflare runbook — what exists and which command made it
docs/findings.md   data anomalies awaiting maintainer review
Makefile           `make check` — the single verification entry point
```

```bash
make setup     # uv sync + npm install
make hooks     # opt-in pre-commit check (once per clone)
make check     # 124 tests: schema, pipeline, TS parity, typecheck
make help

uv sync --extra publish   # adds boto3, only needed for `holo-data publish`
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
| **Phase 1 image tree** | Flat `images/{png,webp}/` → **set-scoped** `images/{png,webp}/{set}/`. Amended in Phase 2: the flat layout could not hold F-006's two same-named-different-artwork reprints, which is a data-loss bug, not a layout preference ([ADR 0003](adr/0003-r2-publish.md)) |
| **D11** | `info.json` is **committed** at `content/info.json` and uploaded by `publish`, not pushed by hand. The card count comes out of its prose and is rendered from `cards.json` instead — a Phase 5 dependency |

## Phase 2 — R2 publish

Full reasoning in [ADR 0003](adr/0003-r2-publish.md); the Cloudflare runbook is
[`infra.md`](./infra.md).

```
holo-data publish          images + artifacts → R2   (--dry-run, --force)
holo-data verify-images    coverage; --remote re-checks bytes against the source
holo-data migrate-images   one-time: v1's flat images → the set-scoped tree
```

- **Two buckets.** `hololive-ocg-wiki-images` is public behind
  `img.hololive-ocg-wiki.tskrlabs.com`; `hololive-ocg-wiki-artifacts` is private. The
  images bucket is world-readable forever by design — artifacts have a different
  lifecycle and stay out of it
- **The local image tree is now set-scoped** — `images/{png,webp}/{set}/{stem}.ext`,
  mirroring `image_key`, so `publish` is a directory sync with no lookup. This is a
  **Phase 1 amendment**, and it is a bug fix: see F-006 below
- **`publish` diffs by listing R2** (size, then MD5/ETag), never deletes, and has
  **no `--confirm`**. Instead it refuses on a *stale* `cards.json` or an incomplete image
  set — gates an agent cannot satisfy by adding a flag
- **Custom domain from the start, `r2.dev` disabled.** `r2.dev` is rate-limited and gets
  no CDN cache at all; the custom domain is what keeps R2 reads near zero
- **Cache headers set explicitly at upload** — images `immutable` for a year, artifacts
  `no-cache` — rather than inherited from Cloudflare's default extension list
- **`boto3` is an optional extra** (`uv sync --extra publish`). 27 MB, and only the
  maintainer can publish anyway (D14)
- **`info.json` is committed editorial copy** at `content/info.json`, carrying no facts
  about the data. v1's hardcoded *"2448 cards (June 19, 2026)"* is gone — Phase 5 renders
  that from `cards.json`'s `generated_at`

**F-006 resolved, and it was a live bug.** The two `hCO01` reprints were fetched and
hashed: `hBP03-044_SR` and `hBP03-055_SR` are **different artwork by different
illustrators** in `hBP03` and `hCO01`, not duplicate files. v1's flat image directory
skipped any filename already on disk, so only one of each pair was ever downloaded and
both cards rendered the same art. The set-scoped tree is what fixes it — the image key
alone does not, since two keys can still point at one flat file.

### Finishing Phase 2

The code is built and `make check` is green, but **the Cloudflare resources do not exist
yet** and the maintainer creates them. Until then `publish` fails with instructions.

1. Create both buckets, add the custom domain, disable `r2.dev`, mint a bucket-scoped
   token — all in [`infra.md`](./infra.md)
2. Put the credentials in `pipeline/.env` (see `pipeline/.env.example`)
3. `uv sync --extra publish && holo-data publish --dry-run`
4. `holo-data migrate-images` → `holo-data images` → `holo-data build`
5. **`holo-data verify-images --remote` once** — proves all ~2,450 migrated files are the
   right bytes for the right keys. This is the check that would have caught F-006 the day
   it shipped
6. `holo-data publish`

Done when images resolve at `img.hololive-ocg-wiki.tskrlabs.com/{set}/{stem}.webp` and a
second `publish` uploads nothing.
