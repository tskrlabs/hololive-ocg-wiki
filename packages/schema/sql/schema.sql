-- DO NOT EDIT — generated from the pydantic models in
-- packages/schema/src/holo_schema/. Regenerate with `make generate`;
-- `make check` fails if this file is stale.
--
-- Apply with:
--   npx wrangler d1 execute hololive-ocg-wiki-db --remote --       --file=packages/schema/sql/schema.sql
--
-- Run from apps/api/, where wrangler.jsonc declares the binding. Note the database is
-- `hololive-ocg-wiki-db`; `hololive-ocg-wiki` is the Worker's name and does not resolve.
--
-- `holo-data seed` never runs DDL. Schema changes are rare and human-driven; giving an
-- agent-driven command the power to DROP TABLE is exactly the blast radius D10 exists to
-- bound.
-- ---------------------------------------------------------------------------
-- cards — one row per card (D8).
--
-- v1 spread a card across 7 tables and ~59,940 rows; rendering a page of 50 cards
-- meant a 6-way join plus five follow-up queries against child tables. Everything a
-- card needs that is never queried in isolation now lives in two JSON columns.
--
-- payload and qa_payload are split because Q&A is 53% of the translation bytes and,
-- per ADR 0002, the only part that churns after a card is printed. Splitting means a
-- new FAQ entry does not rewrite the card's rules text, and — the reason that matters —
-- list endpoints select `payload` alone and never drag 7.5 MB of Q&A through a query
-- that renders 50 tiles.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    card_number TEXT NOT NULL,
    card_type_code TEXT NOT NULL,
    rarity_code TEXT NOT NULL,
    bloom_level_code TEXT,
    image_key TEXT NOT NULL,
    source_image_url TEXT NOT NULL,
    hp INTEGER,
    life INTEGER,
    baton_touch_count INTEGER,
    baton_touch_types TEXT,
    illustrator TEXT,

    -- The card's name in the source locale — the stable per-character identity, and
    -- what the `name` filter ("show me every Fubuki card") matches on.
    --
    -- Not a `Card` field: it is a projection of translations['ja'].name, derived by the
    -- seeder. It exists as a column because the filter needs an index, and the name
    -- lives inside a JSON payload that no index can reach.
    --
    -- Deliberately the *ja* name, not the requested locale's. 122 of 296 characters
    -- (41%) have an inconsistent name in at least one locale — Shirakami Fubuki's 44
    -- cards carry both "Shirakami Fubuki" and "白上フブキ" in `en` — so v1's
    -- per-locale exact match split those characters into two filter entries that each
    -- returned a subset. The ja name is the one key that groups them all. The API pairs
    -- it with the locale's display name so the dropdown still reads in the user's
    -- language. See findings F-015.
    name_ja TEXT NOT NULL,

    -- Language-independent nested data plus all 7 locales' translations, minus Q&A:
    -- color_codes, card_sets, arts, keyword, oshi_skill, sp_oshi_skill, translations.
    payload TEXT NOT NULL,
    -- Q&A only, keyed by locale. Absent on 65% of cards, so frequently '{}'.
    qa_payload TEXT NOT NULL DEFAULT '{}',

    -- The diff baseline (ADR 0004). `seed` compares these against the incoming build
    -- to decide what to write. They live here rather than in a separate artifact
    -- because a file can desynchronise from the database and a column cannot: an
    -- interrupted run resumes correctly with no reconciliation.
    content_hash TEXT NOT NULL,
    qa_hash TEXT NOT NULL,

    -- The *source* baseline (ADR 0009 D26) — and the one column here that decides
    -- nothing about writes.
    --
    -- content_hash covers the translated payload, all seven locales, so a re-translation
    -- marks every card changed while the official card list did nothing. That is a true
    -- statement about our database and a false one about the game. This hash covers the
    -- JP text and the language-independent columns only, so it moves when — and only
    -- when — the official site changed the card.
    --
    -- Q&A is excluded for the reason qa_hash exists: "they errata'd eleven cards" and
    -- "they added FAQs to eleven cards" are different sentences, and a reader wants both.
    --
    -- Nullable, unlike its two neighbours, because NULL is a meaningful third state:
    -- *unknown*, on a row written before this column existed. The seeder reads that as
    -- source-unchanged and backfills silently — treating it as "changed" would report
    -- every card as an official update on the first run after the migration.
    source_hash TEXT,

    -- The run that last wrote this row, for status.json and for debugging.
    seeded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cards_card_number ON cards(card_number);
CREATE INDEX IF NOT EXISTS idx_cards_card_type_code ON cards(card_type_code);
CREATE INDEX IF NOT EXISTS idx_cards_rarity_code ON cards(rarity_code);
CREATE INDEX IF NOT EXISTS idx_cards_bloom_level_code ON cards(bloom_level_code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_image_key ON cards(image_key);
CREATE INDEX IF NOT EXISTS idx_cards_name_ja ON cards(name_ja);

-- ---------------------------------------------------------------------------
-- Junction tables — the filterable lists.
--
-- WITHOUT ROWID with the value leading the primary key, so `WHERE color_code = ?` — the
-- read path, and the hot one — is a range scan over a covering index.
--
-- These are not a normalisation preference. v1 stored these three as JSON arrays with
-- an index on each, and a `LIKE '%"blue"%'` predicate cannot use an index — measured
-- against v1's live database, the site read 882 rows per query on a 2,448-row table and
-- breached the 5M/day free-tier read limit on 2026-07-12 (findings F-014).
--
-- Each table also carries an index on card_id alone, because the *write* path looks
-- rows up the other way round: the seeder issues `DELETE FROM … WHERE card_id = ?` per
-- card. With only the composite key that is a skip-scan over the whole table
-- (`SEARCH … USING PRIMARY KEY (ANY(color_code) AND card_id=?)`), which cost 12,515
-- rows read per card — 15.5M for a full reseed, three times the daily read budget.
-- Measured on the first production seed, not predicted. See ADR 0004.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS card_colors (
    color_code TEXT NOT NULL,
    card_id TEXT NOT NULL,
    PRIMARY KEY (color_code, card_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_card_colors_card_id ON card_colors(card_id);

CREATE TABLE IF NOT EXISTS card_sets (
    set_name TEXT NOT NULL,
    card_id TEXT NOT NULL,
    PRIMARY KEY (set_name, card_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_card_sets_card_id ON card_sets(card_id);

CREATE TABLE IF NOT EXISTS card_tags (
    tag TEXT NOT NULL,
    card_id TEXT NOT NULL,
    PRIMARY KEY (tag, card_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_card_tags_card_id ON card_tags(card_id);

-- ---------------------------------------------------------------------------
-- cards_fts — full-text search.
--
-- tokenize='trigram' rather than the default unicode61. unicode61 treats an unbroken
-- CJK run as a single token, so on the live v1 site 白上フブキ returns 62 cards and
-- フブキ returns zero — the site's default locale is tc and its source locale is ja
-- (findings F-013). Trigram indexes every 3-character window, which makes substring
-- search work in every language the site serves.
--
-- Trigram cannot match a query shorter than 3 characters; it returns no rows rather
-- than erroring. The Phase 4 worker falls back to LIKE below that threshold.
--
-- One row per card, all 7 locales concatenated into `text`. Measured: 2,448 rows at
-- 36 MB, against 17,136 rows at 39.9 MB for a per-card-locale index — nearly the same
-- size for 7x the rows. v1 partitioned by locale and then searched across all locales
-- anyway (worker.ts:469), so the partition was never used.
--
-- Standalone rather than external-content: the indexed text is a concatenation no
-- single column holds. No triggers — the seeder is the only writer, and a trigger's
-- writes are invisible to `seed --dry`'s budget accounting, which would break the D10
-- gate.
--
-- **The rowid is the card id.** An FTS5 column cannot be indexed for lookup — it exists
-- to be searched, not queried — so `DELETE … WHERE card_id = ?` scans the whole table:
-- 2,448 rows read per card, ~6M for a reseed. Deleting by rowid reads *zero*, because
-- rowid is the one key an FTS5 table can address directly. Card ids are numeric strings
-- (verified across all 2,448: unique, 1..2457, str->int->str stable), so the rowid can
-- carry the id rather than duplicating it in an UNINDEXED column.
--
-- The seeder enforces the numeric-id assumption and fails loudly if the scraper ever
-- emits a non-numeric id, rather than silently seeding a database it cannot update.
--
-- Fields feeding this index, by weight:
--   card_number (weight 2.0)
--   tags (weight 1.0)
--   illustrator (weight 1.0)
-- ---------------------------------------------------------------------------

CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
    card_number,
    text,
    tokenize='trigram'
);
