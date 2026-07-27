"""Seed D1 from the published artifact — row mapping, diff, and write accounting.

Replaces v1's `migrate.js` (23 KB of Node) and `diff-status.js`. The CLI wrapper is in
`cli.py`; everything that decides *what* to write lives here so it can be tested against
a local SQLite file with no credentials.

**The diff baseline is D1 itself.** Every row carries `content_hash` and `qa_hash`;
`seed` reads those 2,448 hashes back and compares. v1 kept the baseline in a committed
648 KB `cards_hash.json`, which can disagree with the database — seed from a second
machine, or crash between the last write and the hash file being saved, and the next run
silently skips cards that were never written. A column cannot desynchronise from the
table it is in. Reading it costs 2,448 rows against a 5M/day budget.

**Two hashes, because Q&A is the only thing that churns.** ADR 0002 established that a
card's printed text does not change once published; Q&A is the exception. It is also 53%
of the translation bytes. Splitting the hash lets `status.json` keep v1's "FAQ-only
update" category, and splitting the *payload* means a new FAQ entry does not rewrite the
card's rules text.

**Writes are gated on measured budget, not a constant.** See `plan()`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any, Iterable, Sequence, get_args, get_origin

from holo_schema import Card, CardCollection
from holo_schema.annotations import Junction
from holo_schema.enums import LOCALE_VALUES

from . import d1


def _junction_fields() -> list[tuple[str, str, str]]:
    """Junction-annotated fields as (field, table, value column).

    Read off the contract rather than restated here — the same annotations
    `generate_ddl.py` builds the tables from, so the seeder cannot write to a table
    shape the DDL did not create.
    """
    found: list[tuple[str, str, str]] = []
    for name in Card.model_fields:
        hint = Card.__annotations__.get(name)
        if get_origin(hint) is not Annotated:
            continue
        for mark in get_args(hint)[1:]:
            if isinstance(mark, Junction):
                found.append((name, mark.table, mark.value_column))
    return found


JUNCTIONS = _junction_fields()

# The `cards` table's own columns, in DDL order. Everything else is payload.
CARD_COLUMNS = (
    "id",
    "card_number",
    "card_type_code",
    "rarity_code",
    "bloom_level_code",
    "image_key",
    "source_image_url",
    "hp",
    "life",
    "baton_touch_count",
    "baton_touch_types",
    "illustrator",
)

# What D1 charges per card. Every constant here was measured against the production
# database rather than reasoned about, because the first attempt got two of the three
# wrong in opposite directions and the errors cancelled just enough to look plausible.
#
# Measured on one card with 5 junction rows (`meta.rows_written` per statement group):
#
#     cards upsert       1 statement   ->  5 writes   (1 row + 4 indexes)
#     junction del+ins   8 statements  -> 15 writes   (~3 per row)
#     fts del+ins        2 statements  ->  2 writes
#
CARD_INDEX_COUNT = 4

# A junction row costs ~3: the WITHOUT ROWID key, the card_id index entry, and the
# delete that precedes it (the seeder replaces a card's rows rather than diffing them).
JUNCTION_WRITE_MULTIPLIER = 3

# FTS5 is the one component that genuinely varies. It batches its index into large
# `data` blobs, so the charge depends on how much text is being merged: inserting into
# an empty table averaged ~11 shadow rows per card, while replacing a row in a populated
# one charged 2. This is the *replace* case, which is what the diff path always does;
# a first seed into an empty table will exceed the estimate, and the CLI prints the
# actual figure next to it so the gap is visible rather than assumed.
FTS_WRITE_MULTIPLIER = 2

# Refuse if the incoming set is dramatically smaller than what is stored. This is the
# empty-or-partial-scrape signature, and unlike a flag it is a fact an agent cannot
# argue with (D4, D10).
SHRINK_REFUSAL_RATIO = 0.10


class NonNumericCardId(ValueError):
    """A card id that cannot be an FTS rowid.

    Raised rather than worked around, because the fallback — an UNINDEXED `card_id`
    column — costs 2,448 rows read per card to delete, and would appear as a gradual
    read-budget problem months later rather than as an error here.
    """


def rowid_for(card_id: str) -> int:
    """The FTS rowid for a card, which is its id as an integer.

    Every card id in the dataset is a numeric string (verified across all 2,448: unique,
    1..2457, `str(int(x)) == x`). That lets the FTS table address a card by rowid — the
    only key an FTS5 table can look up directly — instead of carrying a duplicate
    UNINDEXED column that cannot be searched by.

    If the official site ever issues a non-numeric id, this fails at seed time with an
    explanation instead of silently building an index the seeder cannot maintain.
    """
    if not card_id.isdigit():
        raise NonNumericCardId(
            f"card id {card_id!r} is not numeric, and the FTS index uses the card id as "
            "its rowid (see packages/schema/sql/schema.sql).\n\n"
            "Give cards_fts its own INTEGER surrogate key and a card_id -> rowid "
            "mapping, or reconsider the FTS shape — but do not fall back to an "
            "UNINDEXED card_id column: deleting by it costs a full table scan per card."
        )
    return int(card_id)


def _canonical(value: Any) -> str:
    """Stable JSON for hashing — sorted keys, no whitespace drift, UTF-8 as-is."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def card_payloads(card: Card) -> tuple[str, str]:
    """Split a card into its stable payload and its volatile Q&A payload.

    Returns (payload, qa_payload) as JSON text. `exclude_none=True` matches what
    `build` writes to cards.json — absent fields are omitted, never null (ADR 0001).
    """
    dumped = card.model_dump(mode="json", exclude_none=True)

    qa: dict[str, Any] = {}
    translations: dict[str, Any] = {}
    for locale, translation in (dumped.get("translations") or {}).items():
        items = translation.get("qa_items")
        if items:
            qa[locale] = items
        translations[locale] = {
            key: value for key, value in translation.items() if key != "qa_items"
        }

    payload = {
        "arts": dumped.get("arts"),
        "keyword": dumped.get("keyword"),
        "oshi_skill": dumped.get("oshi_skill"),
        "sp_oshi_skill": dumped.get("sp_oshi_skill"),
        "translations": translations,
    }
    payload = {key: value for key, value in payload.items() if value is not None}

    return _canonical(payload), _canonical(qa)


def search_text(card: Card) -> str:
    """Everything searchable about a card, all 7 locales concatenated.

    One FTS row per card rather than one per card-locale: measured at 2,448 rows / 36 MB
    against 17,136 rows / 39.9 MB, and v1 searched across all locales anyway
    (worker.ts:469) despite paying for the partition. See ADR 0004.

    Field weights are recorded on the models via `FullText`, but a trigram index over a
    single concatenated column cannot apply per-field weights — the annotation survives
    as documentation of intent and as the list of what belongs in here at all.
    """
    parts: list[str] = [card.card_number]
    if card.illustrator:
        parts.append(card.illustrator)
    parts.extend(card.tags or [])

    for locale in LOCALE_VALUES:
        translation = card.translations.get(locale)
        if translation is None:
            continue
        parts.append(translation.name)
        parts.extend(translation.tags or [])
        for value in (translation.ability_text, translation.extra):
            if value:
                parts.append(value)
        for art in translation.arts or []:
            parts.append(art.name)
            if art.effect:
                parts.append(art.effect)
        for skill in (translation.oshi_skill, translation.sp_oshi_skill):
            if skill:
                parts.extend([skill.name, skill.effect])
        if translation.keyword:
            parts.extend([translation.keyword.name, translation.keyword.effect])
        for item in translation.qa_items or []:
            parts.extend([item.title, item.question, item.answer])

    return " ".join(part for part in parts if part)


@dataclass(frozen=True)
class CardRow:
    """One card, reduced to exactly what goes into the database."""

    id: str
    columns: tuple[Any, ...]
    payload: str
    qa_payload: str
    content_hash: str
    qa_hash: str
    junction_values: dict[str, list[str]]
    search_text: str


def to_row(card: Card) -> CardRow:
    payload, qa_payload = card_payloads(card)

    columns: list[Any] = []
    for name in CARD_COLUMNS:
        value = getattr(card, name)
        # SQLite has no array type; these are the lists that are never filtered on.
        if isinstance(value, list):
            value = _canonical(value)
        columns.append(value)

    # The content hash covers the columns and the stable payload — everything except
    # Q&A. A card whose only change is a new FAQ entry keeps its content_hash, which is
    # what lets status.json separate the two and what stops a 73 KB row rewrite.
    content_hash = hashlib.sha256(
        _canonical([columns, payload]).encode("utf-8")
    ).hexdigest()
    qa_hash = hashlib.sha256(qa_payload.encode("utf-8")).hexdigest()

    return CardRow(
        id=card.id,
        columns=tuple(columns),
        payload=payload,
        qa_payload=qa_payload,
        content_hash=content_hash,
        qa_hash=qa_hash,
        junction_values={
            table: list(getattr(card, field_name) or [])
            for field_name, table, _value_column in JUNCTIONS
        },
        search_text=search_text(card),
    )


def statements_for(row: CardRow, seeded_at: str) -> list[d1.Statement]:
    """Every statement needed to bring one card up to date.

    Returned as one group so the caller can keep it inside a single batch. D1 batches
    are atomic (verified against the live API), so an un-split group means a card is
    either fully written or not written at all — no half-updated rows to reconcile after
    an interrupted run.

    Junction and FTS rows are deleted then re-inserted rather than diffed: a card has at
    most 17 sets and typically 1-3 of anything else, so computing a minimal delta would
    cost more code than it saves writes.
    """
    placeholders = ", ".join("?" for _ in range(len(CARD_COLUMNS) + 5))
    statements = [
        d1.Statement(
            f"INSERT INTO cards ({', '.join(CARD_COLUMNS)}, payload, qa_payload, "
            f"content_hash, qa_hash, seeded_at) VALUES ({placeholders}) "
            "ON CONFLICT(id) DO UPDATE SET "
            + ", ".join(
                f"{name} = excluded.{name}"
                for name in (
                    *CARD_COLUMNS[1:],
                    "payload",
                    "qa_payload",
                    "content_hash",
                    "qa_hash",
                    "seeded_at",
                )
            ),
            (
                *row.columns,
                row.payload,
                row.qa_payload,
                row.content_hash,
                row.qa_hash,
                seeded_at,
            ),
        )
    ]

    for _field_name, table, value_column in JUNCTIONS:
        statements.append(
            d1.Statement(f"DELETE FROM {table} WHERE card_id = ?", (row.id,))
        )
        for value in row.junction_values.get(table, []):
            statements.append(
                d1.Statement(
                    f"INSERT OR IGNORE INTO {table} ({value_column}, card_id) "
                    "VALUES (?, ?)",
                    (value, row.id),
                )
            )

    # By rowid, not by a card_id column. An FTS5 column cannot be indexed for lookup, so
    # `WHERE card_id = ?` scans the table — 2,448 rows read per card, ~6M for a reseed,
    # measured on the first production seed. By rowid it reads zero.
    statements.append(d1.Statement("DELETE FROM cards_fts WHERE rowid = ?", (rowid_for(row.id),)))
    statements.append(
        d1.Statement(
            "INSERT INTO cards_fts (rowid, card_number, text) VALUES (?, ?, ?)",
            (rowid_for(row.id), row.columns[1], row.search_text),
        )
    )

    return statements


def estimate_writes(rows: Sequence[CardRow]) -> int:
    """How many rows D1 will charge for writing these cards.

    Counts what the platform counts, not what the schema shows: an indexed column adds a
    written row per insert, and FTS5 writes to its shadow tables. v1's estimator counted
    only the visible rows, which is how "a full reseed is ~2,500 writes" came to be off
    by an order of magnitude.
    """
    total = 0
    for row in rows:
        total += 1 + CARD_INDEX_COUNT
        total += (
            sum(len(values) for values in row.junction_values.values())
            * JUNCTION_WRITE_MULTIPLIER
        )
        total += FTS_WRITE_MULTIPLIER
    return total


@dataclass
class SeedPlan:
    """What `seed` intends to do, computed before it does any of it."""

    new: list[CardRow] = field(default_factory=list)
    changed: list[CardRow] = field(default_factory=list)
    qa_updated: list[CardRow] = field(default_factory=list)
    unchanged: int = 0
    missing_ids: list[str] = field(default_factory=list)
    stored_count: int = 0
    incoming_count: int = 0

    @property
    def to_write(self) -> list[CardRow]:
        return [*self.new, *self.changed, *self.qa_updated]

    @property
    def estimated_writes(self) -> int:
        # A pruned card costs one delete per table it appears in; approximated as one
        # per junction plus the card row and its FTS row.
        return estimate_writes(self.to_write)

    @property
    def is_empty(self) -> bool:
        return not self.to_write and not self.missing_ids


def diff(
    rows: Sequence[CardRow], stored: dict[str, tuple[str, str]]
) -> SeedPlan:
    """Compare the build against what D1 already holds.

    `stored` maps card id to (content_hash, qa_hash) as read back from the database.
    """
    plan = SeedPlan(stored_count=len(stored), incoming_count=len(rows))

    for row in rows:
        existing = stored.get(row.id)
        if existing is None:
            plan.new.append(row)
        elif existing[0] != row.content_hash:
            plan.changed.append(row)
        elif existing[1] != row.qa_hash:
            plan.qa_updated.append(row)
        else:
            plan.unchanged += 1

    incoming_ids = {row.id for row in rows}
    plan.missing_ids = sorted(id_ for id_ in stored if id_ not in incoming_ids)
    return plan


@dataclass
class Refusal:
    """A gate that failed, with the reason and what to do about it."""

    reason: str
    detail: str


def check_gates(
    plan: SeedPlan,
    collection: CardCollection,
    schema_version: int,
    writes_used: int | None,
    prune: bool,
) -> list[Refusal]:
    """The hard refusals — the ones no flag can override.

    Each is a *fact* rather than a ceremony: an agent driving this CLI (D4) cannot
    satisfy any of them by adding an argument, which is the property D10 asks for. The
    flag-gated actions (`--prune`, `--full`, `--confirm`) are handled by the CLI.
    """
    refusals: list[Refusal] = []

    if collection.schema_version != schema_version:
        refusals.append(
            Refusal(
                "schema version mismatch",
                f"cards.json declares schema_version {collection.schema_version}; "
                f"this seeder understands {schema_version}. Rebuild, or update the "
                "seeder — do not seed a shape it cannot reason about.",
            )
        )

    # The empty-scrape signature. Deleting is already gated behind --prune, but a
    # collapse this large means the *build* is wrong, so even writing the survivors
    # would publish a broken dataset.
    if plan.stored_count and plan.incoming_count < plan.stored_count * (
        1 - SHRINK_REFUSAL_RATIO
    ):
        shortfall = plan.stored_count - plan.incoming_count
        refusals.append(
            Refusal(
                "the incoming card set is much smaller than what is stored",
                f"D1 holds {plan.stored_count} cards, the build has "
                f"{plan.incoming_count} — {shortfall} fewer "
                f"({100 * shortfall / plan.stored_count:.0f}%). That is what a failed "
                "or partial scrape looks like. Re-run `holo-data scrape` and `build`, "
                "and check `holo-data verify`.",
            )
        )

    estimated = plan.estimated_writes
    if writes_used is not None:
        remaining = d1.DAILY_WRITE_LIMIT - writes_used
        if estimated > remaining:
            refusals.append(
                Refusal(
                    "not enough of today's D1 write budget left",
                    f"this run needs ~{estimated:,} writes; {remaining:,} of "
                    f"{d1.DAILY_WRITE_LIMIT:,} remain today "
                    f"({writes_used:,} already used). The budget resets at 00:00 UTC. "
                    "Running anyway would fail partway through and leave the database "
                    "half-updated.",
                )
            )
    elif estimated > d1.DAILY_WRITE_LIMIT:
        refusals.append(
            Refusal(
                "the run exceeds the daily D1 write limit",
                f"~{estimated:,} writes against a {d1.DAILY_WRITE_LIMIT:,}/day limit.",
            )
        )

    if plan.missing_ids and not prune:
        # Not a refusal — reported so the operator knows, and acted on only with
        # --prune. Deleting is the one irreversible thing seed can do (ADR 0004).
        pass

    return refusals


def read_stored_hashes(
    http: Any, config: d1.D1Config
) -> dict[str, tuple[str, str]]:
    """Read every card's hashes back from D1 — the diff baseline.

    2,448 rows read per seed. Against a 5M/day budget that is 0.05%, and it buys a
    baseline that cannot disagree with the database.
    """
    rows = d1.query(http, config, "SELECT id, content_hash, qa_hash FROM cards")
    return {
        str(row["id"]): (str(row["content_hash"]), str(row["qa_hash"]))
        for row in rows
    }


def prune_statements(ids: Iterable[str]) -> list[list[d1.Statement]]:
    """Delete cards that vanished from the source. One group per card."""
    groups: list[list[d1.Statement]] = []
    for card_id in ids:
        group = [d1.Statement("DELETE FROM cards WHERE id = ?", (card_id,))]
        for _field_name, table, _value_column in JUNCTIONS:
            group.append(
                d1.Statement(f"DELETE FROM {table} WHERE card_id = ?", (card_id,))
            )
        group.append(
            d1.Statement("DELETE FROM cards_fts WHERE rowid = ?", (rowid_for(card_id),))
        )
        groups.append(group)
    return groups


def build_status(
    plan: SeedPlan,
    collection: CardCollection,
    report: d1.WriteReport | None,
    mode: str,
    pruned: Sequence[str] = (),
) -> dict[str, Any]:
    """The `status.json` artifact — what this run actually did.

    D11 moved this from `publish` to `seed` because it describes a *database diff*,
    which is knowledge `publish` cannot have. It records D1's own `rows_written` rather
    than the estimate, so it is an audit record of the run and not a restatement of what
    we hoped would happen.

    Entry shape follows v1's so the Phase 5 status page needs no reshaping, minus
    `imagePath` — D9 replaced it with `image_key`, and the page composes the URL.
    """
    by_id = {card.id: card for card in collection.cards}

    def entry(row: CardRow) -> dict[str, Any]:
        card = by_id.get(row.id)
        name = None
        if card is not None:
            for locale in ("en", "ja"):
                translation = card.translations.get(locale)
                if translation is not None:
                    name = translation.name
                    break
        return {
            "id": row.id,
            "card_number": row.columns[1],
            "image_key": card.image_key if card else None,
            "name": name,
        }

    def by_number(item: dict[str, Any]) -> tuple[str, str]:
        return (item.get("card_number") or f"~{item['id']}", item["id"])

    status: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "built_at": collection.generated_at,
        "mode": mode,
        "counts": {
            "total": plan.incoming_count,
            "new": len(plan.new),
            "changed": len(plan.changed),
            "qa_updated": len(plan.qa_updated),
            "unchanged": plan.unchanged,
            "removed": len(pruned),
            "missing_from_build": len(plan.missing_ids),
        },
        "new": sorted((entry(row) for row in plan.new), key=by_number),
        "changed": sorted((entry(row) for row in plan.changed), key=by_number),
        "qa_updated": sorted((entry(row) for row in plan.qa_updated), key=by_number),
        "removed": [{"id": card_id} for card_id in sorted(pruned)],
    }

    if report is not None:
        status["writes"] = {
            "estimated": plan.estimated_writes,
            "actual": report.rows_written,
            "rows_read": report.rows_read,
            "statements": report.statements,
            "batches": report.batches,
            "database_bytes": report.size_after,
        }

    return status
