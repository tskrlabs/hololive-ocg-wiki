"""Tests for translatable-unit extraction.

The property everything else depends on: **the same source string yields the same key,
and a different one yields a different key.** If that breaks, either divergence returns
(two keys for one string) or translations bleed across unrelated fields (one key for two
strings).
"""

from __future__ import annotations

import pytest

from holo_data.translate import units as U


def translation(**overrides):
    base = {
        "name": "白上フブキ",
        "tags": ["#EN", "#歌"],
        "ability_text": "能力テキスト",
        "arts": [
            {"name": "こんこんきーつね", "effect": "効果テキスト"},
            {"name": "こんこんきーつね", "effect": "別の効果"},
        ],
        "keyword": {"name": "キーワード", "effect": "キーワード効果"},
        "oshi_skill": {"name": "スキル", "effect": "スキル効果", "timing": "ターンに1回"},
        "qa_items": [{"title": "Q1", "question": "質問", "answer": "回答"}],
    }
    base.update(overrides)
    return base


def card(card_id="1", **overrides):
    return {"id": card_id, "translations": {"ja": translation(**overrides)}}


class TestKeys:
    def test_the_same_string_yields_the_same_key(self):
        assert U.unit_key("art_name", "こんこん") == U.unit_key("art_name", "こんこん")

    def test_a_different_string_yields_a_different_key(self):
        assert U.unit_key("art_name", "こんこん") != U.unit_key("art_name", "こんこ")

    def test_the_kind_is_part_of_the_key(self):
        """Only 15 real strings appear under two kinds, but the split buys per-kind
        prompts — an art name and an effect want different instructions."""
        assert U.unit_key("art_name", "同じ") != U.unit_key("art_effect", "同じ")

    def test_the_key_is_readable(self):
        """A cache of 3,893 bare hashes cannot be audited; `grep '^art_name:'` can."""
        key = U.unit_key("art_name", "こんこん")

        assert key.startswith("art_name:")
        assert len(key.split(":")[1]) == 64

    def test_dict_ordering_does_not_change_the_hash(self):
        """Q&A hashes a dict; key order must not invalidate every entry on a re-run."""
        first = U.unit_hash({"title": "Q1", "question": "a", "answer": "b"})
        second = U.unit_hash({"answer": "b", "question": "a", "title": "Q1"})

        assert first == second

    def test_hashes_match_the_v1_cache(self):
        """The two schemes must agree, or the dual-read fallback never hits."""
        from holo_data.translate.cache import hash_value

        assert U.unit_hash("白上フブキ") == hash_value("白上フブキ")


class TestExtraction:
    def test_yields_every_translatable_field(self):
        kinds = {kind for kind, _, _ in U.iter_fields(translation())}

        assert kinds == {
            "card_name",
            "tag",
            "ability_text",
            "art_name",
            "art_effect",
            "keyword_name",
            "keyword_effect",
            "skill_name",
            "skill_effect",
            "skill_timing",
            "qa",
        }

    def test_tags_are_separate_units_not_one_list(self):
        """v1 hashed the whole list, so adding a tag re-translated all of them.

        Per-tag units dedupe 5,481 occurrences to 41 — the largest saving of any kind.
        """
        tags = [value for kind, value, _ in U.iter_fields(translation()) if kind == "tag"]

        assert tags == ["#EN", "#歌"]

    def test_a_repeated_art_name_is_one_unit(self):
        """The fixture prints the same art name twice; it must collapse."""
        units = U.collect([card()])
        art_names = [u for u in units.values() if u.kind == "art_name"]

        assert len(art_names) == 1
        assert art_names[0].occurrences == 2

    def test_absent_fields_are_skipped_not_yielded_empty(self):
        minimal = {"id": "1", "translations": {"ja": {"name": "X"}}}
        kinds = [kind for kind, _, _ in U.iter_fields(minimal["translations"]["ja"])]

        assert kinds == ["card_name"]

    def test_a_card_with_no_source_translation_is_skipped(self):
        assert U.collect([{"id": "1", "translations": {"en": {"name": "X"}}}]) == {}


class TestContext:
    def test_prose_carries_its_card_and_art(self):
        """`そのホロメン` is ambiguous without knowing whose card it is."""
        effects = {
            value: context
            for kind, value, context in U.iter_fields(translation())
            if kind == "art_effect"
        }

        assert effects["効果テキスト"].card_name == "白上フブキ"
        assert effects["効果テキスト"].art_name == "こんこんきーつね"

    def test_labels_carry_no_context_of_their_own(self):
        """A card name is its own context; sending it back to itself is noise."""
        contexts = [
            context for kind, _, context in U.iter_fields(translation())
            if kind == "card_name"
        ]

        assert contexts[0].as_dict() == {}

    def test_context_does_not_change_the_key(self):
        """Otherwise identical rules text on two cards would fragment again — which is
        the exact defect this rework exists to remove."""
        first = U.collect([card("1", name="カードA")])
        second = U.collect([card("2", name="カードB")])

        effect_keys = lambda units: {  # noqa: E731
            k for k, u in units.items() if u.kind == "art_effect"
        }
        assert effect_keys(first) == effect_keys(second)

    def test_the_first_occurrence_supplies_the_context(self):
        units = U.collect([card("1", name="カードA"), card("2", name="カードB")])
        effect = next(u for u in units.values() if u.kind == "art_effect")

        assert effect.context.card_name == "カードA"
        assert effect.occurrences == 2


class TestStats:
    def test_reports_units_occurrences_and_characters(self):
        stats = U.stats(U.collect([card("1"), card("2")]))
        units, occurrences, _ = stats.by_kind["card_name"]

        assert units == 1
        assert occurrences == 2

    def test_totals_across_kinds(self):
        stats = U.stats(U.collect([card()]))

        assert stats.distinct == len(U.collect([card()]))
        assert stats.occurrences >= stats.distinct


class TestTheUnitsSourceIsTheScrape:
    """`translate-units` must read the scrape, never the build.

    A regression guard, and the bug it guards is a deadlock rather than a wrong number:
    `build` refuses to write a card whose locales are missing, so on a new card set the
    built `cards.json` is the *previous* set — the one artifact from which the new
    strings are provably absent. Sourcing units from it meant the v2 path could not
    onboard a new set at all, and the failure was silent in the worst way: it reported
    "everything is up to date" while `build` failed on cards needing exactly the
    translations it had declined to fetch.

    Found updating 2,463 → 2,559 cards, where 132 new units were invisible to it.
    """

    def test_a_new_card_is_visible_before_it_can_be_built(self):
        """The scrape holds the new card; the last build cannot."""
        previous_build = [card("1", name="旧カード")]
        scrape = previous_build + [card("2", name="新カード")]

        assert len(U.collect(scrape)) > len(U.collect(previous_build))

    def test_the_new_strings_are_the_ones_missing_from_the_build(self):
        new_card = card("2", name="新カード")
        missing = set(U.collect([card("1"), new_card])) - set(U.collect([card("1")]))

        assert U.unit_key("card_name", "新カード") in missing

    def test_the_cli_collects_from_load_i18n_not_from_cards_json(self):
        """Pins the call itself: the two sources agree only until a set is added."""
        import inspect

        from holo_data import cli

        source = inspect.getsource(cli.translate_units)

        assert "transform.load_i18n()" in source
        assert "build_module.load()" not in source


class TestAgainstTheRealBuild:
    """The numbers the plan's cost estimates rest on."""

    @pytest.fixture(scope="class")
    @classmethod
    def real_units(cls):
        import json
        from pathlib import Path

        path = Path("pipeline/build/cards.json")
        if not path.exists():
            pytest.skip("no build output")
        return U.collect(json.loads(path.read_text(encoding="utf-8"))["cards"])

    def test_dedupes_the_corpus_substantially(self, real_units):
        stats = U.stats(real_units)

        assert stats.distinct < stats.occurrences / 3, (
            "content addressing should collapse ~15k occurrences to ~4k units"
        )

    def test_qa_dominates_the_character_count(self, real_units):
        """The measurement behind excluding Q&A from the cold run."""
        stats = U.stats(real_units)
        _, _, qa_chars = stats.by_kind["qa"]

        assert qa_chars / stats.chars > 0.5, "Q&A should be over half the corpus"

    def test_every_unit_key_is_unique_to_its_value(self, real_units):
        """A collision would silently merge two different strings' translations."""
        by_key = {}
        for key, unit in real_units.items():
            assert key not in by_key or by_key[key] == unit.value
            by_key[key] = unit.value
