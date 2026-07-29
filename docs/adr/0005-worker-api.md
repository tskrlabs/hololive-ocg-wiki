# ADR 0005 — the Worker API

**Status:** accepted · **Phase:** 4 · **Date:** 2026-07-27

## Context

Phase 4 replaces v1's `cloudflare/worker.ts` — 1,269 lines in one file, an
`if (path === …)` chain, hand-rolled CORS across three helpers, and a `checkRateLimit()`
that unconditionally returned `true` — with a Hono + Zod Worker reading the Phase 3
schema. D7 settled the stack; there is no rollback case to protect, because these are
new resources and the v1 site stays live until cutover.

Grilling the phase before building it turned up five things the plan did not know, and
each changed the work.

### 1. The Worker could not reassemble a card from what D1 stored

`localize()` reads `card.color_codes` and `card.card_sets`. The `cards` table had neither
column, and neither was in `payload` — they existed **only** in the junction tables,
which are keyed `(value, card_id)` for filtering. Reading them back per card would mean
an extra query per list page, which is the `enrichCardDataBatch` fan-out the payload
design exists to delete.

This was a blocker, not a detail: the endpoint that renders the card grid could not have
been built without resolving it.

### 2. `/api/static-filters` was dead code

It returned card types, rarities, colours and bloom levels via four `SELECT DISTINCT`
full scans. v1's own frontend never called it — it read a hand-maintained
`constants/card-data.ts`, which had drifted from the data exactly as Phase 0 predicted:
no `HR` rarity, and `1st`/`2nd` where the data says `first`/`second`.

### 3. Raw user input crashes FTS5

Verified against a local D1 before any code was written: `a AND`, `-x`, and a bare `"`
all raise `fts5: syntax error`. v1 caught that as control flow; a naive port returns 500.

### 4. The `name` filter was broken in v1 and could not be ported as-is

41% of characters (122/296) are spelled inconsistently across their own cards. Full
measurements in [F-015](../archive/findings.md#f-015).

### 5. `apps/web/` does not exist

The phase's own done-when — "SPA + API from one Worker" — could not be met, because
there are no assets to bind until Phase 5.

## Decision

### Scope: API only

`assets`, `not_found_handling`, and the apex custom domain move to **Phase 5**, when
Nuxt produces a real `dist/`. Binding a placeholder directory would prove nothing about
Nuxt's actual output and its `_nuxt/` asset paths, and the domain is better attached once
— with a site behind it — than briefly serving JSON 404s.

Phase 4 deploys to `workers.dev`.

### Seven endpoints, not eight

`/api/static-filters` is **deleted**. Phase 5 imports `@holo/schema/enums`, which is
generated from the same pydantic models as the database. That is the whole point of
defining the contract once, and it removes the file where the drift lived.

`/api/filter-options` stays, but reads a **per-locale R2 artifact** written by
`holo-data build` and uploaded by `publish`. The answer is identical for every user until
the next reseed, and computing it per request was four full scans on the endpoint family
that breached the read tier (F-014). 232 KB across 7 locales, ~33 KB per request, cached
24 h.

### `color_codes` and `card_sets` join the payload

Both fields now carry `Junction(...)` **and** `Blob()`. The junction table is how a card
is *found*; the payload is what a card *is*.

| | |
|---|---|
| Payload growth | 2,933 → 3,027 B/card (**+3.2%**) |
| Extra queries per list page | **0** |

`tags` is deliberately **not** duplicated: `LocalizedCard.tags` comes from
`translation.tags`, which is already inside `translations`. `Card.tags` — the stable ja
identity used by the tag *filter* — stays junction-only, because the filter passes a
value in and never reads it back.

Pinned by a test that rebuilds every fixture card from its row alone and asserts
`localize()` equality in all 7 locales, so a future field cannot reach `LocalizedCard`
without reaching the payload. Verified by deliberately breaking it.

### One payload column, all 7 locales

Measured: `payload` averages 2,933 B/card, of which the requested locale is 459 B (16%).
A 50-card page therefore reads ~143 KB to serve ~22 KB.

Accepted, because **D1 bills rows, not bytes** — this costs no quota, only latency and
the CPU to parse it. The alternatives (a slim `list_payload`, or one column per locale)
each add a second write path and a way for two projections to drift, to fix a latency
problem nobody has measured. Phase 5's real page-load timings decide whether it needs
narrowing; the fix stays additive and needs no API change.

### `name_ja`: an indexed column for the name filter

The filter keys on the **source-locale** name. It is a column rather than a `Card` field
because the filter needs an index and the name lives inside a JSON payload no index can
reach; the seeder derives it from `translations['ja'].name`.

Consequences, measured: names collapse from 381 entries in `en` to **296 in every
locale**, and one query returns every card for a character regardless of spelling.
`/api/filter-options` pairs the key with a display label so the dropdown still reads in
the user's language — and picking that label needed its own rule, because the *majority*
spelling is usually the untranslated Japanese one. See [F-015](../archive/findings.md#f-015).

### Search: a literal phrase, always

Every query is wrapped as an FTS5 phrase (`"` … `"`, inner `"` doubled) before it reaches
`MATCH`. That closes the syntax-error class entirely: `a AND`, `-x`, `fub*` and a bare
quote all return **200 with zero hits** rather than 500.

The cost is that FTS5 operators become literal text. That is the intent — this is a card
wiki's search box, and the alternative is an injection surface into FTS5's query language
for a feature nobody asked for.

**Below 3 characters, search falls back to `LIKE`** over `cards_fts.text`. Trigram cannot
match a shorter query and returns *no rows* rather than erroring, which reads as "no such
card": `そら` is 2 characters and matches 27 cards. The fallback scans all 2,448 rows,
which is accepted rather than hidden — it only fires under 3 characters, it is bounded by
the table size, the result is capped, and the response is cached for an hour.

### Fused colours expand at query time

`blue_red` is one printed icon, stored as printed. A request for `blue` therefore queries
`('blue', 'blue_red')`. Without this, filtering blue silently omits those cards — which
is what the live v1 site does today. See [F-016](../archive/findings.md#f-016).

The expansion is deliberately in the query layer: expanding on write would render two
icons and a comma where the card shows one, and the seeder's
`test_fused_colours_are_stored_as_printed` pins that.

### Zod on input; types on output

Zod guards the untrusted boundary, sourced from the generated enums. Output is guaranteed
structurally by `localize()` returning `LocalizedCard`, already pinned byte-for-byte
against the Python reference by the golden files. Validating responses at runtime would
spend CPU per card re-proving what `make check` proves once.

An unknown **locale** degrades to the default rather than failing, matching v1's
`validateLocale`: the site's i18n uses URL prefixes, so a stale link (v1 accepted `sc`,
which the data never had) should not turn a whole page into an error. An unknown **enum
value** is a broken client and does 400.

### Honest failure modes

Three places where v1 failed silently now fail loudly:

- **Batch endpoints reject over 50** rather than slicing to the first 50, which made a
  deck longer than 50 cards render short with no error.
- **`total` is omitted** when `skip_count` is set, rather than returned as `-1`. A typed
  API should not encode "unknown" as a negative count.
- **Route order is not load-bearing.** `/api/cards/:id{[0-9]+}` is constrained to digits,
  so `/api/cards/search` cannot be swallowed however the file is arranged. Ids are
  numeric strings — an invariant the seeder already enforces because the FTS rowid
  depends on it.

### The rate-limit stub is deleted

`checkRateLimit()` is removed rather than ported. Real protection comes from
`Cache-Control` on every read endpoint — 1 h on cards, 24 h on filter-options — with
Cloudflare's dashboard rate-limiting rules as the escape hatch if abuse appears. TTLs are
set against how often data actually changes (a weekly reseed) rather than v1's 5 minutes,
which allowed 288 origin hits per unique query per day.

Headers only, no `caches.default`: for a GET the edge honours the header, and the manual
match/put pair duplicated it while adding a `waitUntil` to every handler.

### Testing without a new framework

The repo's test story is deliberately dependency-free (`node --test`, "no ts-node, no
vitest, no build step"). Phase 4 keeps that: 25 unit tests over the pure query builders,
FTS escaping and Zod schemas, plus a 34-check smoke test that boots `wrangler dev --local`
against the committed fixtures and exercises every endpoint over real HTTP.

`@cloudflare/vitest-pool-workers` was considered and rejected: it is the more faithful
environment, but it costs a substantial dependency tree to test what `wrangler dev` —
the same workerd, the same SQLite — already exercises. Both run in `make check`, and
neither needs a credential (D12).

## Consequences

- **A full reseed was required**, because every `content_hash` changed. Executed against
  production: **49,785 rows written, exactly the estimate**, 18,762 read, 73.0 MB.
  `CARD_INDEX_COUNT` moved 4 → 5.
- **`schema.sql` cannot evolve a populated database.** It is written with
  `CREATE TABLE IF NOT EXISTS`, so re-applying it to the live database silently skipped
  `name_ja` and then failed on the index referencing it. Phase 4 adds
  `packages/schema/sql/migrations/`, and this is the first entry. Structure only — values
  come from the reseed that follows.
- **The v1 API contract changes in three visible ways**: `total` is absent rather than
  `-1`, over-cap batches 400, and colour filters now include fused cards. All three are
  Phase 5 frontend adjustments, and all three are noted where Phase 5 will look.
- Phase 5 should **drop the separate `blue_red` / `white_green` filter checkboxes** —
  those cards now appear under both constituent colours (F-016).
- The 143 KB-per-page payload read is recorded rather than optimised. If Phase 5's
  timings show it matters, the fix is additive.

## Alternatives considered

**A second query against the junction tables**, keeping the schema as Phase 3 shipped it.
No reseed, and the junctions stay the single source of truth. Rejected: it is three extra
queries per list request on the endpoint whose read count breached the free tier, and it
re-introduces the exact fan-out shape `enrichCardDataBatch` was deleted for.

**Real columns for `color_codes` / `card_sets`** rather than payload fields. Same
denormalisation, more legible in the DDL — but it invites someone to later write a `LIKE`
filter against them, which is the anti-pattern ADR 0004 exists to prevent.

**Rejecting queries under 3 characters** with "type at least 3 characters". Costs zero
reads and is honest about the index, but silently breaks 2-character CJK search, which is
a regression against v1 for a language the site serves by default.

**A second `unicode61` FTS index** for short queries. Gives short *Latin* queries a real
index, but unicode61 is precisely what F-013 showed cannot tokenise CJK — so `そら`, the
case that motivated the fallback, still fails. Another ~36 MB and a per-card write on
every seed.
