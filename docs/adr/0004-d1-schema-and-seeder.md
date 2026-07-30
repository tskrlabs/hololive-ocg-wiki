# ADR 0004 — the D1 schema and the seeder

**Status:** accepted · **Phase:** 3 · **Date:** 2026-07-27

## Context

Phase 3 designs the database v1 has been running on for a year and builds the tool that
loads it. D8 settled the shape in outline — one row per card, translations as JSON,
filterable fields as indexed columns, FTS5 retained — and D10 settled the gating.

Before building, the live v1 database was measured. Four findings changed the design.

### 1. The site is already over the free tier, on reads

D1 analytics for the 30 days to 2026-07-27:

| metric | value |
|---|---|
| read queries/day (avg) | ~1,200 |
| **rows scanned per query** | **882** |
| rows read/day — median | 722k (14% of quota) |
| rows read/day — p90 | 1.64M (33%) |
| rows read/day — **max** | **5,582,892 — over the 5M/day limit** |
| days above 20% of quota | 10 of 31 |

882 rows scanned per query against a 2,448-row table is the full-table-scan signature.
On 2026-07-12 the site exceeded the free tier and D1 would have started refusing
queries. Traffic is modest — a few thousand API calls a day; the row count is almost
entirely an artifact of how the data is queried.

**Reads are the binding constraint, not writes.** v1 has written zero rows in 30 days.
D8's headline win — 48,700 rows down to 2,500 — optimises the resource with slack.

### 2. The JSON-payload design alone would have made it worse

Measured on the query shape `/api/cards/filter` actually issues — filter, sort by card
number, `LIMIT 50`:

| design | rows read per page |
|---|---|
| v1 today (normalised + 5 enrich queries) | ~882 |
| payload column **+ JSON `color_codes`** | **~2,448 — worse than v1** |
| payload column **+ junction `color_codes`** | **~50–100** |

With colours as a JSON array, `ORDER BY` forces evaluating every match before `LIMIT`
applies, so the whole table is scanned. v1's own `idx_cards_color_codes` never fires:
`EXPLAIN QUERY PLAN` on `color_codes LIKE '%"blue"%'` reports `SCAN cards`. The index
has been paying write cost for a year and returning nothing.

### 3. CJK substring search is broken on the live site

Probing the v1 API:

| query | results |
|---|---|
| `白上フブキ` | 62 |
| `フブキ` | **0** |
| `宝鐘マリン` | 32 |
| `宝鐘` | **0** |

FTS5's default `unicode61` tokenizer treats an unbroken CJK run as a single token, so
only a complete name matches. The site's default locale is `tc` and its source locale is
`ja`. Logged as [F-013](../archive/findings.md#f-013).

### 4. Two plan figures were wrong

- D1's free storage tier is **500 MB**, not the 5 GB in `v2-plan.md` §3 — that is the
  paid number. Not a problem (17 MB of data, 36 MB of index) but worth correcting.
- The real v1 row total is **59,940**, not the 48,700 estimated.

## Decision

### Schema

```
cards          one row per card; payload + qa_payload as JSON columns;
               content_hash + qa_hash as the diff baseline
               indexes: card_number, card_type_code, rarity_code, bloom_level_code
card_colors    (color_code, card_id) WITHOUT ROWID    2,032 rows
card_tags      (tag, card_id)        WITHOUT ROWID    5,443 rows
card_sets      (set_name, card_id)   WITHOUT ROWID    2,592 rows
cards_fts      fts5(card_id UNINDEXED, card_number, text, tokenize='trigram')
               standalone, one row per card, all 7 locales concatenated
```

**Junction tables for the three filterable lists.** This amends D8. `WITHOUT ROWID`
with the value leading the primary key means the key *is* the storage: one write per
row, no separate index, and a filter is a range scan over a covering index. The cost is
+10,067 rows per full reseed, paid in the resource that has 100% of its budget free.

**Payload split in two.** Q&A is 53% of the translation bytes and, per ADR 0002, the
only part that churns once a card is printed. Splitting means a new FAQ entry does not
rewrite a card's rules text, and — the reason that matters for reads — list endpoints
select `payload` alone and never drag 7.5 MB of Q&A through a query that renders 50
tiles.

**FTS: trigram, one row per card.** Trigram indexes every 3-character window, which
makes substring search work in every language the site serves. Measured at 2,448 rows /
36 MB against 17,136 rows / 39.9 MB for a per-card-locale index — nearly the same size
for seven times the rows. v1 partitioned by locale and then searched across all locales
anyway (`worker.ts:469`), so the partition was never used.

Trigram cannot match a query shorter than 3 characters, and returns *no rows* rather
than an error — the dangerous shape, because a 2-character query looks like "no such
card". The Phase 4 worker falls back to `LIKE` below the threshold. Pinned by a test.

Standalone rather than external-content (25% larger, but the indexed text is a
concatenation no column holds) and **no triggers** — the seeder is the only writer, and
a trigger's writes are invisible to `seed --dry`'s accounting, which would break the
gate they are being counted for.

**`/api/filter-options` and `/api/static-filters` move to R2 artifacts.** They return
the same answer for every user until the next reseed and currently run four separate
`SELECT DISTINCT` full scans per call.

### Seeder

**Writes go through the D1 REST API from Python**, not generated SQL through `wrangler`.
Two properties decided it: parameters are bound rather than escaped by hand (our data
carries the official site's raw HTML, which is where a quoting bug becomes silent
corruption), and the response carries per-statement `meta.rows_written`, so `seed`
reports what it *actually* wrote instead of restating its own estimate.

**The diff baseline is D1 itself** — `content_hash` and `qa_hash` columns, read back at
the start of each run. v1 kept it in a committed 648 KB `cards_hash.json`, which can
disagree with the database: seed from a second machine, or crash between the last write
and the hash file being saved, and the next run silently skips cards that were never
written. A column cannot desynchronise from the table it is in, and an interrupted run
resumes with no reconciliation logic. Costs 2,448 rows read — 0.05% of the daily budget.

**Batches are grouped per card.** Verified against the live API: a D1 batch is
**transactional** — an `INSERT` followed by a failing statement left no row behind, and
the response carries no `result` array at all. So a whole group in one batch means a
card is either fully written or not written at all.

**Deleting requires `--prune`.** The failure modes are asymmetric: wrongly keeping a
card leaves a stale entry until someone notices; wrongly deleting 2,448 because a scrape
returned an empty list destroys the database. Paired with a hard refusal when the
incoming card count is more than 10% below what is stored — the empty-scrape signature,
and a fact no flag can argue with.

**The write-budget gate reads actual usage.** `seed` queries the GraphQL analytics API
for today's `rowsWritten` and refuses if the estimate would not fit in what remains.
Checking against the flat 100k limit would be blind to a seed that already ran today,
and the failure that guards against is specific: writes start failing *mid-run*, leaving
the database partially updated. Analytics latency was measured at under a few minutes.
If analytics cannot be read, the run is allowed and the CLI says so — a missing read
permission should not block a legitimate seed.

**`seed` uploads `status.json` itself.** D11 moved it from `publish` because it
describes a database diff. Since `publish` runs *before* `seed`, leaving the upload to
the next `publish` would mean the status page always describes the previous run. It
records D1's own `rows_written`, so it is an audit record rather than a restatement of
the estimate.

### Write accounting

This replaces the plan's "`seed --dry` reports ~2,500 rows", which counted only `cards`
rows — it ignored index writes, junction rows and FTS shadow tables, and was an order of
magnitude out.

| scenario | writes | % of 100k/day |
|---|---|---|
| Full reseed | ~47,300 | 47.3% |
| New card set (~120 cards) | ~2,320 | 2.3% |
| Q&A-only update (100 cards) | ~700 | 0.7% |

Every constant behind these was **measured against production**, not reasoned about —
the first attempt had two of three wrong in opposite directions, and the errors cancelled
just enough to look plausible (it predicted 29,651 and the real seed wrote 27,203). Per
statement group, on a card with 5 junction rows: cards upsert 5 writes, junctions 15,
FTS 2.

FTS5 is the one component that genuinely varies — it batches its index into large `data`
blobs, so inserting into an empty table averaged ~11 shadow rows per card while replacing
a row in a populated one charged 2. The estimator models the *replace* case, which is
what the diff path always does; a first seed into an empty database exceeds it. The CLI
prints the actual figure beside the estimate, so the gap is visible rather than assumed.

### Generated DDL, hand-written structure

`packages/schema/sql/schema.sql` generates from the same pydantic models as the JSON
Schema and the TypeScript types, via a new `Junction` annotation alongside `Column`,
`Blob` and `FullText`. The per-field facts are generated; the structural decisions —
that these three fields are junctions, that the FTS table is standalone and trigram —
live in the template.

The split is deliberate. Junction and FTS shape are choices about three specific fields,
not properties of every field, and contorting the annotation vocabulary to express them
would make the annotations harder to read than the SQL they produce. What matters is the
property that prevents drift: adding a field to `Card` updates the DDL, and `make check`
fails if the committed copy is stale.

DDL is applied with `wrangler d1 execute --file`, never by `seed`. Giving an
agent-driven command the power to `DROP TABLE` is exactly the blast radius D10 bounds.

### Local development

`fixtures/fixtures.sql` is committed, generated from the 34 fixture cards, and applied
with `wrangler d1 execute --local --file`. D12's requirement is that a fresh clone runs
with zero Cloudflare credentials; this satisfies it with no token, no network and no
Python. `seed` is not involved — it is a production tool whose entire design is about
gating writes to a live database, and a `--local` flag on it would invite reaching for
the wrong one.

## What the first production seed changed

The design above was verified locally against the full 2,448-card set before anything
touched D1. The first real seed still exposed a bug that no local test could have found,
because SQLite does not report `rows_read` and D1 does.

**The seed wrote 27,203 rows and read 15,508,419** — three times the daily read budget,
on a command whose entire purpose is writing.

The cause was the junction primary key. `(value, card_id)` is right for the read path
(`WHERE color_code = ?`), but the seeder's *write* path looks rows up the other way
round — `DELETE FROM card_colors WHERE card_id = ?` — and with `card_id` trailing the
composite key that is a skip-scan over the whole table:

```
SEARCH card_colors USING PRIMARY KEY (ANY(color_code) AND card_id=?)
```

12,515 rows read per card. **The read path and the write path want opposite key orders**,
so both need an index. Adding `idx_<table>_card_id` to each junction took the per-card
delete cost to zero.

The same measurement exposed a second instance of the same mistake in the FTS table.
`card_id` was declared `UNINDEXED` — and an FTS5 column *cannot* be indexed for lookup;
it exists to be searched. So `DELETE FROM cards_fts WHERE card_id = ?` scanned all 2,448
rows. The fix is to key on the rowid, the one thing an FTS5 table can address directly:
card ids are numeric strings (verified across all 2,448 — unique, 1..2457, `str(int(x))
== x`), so the rowid carries the id and the redundant column is gone. `rowid_for()`
raises rather than falling back if the scraper ever emits a non-numeric id, because the
fallback would reappear as unexplained read growth months later.

| | before | after |
|---|---|---|
| Full reseed, rows read | **15,508,419** | **~22,850** |
| Per-card delete cost | 12,515 | ~9 |

A 679× reduction, measured on production both times. Both regressions are now pinned by
tests that assert the query plan, so neither can come back silently.

**The lesson worth keeping:** a schema reviewed only against the queries it was designed
for will miss the queries that *maintain* it. Writes look up rows differently from reads,
and on D1 the meter runs on both.

## Consequences

- A full reseed costs 30% of the daily write budget rather than the 2.5% D8 projected.
  Acceptable: writes run at zero, and the typical case — a new card set — is 1.5%.
- Filter queries drop from ~882 rows read to ~50–100, roughly a 10–25× reduction on the
  endpoint that breached the free tier.
- Search works for partial CJK names for the first time.
- The Phase 4 worker needs a `hasCJK`-style length check to route short queries to
  `LIKE`. That is a real branch the schema does not hide.
- **Filter with `WHERE c.id IN (SELECT card_id FROM card_colors WHERE …)`, not a join.**
  A join against a junction table returns one row per matching *value*, so a multi-value
  filter (`colors=blue,red`) would return a card once per colour it matches and corrupt
  pagination counts. The `IN` form returns one row per card and is still fully
  index-driven — verified on real D1: `SEARCH card_colors USING PRIMARY KEY
  (color_code=?)` plus a Bloom filter, no scan.

  Note that duplicate *card numbers* in results are legitimate and not this problem:
  F-006 established that `hBP03-044` is two genuinely different cards. Deduplicate on
  `id`, never on `card_number`.
- `FullText(weight=…)` annotations no longer drive anything mechanical: a trigram index
  over one concatenated column cannot apply per-field weights. They survive as a record
  of what belongs in the index. If ranking quality becomes a complaint, the escape hatch
  is a second `unicode61` index for Latin queries — considered and deferred.

## Alternatives considered

**JSON columns with the indexes dropped.** Initially recommended during design, before
the traffic data was read: the indexes are provably unused, so removing them looked like
a strict improvement. It was wrong — it would have made the filtered-page path *worse*
than v1 (2,448 rows vs 882), because the payload design removes the joins but not the
scan. The junction tables are what make the payload design pay off.

**Per-card-locale FTS rows**, as v1 has. 7× the rows for 4 MB more index and a locale
partition v1 never used.

**Hash file in R2** as the diff baseline. Simpler, but can disagree with the database.

**A `seeded_at`-based status endpoint** instead of `status.json`. Cleaner, but loses the
run boundary — two seeds in one day merge — and spends rows on the endpoint we are
trying to keep cheap.
