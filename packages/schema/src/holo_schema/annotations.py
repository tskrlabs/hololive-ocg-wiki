"""Storage annotations — how each field lands in D1.

Phase 0 defines the card *shape*. Phase 3 designs the D1 *schema* (decision D8: one
row per card, translations as JSON). These annotations are the bridge: they let Phase 3
generate the DDL from these same models instead of hand-writing a fourth copy of the
card shape in `schema.sql`.

`scripts/generate_ddl.py` reads these to emit `packages/schema/sql/schema.sql`. They
carry the per-field facts — which fields are columns, which are packed into a payload,
which feed search — so adding a field to `Card` updates the DDL rather than silently
leaving D1 behind. The *structural* parts of the schema (junction table shape, index
choices, the FTS declaration) live in the template beside that script; see ADR 0004 for
why the split falls there.

Usage:

    hp: Annotated[Optional[int], Column()] = None
    translations: Annotated[dict[Locale, Translation], Blob()]
    tags: Annotated[Optional[list[str]], Junction("card_tags", "tag")] = None
"""

from dataclasses import dataclass
from typing import Literal

SqlType = Literal["TEXT", "INTEGER", "REAL", "BOOLEAN"]


@dataclass(frozen=True)
class Column:
    """Field becomes a real D1 column.

    Use for anything queried directly: filtered on, sorted by, or joined against.
    Per D8 these are the *filterable* fields — type, colours, rarity, bloom.

    Args:
        sql_type: D1/SQLite column type.
        indexed: emit a `CREATE INDEX` for this column.
        primary_key: this column is the table's primary key.
        json_array: the value is a list stored as a JSON string. SQLite has no array
            type, so `baton_touch_types` is TEXT holding `'["null"]'`. Only for lists
            that are *never filtered on* — a `LIKE '%"x"%'` predicate cannot use an
            index, so a filterable list must be a `Junction` instead. See ADR 0004.
    """

    sql_type: SqlType = "TEXT"
    indexed: bool = False
    primary_key: bool = False
    json_array: bool = False


@dataclass(frozen=True)
class Blob:
    """Field lives inside a JSON payload column, not a column of its own.

    Use for anything only ever read back whole, per-card. Per D8 this is what collapses
    ~48,700 rows into ~2,500: translations, arts, and QA items are fetched with the
    card and never queried in isolation, so they do not need to be rows.

    Search is unaffected — it comes from FTS5, which is a separate index either way.

    Args:
        column: name of the D1 column this field is packed into.
    """

    column: str = "payload"


@dataclass(frozen=True)
class Junction:
    """Field is a list, stored one row per element in its own table.

    Use for a **filterable** list. The alternative — a JSON array in a column, filtered
    with `LIKE '%"blue"%'` — cannot use an index, so it degrades to a full table scan
    however many indexes are declared on it. v1 shipped three such indexes
    (`idx_cards_color_codes` and friends); measured against its live data they were
    never used, and the site read 882 rows per query on a 2,448-row table as a result.

    The junction row is `(value, card_id)` as a `WITHOUT ROWID` primary key, so the key
    *is* the storage: one write per row, no separate index to maintain, and a filter on
    the value is a range scan over a covering index.

    Args:
        table: the junction table's name, e.g. "card_colors".
        value_column: the column holding one element, e.g. "color_code".
    """

    table: str
    value_column: str


@dataclass(frozen=True)
class Derived:
    """Field is not stored — it is computed on read.

    Use for values reconstructible from other fields. Storing them would mean a reseed
    every time the derivation changes, which is exactly the trap D9 identifies: v1
    baked the CDN folder layout and file extension into `image_path`, so changing host
    or format meant rewriting all 2,448 rows.

    Args:
        note: how the value is derived, for the Phase 3 emitter's generated comment.
    """

    note: str = ""


@dataclass(frozen=True)
class FullText:
    """Field feeds the FTS5 search index.

    Orthogonal to Column/Blob — a field can be both stored as a blob and indexed for
    search. Phase 3 builds the FTS5 virtual table from every field carrying this.

    Args:
        weight: relative ranking weight. Higher wins ties; a card name should outrank
            a match buried in a QA answer.
    """

    weight: float = 1.0
