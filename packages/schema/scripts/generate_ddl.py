"""Generate the D1 schema from the pydantic models' storage annotations.

The fourth generated artifact, after JSON Schema, TypeScript types and enum arrays. v1
declared the card shape in four places — Python, `schema.sql`, `worker.ts`,
`types/card.ts` — and they drifted; this is what stops `schema.sql` becoming the fourth
one again.

    make generate       # regenerate and write
    make check          # verify the committed output is current (fails if stale)

**What is generated and what is not.** The per-field facts come from the annotations:
which fields are columns, their SQL types, which are indexed, which are packed into a
payload, which feed search. Those are the parts that drift when someone adds a field to
`Card`.

The *structural* decisions — that `color_codes` is a junction table rather than a JSON
column, that the FTS table is standalone and trigram-tokenised, that the junctions are
`WITHOUT ROWID` — are written out in `TEMPLATE` below. They are choices about three
specific fields, not properties of every field, and expressing them in the annotation
vocabulary would make the annotations harder to read than the SQL they produce. ADR 0004
records the reasoning and the measurements behind each.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel

from holo_schema import Card
from holo_schema.annotations import Blob, Column, FullText, Junction

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PACKAGE_ROOT / "sql"

BANNER = """-- DO NOT EDIT — generated from the pydantic models in
-- packages/schema/src/holo_schema/. Regenerate with `make generate`;
-- `make check` fails if this file is stale.
--
-- Apply with:
--   npx wrangler d1 execute hololive-ocg-wiki-db --remote \
--       --file=packages/schema/sql/schema.sql
--
-- Run from apps/api/, where wrangler.jsonc declares the binding. Note the database is
-- `hololive-ocg-wiki-db`; `hololive-ocg-wiki` is the Worker's name and does not resolve.
--
-- `holo-data seed` never runs DDL. Schema changes are rare and human-driven; giving an
-- agent-driven command the power to DROP TABLE is exactly the blast radius D10 exists to
-- bound.
"""


def annotations_for(model: type[BaseModel], name: str) -> list[Any]:
    """The storage annotations attached to one model field.

    Pydantic keeps the original `Annotated[...]` metadata on the field info, but only
    the *outer* annotation survives on `Optional[...]` wrappers, so the raw type hint is
    what gets inspected here.
    """
    hint = model.__annotations__.get(name)
    if get_origin(hint) is not Annotated:
        return []
    return list(get_args(hint)[1:])


def first_of(items: list[Any], kind: type) -> Any | None:
    return next((item for item in items if isinstance(item, kind)), None)


def column_definitions() -> tuple[list[str], list[str]]:
    """Emit the `cards` column list and its CREATE INDEX statements.

    Nullability comes from the model: a field pydantic marks required is `NOT NULL`.
    That is the one place the DDL and the contract could silently disagree, so it is
    derived rather than restated.
    """
    columns: list[str] = []
    indexes: list[str] = []

    for name, info in Card.model_fields.items():
        marks = annotations_for(Card, name)
        column = first_of(marks, Column)
        if column is None:
            continue

        parts = [f"    {name} {column.sql_type}"]
        if column.primary_key:
            parts.append("PRIMARY KEY")
        elif info.is_required():
            parts.append("NOT NULL")
        columns.append(" ".join(parts))

        # `unique` implies `indexed` — a UNIQUE INDEX *is* an index, and requiring both
        # flags would let them disagree.
        if (column.indexed or column.unique) and not column.primary_key:
            kind = "UNIQUE INDEX" if column.unique else "INDEX"
            indexes.append(
                f"CREATE {kind} IF NOT EXISTS idx_cards_{name} ON cards({name});"
            )

    return columns, indexes


def junction_tables() -> list[tuple[str, str, str]]:
    """Every `Junction`-annotated field, as (field name, table, value column)."""
    found: list[tuple[str, str, str]] = []
    for name in Card.model_fields:
        junction = first_of(annotations_for(Card, name), Junction)
        if junction is not None:
            found.append((name, junction.table, junction.value_column))
    return found


def fulltext_fields() -> list[str]:
    """Fields carrying `FullText`, ordered by descending weight.

    Recorded as a comment in the DDL rather than as FTS5 columns. The search text is a
    concatenation across all 7 locales and every nested translation, which no single
    column holds — so the index has one `text` column and the weights inform how the
    seeder builds it, not the table shape. See ADR 0004 on why per-locale FTS rows were
    rejected.
    """
    weighted: list[tuple[float, str]] = []
    for name in Card.model_fields:
        mark = first_of(annotations_for(Card, name), FullText)
        if mark is not None:
            weighted.append((mark.weight, name))
    return [f"{name} (weight {weight})" for weight, name in sorted(weighted, reverse=True)]


def blob_fields() -> list[str]:
    return [
        name
        for name in Card.model_fields
        if first_of(annotations_for(Card, name), Blob) is not None
    ]


TEMPLATE = """{banner}
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
{columns},

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
    -- {blobs}.
    payload TEXT NOT NULL,
    -- Q&A only, keyed by locale. Absent on 65% of cards, so frequently '{{}}'.
    qa_payload TEXT NOT NULL DEFAULT '{{}}',

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

{indexes}

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

{junctions}

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
{fts_fields}
-- ---------------------------------------------------------------------------

CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
    card_number,
    text,
    tokenize='trigram'
);
"""


def render() -> str:
    columns, indexes = column_definitions()
    junctions = junction_tables()

    junction_sql = "\n\n".join(
        f"CREATE TABLE IF NOT EXISTS {table} (\n"
        f"    {value_column} TEXT NOT NULL,\n"
        f"    card_id TEXT NOT NULL,\n"
        f"    PRIMARY KEY ({value_column}, card_id)\n"
        f") WITHOUT ROWID;\n\n"
        f"CREATE INDEX IF NOT EXISTS idx_{table}_card_id ON {table}(card_id);"
        for _field, table, value_column in junctions
    )

    # `name_ja` is declared in the template rather than derived from a model field —
    # see the comment beside it — so its index is appended here rather than emitted by
    # `column_definitions()`.
    indexes.append("CREATE INDEX IF NOT EXISTS idx_cards_name_ja ON cards(name_ja);")

    return TEMPLATE.format(
        banner=BANNER.rstrip("\n"),
        columns=",\n".join(columns),
        indexes="\n".join(indexes),
        junctions=junction_sql,
        blobs=", ".join(blob_fields()),
        fts_fields="\n".join(f"--   {entry}" for entry in fulltext_fields()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed output is current; exit 1 if stale. Writes nothing.",
    )
    args = parser.parse_args()

    SQL_DIR.mkdir(parents=True, exist_ok=True)
    target = SQL_DIR / "schema.sql"
    content = render()

    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            print("Generated SQL is out of date:", file=sys.stderr)
            print(f"  {target.relative_to(PACKAGE_ROOT.parent.parent)}", file=sys.stderr)
            print("\nRun `make generate` and commit the result.", file=sys.stderr)
            return 1
        print("✓ schema.sql is current")
        return 0

    target.write_text(content, encoding="utf-8")
    print(f"  wrote {target.relative_to(PACKAGE_ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
