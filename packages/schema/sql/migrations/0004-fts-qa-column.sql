-- issue #67 — give Q&A its own FTS column, so a ruling stops outranking the card it
-- cites.
--
-- Apply from apps/api/ with:
--   npx wrangler d1 execute hololive-ocg-wiki-db --remote \
--       --file=../../packages/schema/sql/migrations/0004-fts-qa-column.sql
--
-- ⚠️ **This leaves the search index EMPTY.** Run `holo-data seed --confirm --full`
-- immediately afterwards; until it finishes, every search on the site returns nothing.
-- The seeder refuses to run against the *old* shape (it probes for `qa` first), so the
-- two halves cannot be done out of order — but they can be left half-done, and this is
-- the only migration here where the gap between them is user-visible.
--
-- ---------------------------------------------------------------------------
-- Why the table is dropped rather than altered.
--
-- `ALTER TABLE cards_fts ADD COLUMN qa` fails: `virtual tables may not be altered:
-- SQLITE_ERROR`. FTS5 has no in-place column addition at all, so a new column means a
-- new table. Verified against D1 before this file was written, not assumed from the
-- SQLite docs.
--
-- Nothing else references `cards_fts` — no foreign keys, no triggers, no views (the
-- seeder is the only writer, by ADR 0004's design) — so dropping it takes nothing with
-- it. The card rows are untouched; `payload` and `qa_payload` still hold every word the
-- index is built from, which is why this is recoverable by re-running the seed rather
-- than by re-scraping.
--
-- ---------------------------------------------------------------------------
-- Why the migration does not refill the index itself.
--
-- It could: D1 supports the JSON extension, and `json_tree(payload)` will happily
-- produce every string in a card's payload in one `INSERT … SELECT`. It was tried, and
-- rejected — the text it yields is *not* what `search_text()` yields. It sweeps up enum
-- codes stored in the payload (`white`, `once_per_turn`, `oshiCharacter`) and the
-- product set names, none of which the Python includes, and it cannot reproduce the
-- ordering. The index would then have been built by one rule here and a different rule
-- on every subsequent seed, with the difference invisible until somebody searched for
-- `once_per_turn` and got 2,463 hits.
--
-- So this file does the part that must be SQL — the table shape — and `search_text()` /
-- `qa_text()` stay the single definition of what is searchable. That is the same split
-- ADR 0004 makes between generated DDL and the seeder's content.
--
-- ---------------------------------------------------------------------------
-- Why `qa` is a column and not simply deleted.
--
-- Q&A was 88% of the indexed text by volume, which is why it dominated: `ORDER BY rank`
-- weights every column 1.0, so a card whose FAQ merely *cites* `hSD01-001` scored like
-- the card numbered `hSD01-001`. Production returned 65 cards for `hSD01` of which 39
-- were hSD01; 29 of 73 `白上フブキ` hits were cards that only mention her.
--
-- Dropping Q&A from the index would fix the ranking and lose a real use — looking up a
-- ruling by its wording. A separate column keeps both: `bm25(cards_fts, 2.0, 1.0, 0.1)`
-- ranks card text first and still returns the rulings underneath. The weights are the
-- ones the models already declare via `FullText` (a name is 3.0, a Q&A field 0.5) — an
-- annotation that until now could not act, because a trigram index cannot weight fields
-- *within* a column.
--
-- ---------------------------------------------------------------------------
-- Re-running this is safe in the sense that matters: it drops and recreates an empty
-- table, so a second run costs another reseed but cannot corrupt anything. Unlike 0001
-- and 0003 it does not fail loudly on the second attempt — there is no duplicate-column
-- error to raise — so the thing to check before running it twice is whether a seed is
-- currently in flight.

DROP TABLE IF EXISTS cards_fts;

CREATE VIRTUAL TABLE cards_fts USING fts5(
    card_number,
    text,
    qa,
    tokenize='trigram'
);
