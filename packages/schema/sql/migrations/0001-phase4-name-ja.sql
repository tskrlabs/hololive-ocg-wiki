-- Phase 4 — add `name_ja` to an existing database.
--
-- Apply from apps/api/ with:
--   npx wrangler d1 execute hololive-ocg-wiki-db --remote \
--       --file=../../packages/schema/sql/migrations/0001-phase4-name-ja.sql
--
-- Why this file exists at all: `schema.sql` is written with `CREATE TABLE IF NOT
-- EXISTS`, so re-applying it to a populated database is a no-op that silently skips new
-- columns — and then fails on the index that references one. It can build a database
-- from nothing; it cannot evolve one. This is the first schema change since the database
-- was populated, so it is the first time that mattered.
--
-- Migrations are for *structure only*. The values are written by the reseed that follows
-- (`holo-data seed --confirm`), which rewrites every row anyway because the payload shape
-- changed in the same phase. Nothing here backfills data, so nothing here has to be
-- correct about a card.
--
-- Safe to re-run only in the sense that it will fail loudly on the second attempt
-- ("duplicate column name"). That is deliberate: a migration that silently does nothing
-- is indistinguishable from one that silently did the wrong thing.

-- The card's name in the source locale — the `name` filter's key. See the commentary
-- beside its declaration in schema.sql for why it is the ja name and not the requested
-- locale's (findings F-015).
--
-- Added with a default because the column is NOT NULL in schema.sql and the table has
-- 2,448 existing rows. The reseed immediately overwrites every one of them; a row still
-- carrying '' afterwards means the seed did not complete.
ALTER TABLE cards ADD COLUMN name_ja TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_cards_name_ja ON cards(name_ja);
