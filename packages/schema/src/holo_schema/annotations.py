"""Storage annotations — how each field lands in D1.

Phase 0 defines the card *shape*. Phase 3 designs the D1 *schema* (decision D8: one
row per card, translations as JSON). These annotations are the bridge: they let Phase 3
generate the DDL from these same models instead of hand-writing a fourth copy of the
card shape in `schema.sql`.

Nothing reads these yet. They exist so that the Phase 3 emitter is a ~50-line script
over already-recorded intent, rather than a fresh set of decisions made months later
against a model file that has forgotten why each field is the way it is.

Usage:

    hp: Annotated[Optional[int], Column()] = None
    translations: Annotated[dict[Locale, Translation], Blob()]
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
            type, so `color_codes` is TEXT holding `'["blue","red"]'`. Kept as a
            column rather than a blob because v1 filters on it with LIKE, and Phase 3
            may promote it to a junction table if that proves too slow.
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
