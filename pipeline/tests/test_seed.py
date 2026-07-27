"""Tests for the seeder's mapping, diff and gates.

The seeder writes to production D1, so the properties pinned here are the ones whose
regression is invisible until it has already done damage:

- a card round-trips through the generated DDL unchanged
- the diff separates a Q&A edit from a rules-text edit (v1 shipped this distinction and
  the status page renders it)
- a second run of an unchanged build writes nothing
- each hard gate refuses, and the normal path does not

Everything runs against a real SQLite database built from the *generated* schema.sql, so
these also serve as the test that the DDL generator emits something that works — a
schema that parses but cannot hold a card would otherwise pass `make check`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from holo_schema import CardCollection
from holo_data import d1, seed as seed_module

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = REPO_ROOT / "packages" / "schema" / "sql" / "schema.sql"
FIXTURES_JSON = REPO_ROOT / "fixtures" / "cards.json"
FIXTURES_SQL = REPO_ROOT / "fixtures" / "fixtures.sql"

SEEDED_AT = "2026-07-27T00:00:00Z"


@pytest.fixture(scope="module")
def collection() -> CardCollection:
    return CardCollection.model_validate_json(
        FIXTURES_JSON.read_text(encoding="utf-8")
    )


@pytest.fixture()
def db() -> sqlite3.Connection:
    """An empty database with the generated schema applied."""
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def apply(connection: sqlite3.Connection, rows) -> None:
    """Run the seeder's own statements against SQLite.

    D1 and SQLite both take `?` placeholders, which is what lets the production write
    path be exercised here without a network or a token.
    """
    for row in rows:
        for statement in seed_module.statements_for(row, SEEDED_AT):
            connection.execute(statement.sql, statement.params)
    connection.commit()


def stored_hashes(connection: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    return {
        str(r[0]): (str(r[1]), str(r[2]))
        for r in connection.execute("SELECT id, content_hash, qa_hash FROM cards")
    }


class TestSchema:
    def test_generated_ddl_executes(self, db):
        tables = {
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"cards", "card_colors", "card_tags", "card_sets", "cards_fts"} <= tables

    def test_junction_filter_uses_an_index(self, db):
        """The whole point of the junction tables (ADR 0004).

        A JSON column filtered with LIKE cannot use an index — that is what made v1
        read 882 rows per query on a 2,448-row table. If this ever degrades to a SCAN,
        the redesign has silently lost its reason to exist.
        """
        plan = db.execute(
            "EXPLAIN QUERY PLAN "
            "SELECT c.id FROM cards c "
            "JOIN card_colors cc ON cc.card_id = c.id WHERE cc.color_code = 'blue'"
        ).fetchall()
        assert "SCAN" not in plan[0][3], plan

    def test_deleting_one_cards_junction_rows_uses_an_index(self, db):
        """The seeder's write path looks junction rows up by card_id, not by value.

        Caught on the first production seed, not predicted: with only the composite
        `(value, card_id)` key, `DELETE … WHERE card_id = ?` is a skip-scan over the
        whole table — `SEARCH … (ANY(color_code) AND card_id=?)`. That cost 12,515 rows
        read per card and 15.5M for a full reseed, three times the daily read budget,
        on a command that only needed 27,203 writes.

        The read path (`WHERE color_code = ?`) and the write path (`WHERE card_id = ?`)
        want opposite key orders, so both need an index.
        """
        for table in ("card_colors", "card_tags", "card_sets"):
            plan = db.execute(
                f"EXPLAIN QUERY PLAN DELETE FROM {table} WHERE card_id = '1'"
            ).fetchall()
            detail = " ".join(row[3] for row in plan)
            assert "ANY(" not in detail, f"{table} skip-scans: {detail}"
            assert "SCAN" not in detail, f"{table} scans: {detail}"

    def test_fts_rows_are_addressed_by_rowid(self, db, collection):
        """An FTS5 column cannot be indexed for lookup — only the rowid can.

        Deleting by an UNINDEXED `card_id` column scanned the whole FTS table: 2,448
        rows read per card, ~6M for a reseed. By rowid it reads zero. Measured on
        production, not predicted.

        This test pins the consequence: the seeder must never reintroduce a `card_id`
        column here, and every statement it emits for the FTS table must key on rowid.
        """
        assert "card_id" not in SCHEMA_SQL.read_text(encoding="utf-8").split(
            "CREATE VIRTUAL TABLE"
        )[1]

        row = seed_module.to_row(collection.cards[0])
        fts_statements = [
            s
            for s in seed_module.statements_for(row, SEEDED_AT)
            if "cards_fts" in s.sql
        ]
        assert fts_statements
        for statement in fts_statements:
            assert "rowid" in statement.sql, statement.sql

    def test_a_non_numeric_card_id_fails_loudly(self):
        """The FTS rowid *is* the card id, so a non-numeric id has to be caught.

        Falling back to an UNINDEXED column would work but cost a full scan per card —
        a read-budget problem that would surface months later as mysterious growth
        rather than as an error at the point the assumption broke.
        """
        with pytest.raises(seed_module.NonNumericCardId):
            seed_module.rowid_for("hBP01-001")

    def test_every_card_id_in_the_fixture_set_is_numeric(self, collection):
        for card in collection.cards:
            assert seed_module.rowid_for(card.id) == int(card.id)

    def test_a_multi_value_filter_returns_each_card_once(self, db, collection):
        """Pins the query form Phase 4 must use (ADR 0004).

        A *join* against a junction table returns one row per matching value, so
        `colors=blue,red` would return a two-colour card twice and corrupt the
        pagination count. The `IN (SELECT …)` form returns one row per card and is
        still index-driven.
        """
        apply(db, [seed_module.to_row(card) for card in collection.cards])

        joined = db.execute(
            "SELECT count(*) FROM cards c "
            "JOIN card_colors cc ON cc.card_id = c.id "
            "WHERE cc.color_code IN ('blue', 'red')"
        ).fetchone()[0]
        scoped = db.execute(
            "SELECT count(*) FROM cards c WHERE c.id IN "
            "(SELECT card_id FROM card_colors WHERE color_code IN ('blue', 'red'))"
        ).fetchone()[0]

        assert scoped <= joined
        # And the form we recommend still resolves through the junction's primary key.
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT c.id FROM cards c WHERE c.id IN "
            "(SELECT card_id FROM card_colors WHERE color_code = 'blue')"
        ).fetchall()
        assert any("card_colors" in row[3] and "SCAN" not in row[3] for row in plan), plan

    def test_fts_matches_a_cjk_substring(self, db):
        """findings F-013 — the bug this phase fixes.

        The default unicode61 tokenizer treats an unbroken CJK run as one token, so on
        the live v1 site `白上フブキ` returns 62 cards and `フブキ` returns zero. The
        site's default locale is `tc` and its source locale is `ja`.
        """
        db.execute(
            "INSERT INTO cards_fts (rowid, card_number, text) VALUES (?, ?, ?)",
            (1, "hBP01-001", "白上フブキ"),
        )
        hits = db.execute(
            "SELECT count(*) FROM cards_fts WHERE cards_fts MATCH ?", ("フブキ",)
        ).fetchone()[0]
        assert hits == 1

    def test_trigram_cannot_match_under_three_characters(self, db):
        """Pins the limit the Phase 4 worker's LIKE fallback exists for.

        Trigram returns *no rows* rather than an error below 3 characters, which is the
        dangerous shape: a 2-character query silently looks like "no such card".
        """
        db.execute(
            "INSERT INTO cards_fts (rowid, card_number, text) VALUES (?, ?, ?)",
            (1, "hBP01-001", "宝鐘マリン"),
        )
        assert (
            db.execute(
                "SELECT count(*) FROM cards_fts WHERE cards_fts MATCH ?", ("宝鐘",)
            ).fetchone()[0]
            == 0
        )
        # ...and the fallback the worker uses instead does find it.
        assert (
            db.execute(
                "SELECT count(*) FROM cards_fts WHERE text LIKE ?", ("%宝鐘%",)
            ).fetchone()[0]
            == 1
        )


class TestRowMapping:
    def test_every_fixture_card_round_trips(self, db, collection):
        rows = [seed_module.to_row(card) for card in collection.cards]
        apply(db, rows)

        assert db.execute("SELECT count(*) FROM cards").fetchone()[0] == len(rows)

        for row in rows:
            payload, qa = db.execute(
                "SELECT payload, qa_payload FROM cards WHERE id = ?", (row.id,)
            ).fetchone()
            assert payload == row.payload
            assert qa == row.qa_payload
            # The payloads must survive as JSON, not just as bytes — the Worker parses
            # them at request time.
            json.loads(payload)
            json.loads(qa)

    def test_a_card_reassembles_from_its_row_alone(self, db, collection):
        """The Worker must rebuild a card without touching the junction tables.

        This is the property Phase 4 added `color_codes` and `card_sets` to the payload
        for. `localize()` reads both; they live in junction tables keyed for *filtering*
        (value first), so reading them back per card would mean an extra query per list
        page — the `enrichCardDataBatch` fan-out the payload design exists to delete.

        Asserted as an equality against `localize()` on the original card, so it fails
        if a future field is added to `Card` and reaches `LocalizedCard` without
        reaching the payload.
        """
        from holo_schema.enums import LOCALE_VALUES
        from holo_schema.localize import localize

        for card in collection.cards:
            row = seed_module.to_row(card)
            stored = dict(zip(seed_module.CARD_COLUMNS, row.columns))
            payload = json.loads(row.payload)

            rebuilt = {
                key: value
                for key, value in stored.items()
                if value is not None and key not in seed_module.DERIVED_COLUMNS
            }
            # The one JSON-array column; the Worker decodes it the same way.
            if rebuilt.get("baton_touch_types") is not None:
                rebuilt["baton_touch_types"] = json.loads(rebuilt["baton_touch_types"])
            rebuilt.update(payload)
            for locale, items in json.loads(row.qa_payload).items():
                rebuilt["translations"][locale]["qa_items"] = items

            from_row = CardCollection.model_validate(
                {"generated_at": SEEDED_AT, "cards": [rebuilt]}
            ).cards[0]

            for locale in LOCALE_VALUES:
                assert localize(from_row, locale) == localize(card, locale), (
                    f"card {card.id} does not survive the payload round trip in "
                    f"{locale} — a field reaches LocalizedCard but not the payload"
                )

    def test_name_ja_is_the_source_locale_name(self, db, collection):
        """The `name` filter's key.

        It is the ja name, not the requested locale's: 41% of characters have an
        inconsistent name in at least one locale, so a per-locale match splits a
        character across two filter entries (findings F-015).
        """
        from holo_schema.enums import SOURCE_LOCALE

        card = collection.cards[0]
        row = seed_module.to_row(card)
        index = seed_module.CARD_COLUMNS.index("name_ja")
        assert row.columns[index] == card.translations[SOURCE_LOCALE].name

        apply(db, [row])
        stored = db.execute(
            "SELECT name_ja FROM cards WHERE id = ?", (card.id,)
        ).fetchone()[0]
        assert stored == card.translations[SOURCE_LOCALE].name

    def test_qa_is_split_out_of_the_payload(self, db, collection):
        """Q&A is 53% of the translation bytes and the only part that churns.

        Keeping it in its own column is what stops a new FAQ entry rewriting a card's
        rules text, and what lets list endpoints avoid reading it at all.
        """
        card = next(
            c for c in collection.cards if any(t.qa_items for t in c.translations.values())
        )
        row = seed_module.to_row(card)
        assert "qa_items" not in row.payload
        assert json.loads(row.qa_payload)

    def test_integers_stay_integers(self, db, collection):
        """`hp` and `life` are INTEGER columns.

        D1's REST API binds native JSON types; passing "42" makes SQLite store text,
        which compares wrongly the first time anything sorts on it.
        """
        card = next(c for c in collection.cards if c.hp is not None)
        apply(db, [seed_module.to_row(card)])
        kind = db.execute(
            "SELECT typeof(hp) FROM cards WHERE id = ?", (card.id,)
        ).fetchone()[0]
        assert kind == "integer"

    def test_junction_rows_match_the_card(self, db, collection):
        card = next(c for c in collection.cards if c.color_codes)
        apply(db, [seed_module.to_row(card)])
        colours = {
            r[0]
            for r in db.execute(
                "SELECT color_code FROM card_colors WHERE card_id = ?", (card.id,)
            )
        }
        assert colours == set(card.color_codes)

    def test_fused_colours_are_stored_as_printed(self, db, collection):
        """A fused dual-colour symbol is one printed icon, not two colours.

        The filter-time expansion (`blue_red` matches a `blue` filter) is a query-layer
        rule; storing it expanded would render two icons and a comma where the card
        shows one.
        """
        fused = [c for c in collection.cards if c.color_codes and any(
            code in ("blue_red", "white_green") for code in c.color_codes
        )]
        assert fused, "the fixture set should carry both fused colour codes"
        apply(db, [seed_module.to_row(card) for card in fused])
        stored = {
            r[0] for r in db.execute("SELECT DISTINCT color_code FROM card_colors")
        }
        assert stored & {"blue_red", "white_green"}


class TestDiff:
    def test_an_unchanged_build_writes_nothing(self, db, collection):
        rows = [seed_module.to_row(card) for card in collection.cards]
        apply(db, rows)
        plan = seed_module.diff(rows, stored_hashes(db))
        assert plan.is_empty
        assert plan.unchanged == len(rows)
        assert plan.estimated_writes == 0

    def test_a_qa_edit_is_not_a_content_change(self, db, collection):
        """The distinction v1's status page renders, preserved."""
        rows = [seed_module.to_row(card) for card in collection.cards]
        apply(db, rows)
        baseline = stored_hashes(db)

        edited = collection.model_copy(deep=True)
        target = next(
            c for c in edited.cards if any(t.qa_items for t in c.translations.values())
        )
        locale = next(l for l, t in target.translations.items() if t.qa_items)
        target.translations[locale].qa_items[0].answer += " (edited)"

        plan = seed_module.diff(
            [seed_module.to_row(card) for card in edited.cards], baseline
        )
        assert [r.id for r in plan.qa_updated] == [target.id]
        assert not plan.changed

    def test_a_text_edit_is_a_content_change(self, db, collection):
        rows = [seed_module.to_row(card) for card in collection.cards]
        apply(db, rows)
        baseline = stored_hashes(db)

        edited = collection.model_copy(deep=True)
        target = edited.cards[0]
        target.translations["ja"].name += "★"

        plan = seed_module.diff(
            [seed_module.to_row(card) for card in edited.cards], baseline
        )
        assert [r.id for r in plan.changed] == [target.id]
        assert not plan.qa_updated

    def test_a_card_absent_from_the_build_is_reported_not_deleted(self, db, collection):
        rows = [seed_module.to_row(card) for card in collection.cards]
        apply(db, rows)
        plan = seed_module.diff(rows[1:], stored_hashes(db))
        assert plan.missing_ids == [rows[0].id]
        # Reported only — deleting is gated behind --prune, because it is the one
        # irreversible thing seed can do.
        assert rows[0].id not in {r.id for r in plan.to_write}

    def test_reseeding_after_an_interrupted_run_resumes(self, db, collection):
        """The property that makes the in-database baseline worth its 2,448 reads.

        A hash file written after the last write would leave a crashed run's cards
        looking already-seeded. Here the baseline *is* the table, so whatever landed is
        what counts as done.
        """
        rows = [seed_module.to_row(card) for card in collection.cards]
        apply(db, rows[:10])  # a run that died a third of the way in
        plan = seed_module.diff(rows, stored_hashes(db))
        assert len(plan.new) == len(rows) - 10
        assert plan.unchanged == 10


class TestEstimate:
    def test_counts_indexes_and_fts_not_just_rows(self, collection):
        """v1's estimator counted visible rows only, and was an order of magnitude out.

        An indexed column costs an extra written row per insert and FTS5 writes to its
        shadow tables; a gate that under-reports is worse than no gate, because it is
        trusted.
        """
        row = seed_module.to_row(collection.cards[0])
        junction_rows = sum(len(v) for v in row.junction_values.values())
        expected = (
            1
            + seed_module.CARD_INDEX_COUNT
            + junction_rows * seed_module.JUNCTION_WRITE_MULTIPLIER
            + seed_module.FTS_WRITE_MULTIPLIER
        )
        assert seed_module.estimate_writes([row]) == expected

    def test_a_full_reseed_fits_inside_the_daily_budget(self, collection):
        rows = [seed_module.to_row(card) for card in collection.cards]
        per_card = seed_module.estimate_writes(rows) / len(rows)
        assert per_card * 2448 < d1.DAILY_WRITE_LIMIT


class TestGates:
    def _plan(self, collection):
        rows = [seed_module.to_row(card) for card in collection.cards]
        return seed_module.diff(rows, {}), rows

    def test_a_normal_run_is_not_refused(self, collection):
        plan, _ = self._plan(collection)
        assert seed_module.check_gates(plan, collection, 1, 0, prune=False) == []

    def test_a_collapsed_card_set_is_refused(self, collection):
        """The empty-or-partial-scrape signature.

        Not covered by --prune: a collapse this large means the *build* is wrong, so
        even writing the survivors would publish a broken dataset.
        """
        rows = [seed_module.to_row(card) for card in collection.cards]
        stored = {row.id: (row.content_hash, row.qa_hash) for row in rows}
        plan = seed_module.diff(rows[:5], stored)
        refusals = seed_module.check_gates(plan, collection, 1, 0, prune=False)
        assert any("smaller" in r.reason for r in refusals)

    def test_an_exhausted_write_budget_is_refused(self, collection):
        plan, _ = self._plan(collection)
        refusals = seed_module.check_gates(
            plan, collection, 1, d1.DAILY_WRITE_LIMIT - 1, prune=False
        )
        assert any("budget" in r.reason for r in refusals)

    def test_a_schema_version_mismatch_is_refused(self, collection):
        plan, _ = self._plan(collection)
        refusals = seed_module.check_gates(plan, collection, 999, 0, prune=False)
        assert any("schema version" in r.reason for r in refusals)

    def test_unreadable_analytics_does_not_block_a_small_run(self, collection):
        """A missing analytics permission should not stop a legitimate seed.

        `writes_used=None` means we could not read today's usage; the run is allowed but
        the CLI says so. Only an estimate above the whole daily limit is refused.
        """
        plan, _ = self._plan(collection)
        assert seed_module.check_gates(plan, collection, 1, None, prune=False) == []


class TestFixturesSql:
    def test_it_loads_and_is_idempotent(self, db):
        """D12: a fresh clone must run with zero Cloudflare credentials."""
        script = FIXTURES_SQL.read_text(encoding="utf-8")
        db.executescript(script)
        first = db.execute("SELECT count(*) FROM cards").fetchone()[0]
        db.executescript(script)
        assert db.execute("SELECT count(*) FROM cards").fetchone()[0] == first
        assert first > 0

    def test_sql_escaping_round_trips(self, db, collection):
        """The fixture text carries the official site's raw HTML and 7 languages.

        `fixtures.sql` uses literals rather than bound parameters because it is a file,
        so this is the only thing standing between a stray apostrophe and a corrupt
        local dataset.
        """
        db.executescript(FIXTURES_SQL.read_text(encoding="utf-8"))
        for card in collection.cards:
            row = seed_module.to_row(card)
            payload, qa = db.execute(
                "SELECT payload, qa_payload FROM cards WHERE id = ?", (card.id,)
            ).fetchone()
            assert payload == row.payload
            assert qa == row.qa_payload


class TestBatching:
    def test_a_card_is_never_split_across_batches(self, collection):
        """D1 batches are atomic, so a whole group in one batch means a card is either
        fully written or not written at all."""
        groups = [
            seed_module.statements_for(seed_module.to_row(card), SEEDED_AT)
            for card in collection.cards
        ]
        batches = d1.pack_groups(groups, size=10)
        flat = [statement for batch in batches for statement in batch]
        assert len(flat) == sum(len(g) for g in groups)

        # Every card's statements land contiguously inside exactly one batch.
        for group in groups:
            assert any(
                all(statement in batch for statement in group) for batch in batches
            )

    def test_params_are_bound_never_interpolated(self, collection):
        """The reason the seeder does not generate SQL text (ADR 0004).

        Card data carries the official site's raw HTML; hand-escaping it at each call
        site is where a quoting bug becomes silent data corruption.
        """
        row = seed_module.to_row(collection.cards[0])
        for statement in seed_module.statements_for(row, SEEDED_AT):
            assert "'" not in statement.sql or statement.sql.count("'") % 2 == 0
            payload = statement.as_payload()
            assert payload["params"] == list(statement.params)
