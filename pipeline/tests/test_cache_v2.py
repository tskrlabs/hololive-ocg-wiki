"""Tests for the content-addressed cache and the Q&A migration.

Two properties carry the whole rework:

**One source string has one slot.** That is what makes #20 and #21 unrepresentable rather
than merely corrected — a cache that can hold two answers for one string is the old cache
with extra steps.

**A manual entry is never overwritten.** ADR 0002's guarantee, preserved. A human decided
it, the source has not moved, so it stands regardless of what any model returns.
"""

from __future__ import annotations

import json

import pytest

from holo_data.translate import migrate as M
from holo_data.translate import units as U
from holo_data.translate.cache import CACHE_VERSION as V1_VERSION
from holo_data.translate.cache import TranslationCache
from holo_data.translate.cache_v2 import TranslationCacheV2, resolve


def unit(kind="art_name", value="こんこん", occurrences=1):
    return U.Unit(kind=kind, value=value, occurrences=occurrences)


class TestOneSlotPerString:
    def test_the_same_string_from_two_cards_shares_one_entry(self):
        """The defect this rework removes: five cards, five translations, five answers."""
        cache = TranslationCacheV2()
        first = unit(value="こんこん")
        second = unit(value="こんこん")  # a different Unit object, same content

        cache.put("en", first, "Konkon")

        assert cache.value_for("en", second) == "Konkon"

    def test_writing_twice_replaces_rather_than_accumulating(self):
        cache = TranslationCacheV2()
        cache.put("en", unit(), "First")
        cache.put("en", unit(), "Second")

        assert cache.count("en") == 1
        assert cache.value_for("en", unit()) == "Second"

    def test_a_changed_source_is_a_different_slot(self):
        cache = TranslationCacheV2()
        cache.put("en", unit(value="こんこん"), "Konkon")

        assert cache.value_for("en", unit(value="こんこんきーつね")) is None

    def test_locales_are_independent(self):
        cache = TranslationCacheV2()
        cache.put("en", unit(), "Konkon")

        assert cache.value_for("tc", unit()) is None


class TestStaleness:
    def test_an_untranslated_unit_is_stale(self):
        assert TranslationCacheV2().stale("en", [unit()]) == [unit()]

    def test_a_translated_unit_is_not(self):
        cache = TranslationCacheV2()
        cache.put("en", unit(), "Konkon")

        assert cache.stale("en", [unit()]) == []

    def test_a_manual_entry_is_never_stale_while_the_source_holds(self):
        """ADR 0002's guarantee. A human decided it; the model does not get a vote."""
        cache = TranslationCacheV2()
        cache.put("en", unit(), "Hand-written", source="manual")

        assert cache.stale("en", [unit()]) == []
        assert cache.value_for("en", unit()) == "Hand-written"

    def test_an_entry_whose_hash_was_tampered_with_is_stale(self):
        """The hash is stored as well as embedded in the key, so a hand-edited cache
        fails loudly rather than serving a translation of different text."""
        cache = TranslationCacheV2()
        cache.put("en", unit(), "Konkon")
        cache.entries["en"][unit().key].source_hash = "0" * 64

        assert cache.stale("en", [unit()]) == [unit()]


class TestPruning:
    def test_drops_units_the_build_no_longer_contains(self):
        cache = TranslationCacheV2()
        cache.put("en", unit(value="残る"), "Stays")
        cache.put("en", unit(value="消える"), "Goes")

        removed = cache.prune("en", [unit(value="残る")])

        assert removed == 1
        assert cache.count("en") == 1

    def test_a_string_still_printed_by_any_card_survives(self):
        """Content addressing sharpens this: dead means *no card anywhere* prints it."""
        cache = TranslationCacheV2()
        cache.put("en", unit(), "Konkon")

        assert cache.prune("en", [unit()]) == 0


class TestPersistence:
    def test_round_trips(self, tmp_path):
        path = tmp_path / "v2.json"
        cache = TranslationCacheV2()
        cache.put("en", unit(), "Konkon")
        cache.put("tc", unit(), "手動", source="manual")
        cache.put("en", unit(kind="qa", value={"title": "Q"}), {"title": "Q"}, source="legacy")
        cache.save(path)

        loaded = TranslationCacheV2.load(path)

        assert loaded.value_for("en", unit()) == "Konkon"
        assert loaded.count(source="manual") == 1
        assert loaded.count(source="legacy") == 1

    def test_a_missing_file_is_an_empty_cache(self, tmp_path):
        assert TranslationCacheV2.load(tmp_path / "absent.json").entries == {}

    def test_a_v1_file_is_refused_rather_than_misread(self, tmp_path):
        """Reading a v1 cache as v2 would treat card ids as content addresses."""
        path = tmp_path / "v1.json"
        path.write_text(json.dumps({"version": V1_VERSION, "locales": {}}))

        with pytest.raises(ValueError, match="version"):
            TranslationCacheV2.load(path)

    def test_written_sorted(self, tmp_path):
        """`publish` content-diffs the artifact; unstable ordering re-uploads it."""
        path = tmp_path / "v2.json"
        cache = TranslationCacheV2()
        for value in ("う", "あ", "い"):
            cache.put("en", unit(value=value), value)
        cache.save(path)

        keys = list(json.loads(path.read_text(encoding="utf-8"))["locales"]["en"])
        assert keys == sorted(keys)


class TestMigrationStatus:
    def test_reports_progress_per_locale(self):
        cache = TranslationCacheV2()
        units = [unit(value="あ"), unit(value="い"), unit(value="う")]
        cache.put("en", units[0], "A")
        cache.put("en", units[1], "B", source="legacy")

        status = cache.status("en", units)

        assert (status.total, status.fresh, status.missing) == (3, 2, 1)
        assert status.legacy == 1
        assert not status.is_complete

    def test_a_fully_translated_locale_is_complete(self):
        cache = TranslationCacheV2()
        cache.put("en", unit(), "Konkon")

        assert cache.status("en", [unit()]).is_complete


class TestDualRead:
    """A locale ships when it is ready, rather than all six landing together."""

    def test_v2_wins_when_it_has_the_unit(self):
        v1 = TranslationCache()
        v1.put("en", "1", "arts[0].name", "こんこん", "Old")
        v2 = TranslationCacheV2()
        v2.put("en", unit(), "New")

        assert resolve(v2, v1, "en", unit(), "1", "arts[0].name") == "New"

    def test_v1_answers_when_v2_has_not_been_filled(self):
        v1 = TranslationCache()
        v1.put("en", "1", "arts[0].name", "こんこん", "Old")

        assert resolve(TranslationCacheV2(), v1, "en", unit(), "1", "arts[0].name") == (
            "Old"
        )

    def test_a_stale_v1_entry_does_not_answer(self):
        """The source moved since v1 cached it, so its value describes different text."""
        v1 = TranslationCache()
        v1.put("en", "1", "arts[0].name", "古い原文", "Old")

        assert resolve(TranslationCacheV2(), v1, "en", unit(), "1", "arts[0].name") is None

    def test_no_fallback_configured_returns_nothing(self):
        assert resolve(TranslationCacheV2(), None, "en", unit(), "1", "x") is None


class TestQaMigration:
    def _fixture(self):
        qa = {"title": "Q1", "question": "質問", "answer": "回答"}
        cards = [
            {"id": "1", "translations": {"ja": {"name": "A", "qa_items": [qa]}}},
            {"id": "2", "translations": {"ja": {"name": "B", "qa_items": [qa]}}},
        ]
        return qa, cards, U.collect(cards)

    @staticmethod
    def _qa_unit(units):
        """The Q&A unit specifically — `next(iter(...))` picks up a card_name."""
        return next(u for u in units.values() if u.kind == "qa")

    def test_migrates_a_unit_and_marks_it_legacy(self):
        """`legacy` is a third provenance so a later pass can find exactly these."""
        qa, cards, units = self._fixture()
        v1 = TranslationCache()
        v1.put("en", "1", "qa_items[0]", qa, {"title": "Q1", "answer": "Answer"})
        v2 = TranslationCacheV2()

        report = M.migrate_qa(v1, v2, units, cards, ["en"])

        assert report.migrated["en"] == 1
        assert v2.count(source="legacy") == 1

    def test_a_conflict_is_resolved_and_counted(self):
        """Two cards, two different translations of one Q&A — 528 of 596 in `en`."""
        qa, cards, units = self._fixture()
        v1 = TranslationCache()
        v1.put("en", "1", "qa_items[0]", qa, {"answer": "First"})
        v1.put("en", "2", "qa_items[0]", qa, {"answer": "Second"})
        v2 = TranslationCacheV2()

        report = M.migrate_qa(v1, v2, units, cards, ["en"])

        assert report.conflicted["en"] == 1
        assert report.migrated["en"] == 1  # still exactly one slot

    def test_the_winner_is_deterministic(self):
        """A winner that varied per run would re-upload the artifact every build."""
        qa, cards, units = self._fixture()
        v1 = TranslationCache()
        v1.put("en", "1", "qa_items[0]", qa, {"answer": "First"})
        v1.put("en", "2", "qa_items[0]", qa, {"answer": "Second"})

        results = []
        for _ in range(3):
            v2 = TranslationCacheV2()
            M.migrate_qa(v1, v2, units, cards, ["en"])
            results.append(v2.value_for("en", self._qa_unit(units)))

        assert len(set(json.dumps(r, sort_keys=True) for r in results)) == 1

    def test_an_untranslated_passthrough_loses_to_a_real_translation(self):
        qa, cards, units = self._fixture()
        v1 = TranslationCache()
        v1.put("en", "1", "qa_items[0]", qa, qa)  # never translated
        v1.put("en", "2", "qa_items[0]", qa, {"answer": "Real"})
        v2 = TranslationCacheV2()

        M.migrate_qa(v1, v2, units, cards, ["en"])

        assert v2.value_for("en", self._qa_unit(units)) == {"answer": "Real"}

    def test_units_with_no_v1_entry_are_counted_not_invented(self):
        qa, cards, units = self._fixture()
        v2 = TranslationCacheV2()

        report = M.migrate_qa(TranslationCache(), v2, units, cards, ["en"])

        assert report.unmatched["en"] == 1
        assert v2.count() == 0

    def test_only_qa_is_migrated(self):
        """Everything else conflicts at 28-83% and is re-translated cold."""
        qa, cards, units = self._fixture()
        v1 = TranslationCache()
        v1.put("en", "1", "name", "A", "Card A")
        v1.put("en", "1", "qa_items[0]", qa, {"answer": "Answer"})
        v2 = TranslationCacheV2()

        M.migrate_qa(v1, v2, units, cards, ["en"])

        kinds = {key.split(":")[0] for key in v2.entries["en"]}
        assert kinds == {"qa"}
