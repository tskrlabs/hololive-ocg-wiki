# ADR 0001 — The card contract is generated from pydantic

**Status:** accepted
**Date:** 2026-07-25
**Phase:** 0
**Supersedes:** the "four places" problem described in [`v2-plan.md`](../v2-plan.md) §D5

## Context

In v1 the card shape was written out independently in four places — the Python
pipeline, `cloudflare/schema.sql`, `cloudflare/worker.ts`, and `types/card.ts` — plus a
fifth copy of the enums in `constants/card-data.ts`. They drifted. Verified before
starting Phase 0, by census over all 2,448 cards in v1's `data/cards.json`:

| Drift | Consequence |
|---|---|
| `rarity_code` "HR" missing from the TS union and from `constants/card-data.ts` | 24 cards were **unfilterable in the live UI** |
| `card_type_code` "unknown" missing from the TS union | 2 cards untyped (both were really `サポート・スタッフ` — F-001; the value itself was later removed, [#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)) |
| `oshi_skill.cost` declared in `types/card.ts`, `worker.ts` **and** `schema.sql` | field has never existed in the data |
| `special_values` typed `string[]` in `worker.ts` | actually `number[]` |
| `CARD_BLOOM_LEVELS = ["debut","1st","2nd","spot"]` | data says `first`/`second` — the bloom filter was built from the wrong spelling |

Two further data-level problems, neither caught by any of the four definitions:

- **`image_path` collides.** `hBP03-044_SR.png` and `hBP03-055_SR.png` each map to two
  different card ids, because `hCO01` reprints reuse the original set's filename. Under
  D9 those pairs would silently overwrite each other as R2 objects.
- **`_source_hash`** — translator cache bookkeeping — leaked into 14,688 translation
  objects of the published artifact.

## Decision

The contract is defined **once**, as pydantic models in
`packages/schema/src/holo_schema/`. Everything else is generated from them.

### 1. Two shapes, one projection

`Card` is canonical: snake_case, all 7 locales nested under `translations`. It is what
the pipeline writes, the seeder reads, and D1 stores.

`LocalizedCard` is the API response: one locale, translation fields flattened to the top
level. It is *derived* from `Card` by `localize(card, locale)`.

The projection is a function, not a second hand-maintained shape. v1 had this logic
hand-written inside `enrichCardDataBatch` (`worker.ts:266`) as a set of SQL joins with
no shared definition — which is how the API and the frontend types drifted apart.

### 2. `localize()` exists twice, pinned by golden files

D3 keeps the pipeline in Python; D8 stores translations as JSON, so the Worker must
project at **request time**, in TypeScript. Both implementations are therefore
necessary.

`localize.py` is the reference. `scripts/golden.py` runs it over the fixture corpus and
writes `golden/localized-{locale}.json` for all 7 locales. `tests/localize.test.ts`
asserts the TypeScript port reproduces those files exactly.

This is what makes "defined once" true for *behaviour* and not just for field names.
The TypeScript side gets written in Phase 4, months of context after the Python side —
precisely where "I'm sure I ported that correctly" goes wrong.

### 3. Generated output is committed

`json-schema/*.json` and `dist/*.d.ts` are in git, with a `DO NOT EDIT` banner and a
`.gitattributes` marking them `linguist-generated`.

The alternative — generating at install time — would put `uv` on the critical path for
every frontend contributor. D3 says contributors touching only the website never run
Python, and D14 says a fresh clone must run with zero credentials. Committing the output
is what makes both true. `make check` runs `generate.py --check` and fails if the
committed copy is stale.

### 4. Enums are closed, with an escape hatch

Every enum is a `Literal` union, complete against today's data. Unknown values are
**collected and reported** rather than raising on the first one, and the run exits
non-zero.

The data comes from scraping a site we do not control, and Hololive ships new sets
regularly. A hard failure on the first unrecognised value would block a set launch; no
validation at all lets a new rarity reach production silently. The escape hatch is
deliberately ugly so it does not become the default path.

> **Amended by [#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)
> (2026-07-30), on two counts.**
>
> **The escape hatch did not work.** This section said `--allow-unknown-enums`
> "publishes anyway and prints what it let through". It never once did: `build()`
> honoured the flag and then discarded the result on a `len(validated) != len(cards)`
> check that is true precisely when a card fails validation. No test covered it.
>
> The promise was also unimplementable as worded. These enums are closed `Literal`s, so
> a card carrying an unmapped value cannot become a `Card` at all — there is nothing to
> publish. The flag now **drops** those cards, ships the rest, and records the dropped
> ids in `CardCollection.dropped`; `publish` and `seed` refuse a non-empty list, with no
> override flag. So it unblocks `build` alone and never reaches the site.
>
> **`"unknown"` is no longer a `card_type_code`.** It was described here as legitimate
> and documented — the scraper's fallback, modelled so the build does not fail on cards
> we already ship. But it was the fallback in four enums and a member of only this one,
> so an unmapped value stopped the build in three fields and shipped silently in the
> fourth, into no deck section, counted by nothing. Those 2 cards were `サポート・スタッフ`
> all along (F-001), found by a hand-run census months later. Graceful degradation is now
> the operator's explicit choice via the flag above, and `holo-data transform` names the
> source value the site printed — which nothing could do before, since the sentinel
> discards it.

### 5. Colours are modelled exactly as the data has them

`blue_red` and `white_green` stay as first-class enum members alongside the
single-colour codes.

This was nearly normalised to `["blue","red"]` on the theory that the array already
expresses multi-colour. That would have been **wrong**: `public/icons/type_blue_red.webp`
is a distinct 4.2 KB asset against ~20 KB for each single-colour icon, i.e. a fused
symbol as printed on the card, not a composite. The data contains both `["blue_red"]`
(5 FUWAMOCO cards, one fused symbol) and `["red","blue"]` (3 miComet cards, two separate
symbols) — genuinely different things. Normalising would render two icons and a comma
where the card shows one icon.

Consequence: a "red" filter must also match fused codes containing red. That is a
**query-layer** rule (Phase 4), deliberately not a contract-layer one. `FUSED_COLORS`
is exported for it.

### 6. Storage annotations now, DDL in Phase 3

Fields carry `Column` / `Blob` / `FullText` markers describing how they land in D1.
Nothing reads them yet.

D5 said `packages/schema` would generate SQL too, but the Phase 0 done-criterion said
JSON Schema + TS only. They are incompatible: generating the DDL means *designing* the
D1 schema, which is D8/Phase 3 work needing decisions Phase 0 cannot make well (FTS5
column selection, index choices, upsert keys). A generated `schema.sql` that has never
run against real D1 is worse than none, because it looks authoritative. The annotations
let Phase 3 emit the DDL from these same models without re-deciding anything.

### 7. Verification is local — no CI

`make check` runs everything; `scripts/hooks/pre-commit` runs it automatically when a
commit touches `packages/schema/` or `fixtures/`, enabled per-clone with `make hooks`.

**GitHub Actions is not used in this project, by maintainer decision.** Note this is
independent of Workers Builds (Phase 6), which runs on Cloudflare's infrastructure and
is unaffected.

Accepted limitation: hooks are bypassable with `--no-verify`, and a contributor who
never runs `make hooks` gets no guard. There is no enforcement at the PR boundary.
Mitigation is that `make check` is also the first thing a pipeline run does, so a stale
artifact surfaces at the next build even if the hook was skipped.

## Consequences

**Good**

- All five drift sites above are now impossible: the enums have one definition, and `HR`
  is present. (`unknown` was too, until [#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)
  removed it deliberately — see the amendment under §4. The drift it fixed was real; the
  fix is now "such a card stops the build" rather than "such a card has a name".)
- `CardCollection` validates `image_key` uniqueness, so the R2 collision cannot ship.
  It fired on first run against real data, exactly as intended.
- All 2,448 v1 cards validate against the contract, so it describes reality rather than
  an idealised version of it.
- A frontend contributor gets types from `npm install` with no Python toolchain.

**Costs**

- Generated files in git create diff noise on model changes. Mitigated by the banner and
  `.gitattributes`.
- `localize()` is written twice. The golden files make divergence a test failure rather
  than a production bug, but it is still two things to edit.
- `fixtures/cards.json` (~560 KB) is committed, which is a stated exception to D1 ("data
  lives outside git"). D1's reasoning targets the 1 GB of images and 66 MB of snapshots
  that made cloning impossible; a 560 KB fixture file is source, and it is what makes
  D14's zero-credential clone work.

## Amendments to the v2 plan

- **D5** — "pydantic → JSON Schema → TS types + SQL": SQL moves to Phase 3.
- **Phase 1 done-when** — was "`holo-data build` reproduces today's `cards.json` shape".
  The canonical artifact is now snake_case, so a byte-diff against v1's output would show
  every key renamed. Restated as reproducing today's *data* — same 2,448 cards, same
  values, validated against `packages/schema`.

## Notes for later phases

- ~~**Phase 1** — `scripts/v1_adapter.py` is a migration aid, not contract code. Delete
  it once `holo-data build` emits v2 shapes natively.~~ **Done**, though two phases late
  than intended: `build_fixtures.py` kept reading v1's data through it until issue #16.
  Selecting the fixture corpus from a schema the contract had moved on from is what let
  the corpus and its generator disagree. The generator now reads `holo-data build`
  output and the adapter is deleted.
- **Phase 2** — adopt the `{set}/{filename}` image key scheme the adapter uses; it is
  what resolves the reprint collisions.
- **Phase 3** — the DDL emitter reads `annotations.py`.
- **Phase 4** — `FUSED_COLORS` is for the filter expansion rule. `/api/static-filters`
  should keep deriving from the database, not from the enum: "what rarities exist in the
  enum" and "what rarities exist in the current card pool" are different questions.
- **Phase 5** — delete `constants/card-data.ts`; import `dist/enums.ts` instead.
