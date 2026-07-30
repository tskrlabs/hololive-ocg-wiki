"""Tests for unit batching and reply collection.

The batcher is what turns 14,778 API calls into ~200. What is pinned here is that it does
so without losing or mixing up units — a batch is a positional mapping, and an off-by-one
between the payload and the reply would file every translation against the wrong string.
"""

from __future__ import annotations

import json

import pytest

from holo_data.glossary import Entry, Glossary
from holo_data.translate import units as U
from holo_data.translate.batcher import (
    DEFAULT_CHAR_BUDGET,
    BatchPlan,
    build_batches,
    collect_result,
    parse_reply,
)
from holo_data.translate.mask_table import Restorer, combined_table


@pytest.fixture
def glossaries():
    names = Glossary(
        kind="names",
        entries={
            "白上フブキ": Entry(
                key="白上フブキ", translations={"en": "Shirakami Fubuki"}
            )
        },
    )
    tags = Glossary(
        kind="tags", entries={"3期生": Entry(key="3期生", translations={"en": "3rd Gen"})}
    )
    return names, tags


@pytest.fixture
def table(glossaries):
    return combined_table(*glossaries)


@pytest.fixture
def restorer(glossaries):
    return Restorer(*glossaries)


def unit(kind="art_name", value="こんこん", **context):
    return U.Unit(kind=kind, value=value, context=U.Context(**context))


class TestBatching:
    def test_groups_by_kind(self, table):
        batches = build_batches(
            [unit(kind="art_name"), unit(kind="art_effect", value="効果")],
            "en",
            table,
        )

        assert {b.kind for b in batches} == {"art_name", "art_effect"}
        assert all(len({i.unit.kind for i in b.items}) == 1 for b in batches)

    def test_splits_on_the_character_budget(self, table):
        units = [unit(value="あ" * 100) for _ in range(10)]
        # Distinct values, or they would collapse into one unit.
        units = [unit(value=f"{'あ' * 100}{i}") for i in range(10)]

        batches = build_batches(units, "en", table, char_budget=300)

        assert len(batches) > 1
        assert all(b.char_count <= 300 or b.size == 1 for b in batches)

    def test_a_single_oversized_unit_still_ships(self, table):
        """A Q&A entry can exceed the budget on its own; dropping it is not an option."""
        batches = build_batches([unit(value="あ" * 9000)], "en", table, char_budget=100)

        assert len(batches) == 1
        assert batches[0].size == 1

    def test_composition_is_deterministic(self, table):
        """A re-run after a partial failure must send the same groupings."""
        units = [unit(value=f"text{i}") for i in range(20)]

        first = build_batches(units, "en", table, char_budget=40)
        second = build_batches(list(reversed(units)), "en", table, char_budget=40)

        assert [[i.unit.key for i in b.items] for b in first] == [
            [i.unit.key for i in b.items] for b in second
        ]

    def test_units_are_masked_on_the_way_in(self, table):
        batches = build_batches([unit(value="白上フブキのこんこん")], "en", table)

        assert batches[0].items[0].masked.text == "[[N0]]のこんこん"


class TestPayload:
    def test_ids_are_positional_not_hashes(self, table):
        """A 64-char key repeated 40 times is pure token cost."""
        batch = build_batches([unit(value="あ"), unit(value="い")], "en", table)[0]

        assert set(json.loads(batch.payload())) == {"0", "1"}

    def test_prose_carries_its_context(self, table):
        batch = build_batches(
            [unit(kind="art_effect", value="効果", card_name="カード", art_name="技")],
            "en",
            table,
        )[0]

        entry = json.loads(batch.payload())["0"]
        assert entry["context"] == {"card_name": "カード", "art_name": "技"}

    def test_labels_do_not_carry_context(self, table):
        """A card name is its own context; sending it back is noise the model may echo."""
        batch = build_batches(
            [unit(kind="art_name", value="技名", card_name="カード")], "en", table
        )[0]

        assert json.loads(batch.payload())["0"] == "技名"

    def test_the_payload_carries_masked_text(self, table):
        batch = build_batches([unit(value="白上フブキ")], "en", table)[0]

        assert "白上フブキ" not in batch.payload()
        assert "[[N0]]" in batch.payload()


class TestReplyParsing:
    def test_extracts_json_from_a_fenced_reply(self):
        assert parse_reply('```json\n{"0": "x"}\n```') == {"0": "x"}

    def test_extracts_json_after_prose(self):
        assert parse_reply('Here you go:\n{"0": "x"}') == {"0": "x"}

    def test_a_reply_with_no_object_raises(self):
        with pytest.raises(ValueError, match="no JSON object"):
            parse_reply("I cannot do that")


class TestCollectResult:
    def test_maps_replies_back_by_position(self, table, restorer):
        """Position in the *batch*, not in the caller's list.

        `build_batches` sorts by content address so composition is deterministic across
        runs, which means input order is not payload order. The reply is matched against
        `batch.items`, and this pins that rather than the incidental input order.
        """
        batch = build_batches([unit(value="あ"), unit(value="い")], "en", table)[0]

        result = collect_result(batch, {"0": "first", "1": "second"}, restorer)

        expected = {
            batch.items[0].unit.key: "first",
            batch.items[1].unit.key: "second",
        }
        assert result.translations == expected

    def test_unmasks_names(self, table, restorer):
        batch = build_batches([unit(value="白上フブキのこんこん")], "en", table)[0]

        result = collect_result(batch, {"0": "[[N0]]'s Konkon"}, restorer)

        assert list(result.translations.values()) == ["Shirakami Fubuki's Konkon"]

    def test_unmasks_tags_with_their_prefix(self, table, restorer):
        """The `#` is normalised in one place, not stored in 41 glossary values."""
        batch = build_batches(
            [unit(kind="art_effect", value="#3期生を持つホロメン")], "en", table
        )[0]

        result = collect_result(batch, {"0": "holomem with [[N0]]"}, restorer)

        assert list(result.translations.values()) == ["holomem with #3rd Gen"]

    def test_a_unit_missing_from_the_reply_is_reported_not_invented(
        self, table, restorer
    ):
        batch = build_batches([unit(value="あ"), unit(value="い")], "en", table)[0]

        result = collect_result(batch, {"0": "A"}, restorer)

        assert result.ok == 1
        assert len(result.failures) == 1

    def test_a_unit_with_lost_mask_tokens_is_dropped(self, table, restorer):
        """Dropped, not stored — it stays stale and is retried, which beats caching a
        name-mangled string that would need a human to notice."""
        batch = build_batches([unit(value="白上フブキのこんこん")], "en", table)[0]

        result = collect_result(batch, {"0": "Fubuki's Konkon"}, restorer)

        assert result.ok == 0
        assert "dropped" in result.failures[0]

    def test_a_non_string_reply_for_a_string_unit_is_rejected(self, table, restorer):
        batch = build_batches([unit(value="あ")], "en", table)[0]

        result = collect_result(batch, {"0": {"unexpected": "object"}}, restorer)

        assert result.ok == 0
        assert "expected a string" in result.failures[0]

    def test_structured_units_pass_through_unmasked(self, table, restorer):
        """Q&A is a dict; there is no string to unmask."""
        qa = {"title": "Q1", "question": "q", "answer": "a"}
        batch = build_batches([unit(kind="qa", value=qa)], "en", table)[0]

        result = collect_result(batch, {"0": {"title": "Q1", "answer": "A"}}, restorer)

        assert result.ok == 1


class TestPlan:
    def test_reports_calls_units_and_characters(self, table):
        plan = BatchPlan(build_batches([unit(value=f"x{i}") for i in range(5)], "en", table))

        assert plan.call_count == 1
        assert plan.unit_count == 5

    def test_the_real_corpus_fits_in_a_few_hundred_calls(self, table):
        """The claim the whole phase rests on: 14,778 calls become ~200."""
        import json as _json
        from pathlib import Path

        path = Path("pipeline/build/cards.json")
        if not path.exists():
            pytest.skip("no build output")

        cards = _json.loads(path.read_text(encoding="utf-8"))["cards"]
        work = [u for u in U.collect(cards).values() if u.kind != "qa"]
        plan = BatchPlan(build_batches(work, "en", table, DEFAULT_CHAR_BUDGET))

        assert plan.call_count < 60, "one locale should be well under 60 calls"
        assert plan.unit_count == len(work)
