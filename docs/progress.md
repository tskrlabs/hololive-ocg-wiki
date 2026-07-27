# v2 rebuild — progress

**Where we are:** Phases 0–4 done; **Phase 5 is in progress** on branch
`phase-5-website`. Images are live at `img.hololive-ocg-wiki.tskrlabs.com`, `publish` is
idempotent, D1 is populated and reseeded into the Phase 4 shape (2,448 cards), and the
Worker is built and green — now **nine endpoints**, `make check` covers them end-to-end
against local D1.

⚠️ **Nothing is deployed yet, deliberately.** Phase 5 decided on a *single* deploy at the
end, shipping the Worker and the static site together — so there is no API-only interim
deploy. See [Phase 5](#phase-5--the-website).

**Phase 5 design is settled.** Sixteen decisions, recorded in
[ADR 0006](adr/0006-website.md) with the full interview in
[`phase-5-grilling.md`](./phase-5-grilling.md).

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
| 2 | CF resources + R2 publish | ✅ done | [ADR 0003](adr/0003-r2-publish.md) · live |
| 3 | D1 redesign + seeder | ✅ done | [ADR 0004](adr/0004-d1-schema-and-seeder.md) · live |
| 4 | Worker rewrite (Hono + Zod) | ✅ done — deploys with Phase 5 | [ADR 0005](adr/0005-worker-api.md) |
| 5 | Website (new API/R2, 4 refactors) | 🚧 **in progress** | [ADR 0006](adr/0006-website.md) |
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
packages/schema/   the card contract — pydantic → JSON Schema → TS types → D1 DDL
packages/schema/sql/schema.sql       generated D1 schema (Phase 3)
packages/schema/sql/migrations/      evolving an already-populated database (Phase 4)
pipeline/          holo-data CLI: scrape … publish, seed
apps/api/          the Worker — Hono + Zod over D1 and R2 (Phase 4)
content/           info.json — editorial site copy, uploaded by publish
fixtures/          34 cards + fixtures.sql — credential-free local dev (D12)
docs/adr/          decisions made during execution
docs/infra.md      the Cloudflare runbook — what exists and which command made it
docs/findings.md   data anomalies awaiting maintainer review
Makefile           `make check` — the single verification entry point
```

```bash
make setup     # uv sync + npm install
make hooks     # opt-in pre-commit check (once per clone)
make check     # schema, pipeline, seeder, TS parity, Worker units + endpoints, typecheck
make check-api # just the Worker: 25 unit tests + 34 endpoint checks (no credentials)
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
holo-data publish / verify-images / migrate-images                 ← Phase 2
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
- `holo-data images` — PNG → WebP at q90. Measured over the real set in Phase 2:
  **191 MB**, 68% smaller than the PNGs and well under the 425 MB the sample predicted.
  New: nothing in v1 produced WebP
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
| **D8** | "filterable fields stay real indexed columns" → the three **multi-valued** ones become **junction tables**. A JSON array filtered with `LIKE` cannot use an index, so v1's three such indexes never fired. Measured on the real query shape: ~2,448 rows read vs ~50–100 ([ADR 0004](adr/0004-d1-schema-and-seeder.md)) |
| **D8** | `/api/filter-options` and `/api/static-filters` move **off D1** to R2 artifacts — same answer for every user until the next reseed, currently four full scans per call |
| **Plan §3** | D1 free storage is **500 MB**, not 5 GB — the plan quoted the paid tier. Not a problem: 17 MB data + 36 MB index |
| **Phase 3 done-when** | "`seed --dry` reports ~2,500 rows" → **~47,300 writes for a full reseed, ~2,320 for a new set**. The original counted only `cards` rows, ignoring index writes, junction rows and FTS shadow tables |
| **D8** | `color_codes` and `card_sets` are **also in `payload`**, not only in their junction tables. `localize()` reads both, so without them the Worker could not rebuild a card from the row it just selected. Junction = how a card is found, payload = what it is (+3.2%, [ADR 0005](adr/0005-worker-api.md)) |
| **D8** | New indexed **`name_ja`** column. The `name` filter needs an index and the name lives inside a JSON payload no index can reach. `CARD_INDEX_COUNT` 4 → 5, so a full reseed is **~49,785 writes** |
| **D8** | `/api/static-filters` is **deleted**, not moved to R2. It returned enum values the contract already owns, and v1's frontend never called it — it read a hand-maintained constants file that had drifted |
| **Phase 4 done-when** | "All 8 endpoints; SPA + API from one Worker" → **7 endpoints, API only**. `apps/web` does not exist until Phase 5, so there are no assets to bind; the `assets` block, SPA fallback and apex domain move there |
| **Phase 3 schema** | `schema.sql` is `CREATE TABLE IF NOT EXISTS`, so it **cannot evolve a populated database** — re-applying it silently skips a new column, then fails on the index using it. `packages/schema/sql/migrations/` added |
| **Phase 4** | Seven endpoints → **nine**. `/api/info` and `/api/status` were never built, so `info.json` (uploaded since Phase 2) and `status.json` (since Phase 3) sat in a private bucket **with no reader at all** ([ADR 0006](adr/0006-website.md)) |
| **D11** | `content/README.md` claimed the card count comes from `cards.json` "which the site already loads" — **the site never loads it** (21 MB; D8 moved querying to D1). It comes from `/api/status`, which already carries `counts.total` and `generated_at` |
| **D11** | The edit-without-redeploy premise is **weaker than when written**: `info.json` has been *committed* since Phase 2, so editing it is already edit → commit → publish, and Workers Builds will auto-deploy that commit anyway. R2 retained for consistency with `status.json`, which has no committed copy |
| **D13** | "four refactors + dead-code purge" is joined by a **framework upgrade**, Nuxt 3.17 → 4.5. Still no new features, no redesign, no rendering-mode change |
| **Phase 5 status page** | v2's `status.json` dropped `skipped[]` and `source.valid` and is snake_case throughout, so `/status` **cannot be ported unchanged**. Ported adapted; the Skipped tab has no data source in v2 and is dropped |
| **v2-plan §7** | The SEO decision stays deferred — which means Phase 5 must **actively block indexing** to keep it deferrable |

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

### Phase 2 execution

The code is built and `make check` is green, but **the Cloudflare resources do not exist
yet** and the maintainer creates them. Until then `publish` fails with instructions.

Commands are `uv run holo-data …` — the CLI lives in the project venv, not on your PATH.

**✅ Phase 2 is complete and live.** Executed 2026-07-27:

| | result |
|---|---|
| Buckets | both created, `r2.dev` disabled on each |
| Custom domain | `img.hololive-ocg-wiki.tskrlabs.com` → CDN `HIT`, `immutable` cache header |
| Images migrated | 2,448 PNG across 34 set folders (603 MB) |
| WebP converted | 2,448 (191 MB — **68% smaller**, and well under the 425 MB estimate) |
| `build` | 2,448 cards, 100% translation coverage in all 7 locales, 21.3 MB |
| `verify` vs v1 | only the 2 known F-001 cards + the F-003/F-004 arts — **zero unexplained drift** |
| `verify-images --remote` | **2,448/2,448 byte-identical to source** (after F-012) |
| `publish` | 2,450 objects; a second run uploads nothing |

R2 usage: images 191.4 MB, artifacts 21.4 MB — **2% of the 10 GB free tier.**

**F-012 found during this run.** The first provenance check reported 12 images differing
from source — not wrong cards, but stale copies: the official site had silently
re-uploaded 7 at higher resolution and re-compressed 5. `download_image()` skips files
already on disk, so a *replaced* upstream file is never noticed. Re-fetched and clean.
This is why `verify-images --remote` exists, and worth re-running after each new set.

### Working data lives in the main checkout

`pipeline/data/`, `locales/`, `images/` and `build/` are gitignored, and they were
populated in the **main checkout** (`/Users/chingli/tskrlabs/projects/hololive-ocg-wiki`)
rather than in a worktree, so they survive this branch being merged. A worktree run needs:

```bash
MAIN=/Users/chingli/tskrlabs/projects/hololive-ocg-wiki/pipeline
export HOLO_DATA_DIR=$MAIN/data HOLO_LOCALES_DIR=$MAIN/locales \
       HOLO_IMAGES_DIR=$MAIN/images HOLO_BUILD_DIR=$MAIN/build
```

The translation cache is seeded (81,124 entries from v1), so `translate` has nothing to
do until new cards ship.

Done when images resolve at `img.hololive-ocg-wiki.tskrlabs.com/{set}/{stem}.webp` and a
second `publish` uploads nothing.

## Phase 3 — D1 redesign + seeder

Full reasoning and the measurements behind every choice in
[ADR 0004](adr/0004-d1-schema-and-seeder.md).

```
holo-data seed --dry        row counts + write estimate   (reads only)
holo-data seed --confirm    diff-based upsert into D1     (writes)
holo-data seed --full       rewrite everything            (gated separately)
holo-data seed --prune      delete cards missing from the build
```

**The measurements changed the design.** Reading v1's live D1 analytics turned up that
**reads, not writes, are the binding constraint** — the site scans 882 rows per query on
a 2,448-row table and **breached the 5M/day free tier on 2026-07-12** (F-014). D8
optimised the row count, which is the resource with slack.

More sharply: the JSON-payload design *on its own* would have made the live problem
worse. With `color_codes` as a JSON column, a filtered and sorted page is a full 2,448-row
scan — worse than v1's 882 — because `ORDER BY` evaluates every match before `LIMIT`
applies. The junction tables are what make the payload design pay off.

| design | rows read per 50-card filtered page |
|---|---|
| v1 today | ~882 (measured in production) |
| payload + JSON colour | ~2,448 — **worse** |
| payload + junction colour | **~50–100** |

- **Junction tables** for `color_codes`, `tags`, `card_sets` — `WITHOUT ROWID`, value
  leading the PK, so the key is the storage and a filter is a covering-index range scan
- **`payload` / `qa_payload` split.** Q&A is 53% of the translation bytes and the only
  part that churns after a card is printed (ADR 0002). List endpoints never read it
- **FTS5 `tokenize='trigram'`**, one row per card, all 7 locales concatenated. This
  **fixes a live search bug** — F-013: `白上フブキ` returns 62 cards on v1 but `フブキ`
  returns **zero**, because `unicode61` treats an unbroken CJK run as one token. Verified
  on the real set: `フブキ` now returns 73
- **The diff baseline is D1 itself** — `content_hash`/`qa_hash` columns rather than v1's
  committed 648 KB hash file, which can disagree with the database. An interrupted run
  resumes with no reconciliation
- **Writes go through the D1 REST API** from Python, fully parameterised. D1 batches are
  **transactional** (verified), so one batch per card means a card is never half-written
- **`seed` reads today's actual write usage** from analytics and refuses if the estimate
  will not fit — not the flat 100k, which is blind to a seed that already ran
- **Deleting needs `--prune`**, plus a hard refusal if the card count drops >10%
- **`schema.sql` is generated** from the same pydantic models, via a new `Junction`
  annotation. Applied with `wrangler`, never by `seed`

**Write accounting** (replaces the plan's "~2,500 rows"):

| scenario | writes | % of 100k/day |
|---|---|---|
| Full reseed | ~47,300 | 47.3% |
| New card set (~120 cards) | ~2,320 | 2.3% |
| Q&A-only update (100 cards) | ~700 | 0.7% |

Every constant behind these was measured against production, not estimated.

### Phase 3 execution

**✅ Phase 3 is complete and live.** Executed 2026-07-27 against
`hololive-ocg-wiki-db` (`75238170-4525-4a06-bfd3-5a32c4daef57`):

| | result |
|---|---|
| Schema applied | 4 tables + FTS virtual table, 7 indexes |
| `seed --confirm` | 2,448 cards, 27,203 rows written, 327 batches, 81s |
| Row counts | cards 2,448 · colors 2,032 · tags 5,443 · sets 2,592 · fts 2,448 |
| CJK search | `フブキ` **73 hits** (v1 returns 0), `宝鐘マリン` 45, `ときのそら` 52 |
| Second `seed --dry` | "D1 is already up to date — nothing to write" |
| Database size | 53.8 MB (11% of the 500 MB free tier) |

**The first seed found a bug no local test could have.** It wrote 27,203 rows but
**read 15,508,419** — three times the daily read budget — because the seeder's
`DELETE … WHERE card_id = ?` could not use the junction tables' `(value, card_id)` key
and skip-scanned each table per card. The read path and the write path want opposite
key orders. Adding a `card_id` index to each junction, and keying the FTS table on rowid
instead of an UNINDEXED column, took a full reseed from **15.5M rows read to ~22,850** —
a 679× reduction. SQLite does not report `rows_read`; D1 does, which is why only a real
run surfaced it. Both are now pinned by query-plan tests.

`seed` needs `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in `pipeline/.env` — a
**different token from the R2 one**, scoped to D1 Edit on this database plus Account
Analytics Read (the write-budget gate). See [`infra.md`](./infra.md).

~~One follow-up: `status.json` was written locally but not uploaded~~ — done in Phase 4.

### Local development needs no credentials (D12)

Run from `apps/api/`, where `wrangler.jsonc` declares the bindings. Note the database is
`hololive-ocg-wiki-db`; `hololive-ocg-wiki` is the *Worker's* name and does not resolve —
the command printed here before Phase 4 was wrong.

```bash
cd apps/api
npx wrangler d1 execute hololive-ocg-wiki-db --local \
    --file=../../packages/schema/sql/schema.sql
npx wrangler d1 execute hololive-ocg-wiki-db --local --file=../../fixtures/fixtures.sql
```

Or just `make check-api`, which does both and then exercises every endpoint.

`fixtures.sql` is committed and generated from the 34 fixture cards — every card type,
every rarity, all 9 colours, all 7 locales, 546 Q&A items. No token, no network, no
Python. `seed` is deliberately not involved: it only ever writes to production.

Done when `seed --dry` reports the estimate above, production D1 is populated, and a
second `seed` writes nothing.

## Phase 4 — the Worker

Full reasoning and every measurement in [ADR 0005](adr/0005-worker-api.md).

```
apps/api/src/index.ts        app wiring, CORS, error handling
apps/api/src/routes/         cards (search/filter/detail/batch), filters (R2)
apps/api/src/db/             query builders and FTS escaping — pure, unit-tested
apps/api/src/lib/            Zod input schemas, response + cache helpers
apps/api/tests/smoke.sh      boots wrangler dev and curls every endpoint
```

**Grilling found five things the plan did not know.** Each changed the work, and two
were blockers:

1. **The Worker could not rebuild a card from what D1 stored.** `localize()` reads
   `color_codes` and `card_sets`; neither was a column and neither was in `payload` —
   they lived only in the junction tables, keyed for filtering rather than lookup. Both
   now go in the payload too (+3.2%), so a list page is one query with no fan-out.
2. **`/api/static-filters` was dead code**, returning enum values the contract already
   owns. Deleted; Phase 5 imports `@holo/schema/enums`. Eight endpoints became seven.
3. **Raw input crashes FTS5** — `a AND`, `-x` and a bare `"` are syntax errors. Every
   query is now wrapped as a literal phrase, so they return 200 with zero hits.
4. **The `name` filter was broken in v1**: 41% of characters are spelled inconsistently
   across their own cards ([F-015](findings.md#f-015)). It keys on `name_ja` now.
5. **`apps/web/` does not exist**, so the phase's own done-when was unmeetable. Scope
   became API-only.

**A sixth turned up while building:** v1's colour filter silently omits fused
dual-colour cards ([F-016](findings.md#f-016)). Filtering `blue` misses the 5 `blue_red`
cards, because `LIKE '%"blue"%'` does not match `"blue_red"`. The Worker expands the
filter instead of the storage.

### Phase 4 execution

**Executed 2026-07-27.** Schema migrated, production reseeded, artifacts published:

| | result |
|---|---|
| Migration | `name_ja` column + index added to the live database |
| `seed --confirm` | 2,448 cards, **49,785 rows written — exactly the estimate**, 18,762 read |
| Database size | 73.0 MB (15% of the 500 MB free tier) |
| `name_ja` populated | 2,448/2,448, **296 distinct characters** (was 381 name entries in `en`) |
| `publish` | 8 artifacts — `cards.json` + 7 `filter-options/` files; a second run uploads nothing |
| `make check` | green — 167 Python, 11 TS parity, 25 Worker unit, 34 endpoint checks |

**The deploy moved to Phase 5**, by decision — one deploy shipping the Worker and the
site together, rather than an API-only interim. It still needs a token with **Workers
Scripts Edit**; the seeder's token is scoped to D1 Edit + Analytics Read only, which is
correct and worth keeping. Commands are in [Phase 5](#phase-5--the-website).

## Phase 5 — the website

Full reasoning in [ADR 0006](adr/0006-website.md); the complete interview, including
every option rejected, in [`phase-5-grilling.md`](./phase-5-grilling.md).

**The grilling found three holes, all of them gaps *between* phases rather than bugs
inside one:**

1. **`info.json` and `status.json` had no reader.** Uploaded to the private artifacts
   bucket since Phases 2 and 3; no Worker route served either. The site would have had no
   way to render its about dialog or its status page. → `/api/info`, `/api/status`.
2. **`content/README.md` documents a mechanism that does not exist** — it says the card
   count comes from `cards.json` "which the site already loads". The site never loads it.
3. **`status.json` changed shape**, so `/status` cannot be ported unchanged, and its
   Skipped tab has no data source in v2 at all.

### The commit sequence

| # | commit | state |
|---|---|---|
| 1 | `/api/info` + `/api/status` | ✅ done |
| 2 | scaffold `apps/web` on Nuxt 4 (`app/` srcDir, `nuxt generate`, `make dev`) | ✅ done |
| 3 | port the **live** code only — green on fixtures | ⬜ |
| 4 | Candidate 01 — one `useCardQuery` interface | ⬜ |
| 5 | Candidate 02 — deep Filter module | ⬜ |
| 6 | Candidate 03 — Deck as sections, **wire format frozen** | ⬜ |
| 7 | Candidate 04 — `useDeckCards` | ⬜ |
| 8 | `assets` binding + deploy + domain | ⬜ |

### Working on the site

```bash
make dev       # site on :3000 + Worker on :8787, HMR, fixtures, no credentials
make preview   # rehearsal: nuxt generate, then the Worker serves site + API on one port
make check-web # the site's unit tests
```

`make dev` proxies `/api` to the Worker, which is Nuxt's behaviour. `make preview` is the
only thing that exercises the **real** SPA fallback and same-origin requests — run it
before deploying, since the first deploy is otherwise unrehearsed.

**Indexing and analytics are off** unless `NUXT_PUBLIC_LAUNCHED=true`. Verified in both
directions: unset gives `Disallow: /`, `noindex, nofollow` and no sitemap; set gives an
indexable `robots.txt`, `sitemap_index.xml` and `index, follow`.

### Three API changes the frontend must adapt to

Verified against v1's live code, not assumed:

- **`total` is absent** when `skip_count=true`, rather than `-1`. `useCardStoreAPI.ts:657`
  comments *"response.total is -1 when skip_count=true"*. Read it as `total ?? cachedTotal`.
- **Over-cap batch requests 400** instead of silently returning the first 50.
  `useCardStoreAPI.ts:448` joins ids with no chunking. Chunk to 50 client-side.
- **Colour filters include fused cards**, so the separate `blue_red` / `white_green`
  checkboxes go — those cards now appear under both constituent colours (F-016).

Also: `constants/card-data.ts` → `@holo/schema/enums`, and `normalizeCard`
(`useCardStoreAPI.ts:88`) is a no-op spread over a commented-out body — delete outright.

### Two switches that must flip at Phase 7

The pre-launch site is deliberately invisible: **`noindex`** (v2-plan §7 defers the SEO
decision, and an indexed v2 would pre-empt it) and **analytics off** (pre-launch traffic
would pollute the container holding v1's real year of data). If these are missed at
launch, the new site stays invisible.

### The deploy, when commit 8 lands

Split in two deliberately — everything before it is verified against **34 fixture cards**,
and Phase 3's lesson was that the expensive bug only appears against a real database:

```bash
cd apps/api
npx wrangler login          # or export a token with Workers Scripts Edit
npx wrangler deploy         # Worker + assets → workers.dev
```

Verify against the real 2,448 cards **before** attaching the domain. These are the
numbers Phase 3 and 4 measured, so they double as a check that the reseed landed:

```bash
API=https://hololive-ocg-wiki.<your-subdomain>.workers.dev
curl -s "$API/api/health"
curl -s "$API/api/cards/search?q=フブキ"    | jq '.cards | length'   # expect 73
curl -s "$API/api/cards/search?q=そら"      | jq '.cards | length'   # 2 chars → LIKE path
curl -s "$API/api/cards/search?q=a%20AND"   | jq                     # 200, not 500
curl -s "$API/api/cards/filter?name=白上フブキ&locale=en" | jq '.total'  # expect 44
curl -s "$API/api/filter-options?locale=en" | jq '.names | length'   # expect 296
curl -s "$API/api/status" | jq '.counts.total'                       # expect 2448
curl -s "$API/api/info"   | jq '.contents | length'                  # expect 3
```

Then walk the site itself on that URL — filter, search, open a card, build a deck, share
a deck code — and only then point `hololive-ocg-wiki.tskrlabs.com` at it.
