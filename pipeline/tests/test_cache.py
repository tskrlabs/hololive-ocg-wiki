"""Tests for the field-level translation cache.

The behaviours pinned here are the ones that cost money or lose work when wrong:
Q&A churn must not invalidate card text, and a manual correction must survive.
"""

from __future__ import annotations

import pytest

from holo_data.translate.cache import TranslationCache, field_keys, hash_value


def jp_card(**overrides):
    base = {
        "name": "IRyS",
        "tags": ["EN", "Promise"],
        "arts": [{"name": "ハイRyS！", "effect": "効果テキスト"}],
        "oshi_skill": {"name": "スキル", "effect": "効果", "timing": "ターンに1回"},
        "qa_items": [
            {"title": "Q1", "question": "質問1", "answer": "回答1"},
            {"title": "Q2", "question": "質問2", "answer": "回答2"},
        ],
    }
    base.update(overrides)
    return base


class TestFieldKeys:
    def test_addresses_every_translatable_unit(self):
        keys = {key for key, _ in field_keys(jp_card())}
        assert keys == {
            "name",
            "tags",
            "arts[0].name",
            "arts[0].effect",
            "oshi_skill.name",
            "oshi_skill.effect",
            "oshi_skill.timing",
            "qa_items[0]",
            "qa_items[1]",
        }

    def test_skips_absent_and_empty(self):
        keys = {key for key, _ in field_keys({"name": "X", "extra": "", "arts": []})}
        assert keys == {"name"}

    def test_qa_hashes_as_a_unit(self):
        """Title/question/answer translate together — splitting risks desync."""
        pairs = dict(field_keys(jp_card()))
        assert pairs["qa_items[0]"] == {
            "title": "Q1",
            "question": "質問1",
            "answer": "回答1",
        }


class TestStaleness:
    def test_everything_stale_when_empty(self):
        cache = TranslationCache()
        stale = cache.stale_fields("en", "2314", jp_card())
        assert len(stale) == 9

    def test_nothing_stale_once_populated(self):
        cache = TranslationCache()
        card = jp_card()
        for key, value in field_keys(card):
            cache.put("en", "2314", key, value, f"translated:{key}")
        assert cache.stale_fields("en", "2314", card) == []

    def test_qa_change_does_not_invalidate_card_text(self):
        """The central claim: Q&A churns, card text does not, so they must be independent.

        Measured on real data — 37-39 cards had Q&A changes between snapshots while
        `name` changed on 2 and everything else on 0-1.
        """
        cache = TranslationCache()
        card = jp_card()
        for key, value in field_keys(card):
            cache.put("en", "2314", key, value, f"translated:{key}")

        # The official site edits one Q&A answer.
        updated = jp_card()
        updated["qa_items"][1]["answer"] = "回答2（修正）"

        assert cache.stale_fields("en", "2314", updated) == ["qa_items[1]"]

    def test_added_qa_does_not_disturb_existing(self):
        cache = TranslationCache()
        card = jp_card()
        for key, value in field_keys(card):
            cache.put("en", "2314", key, value, f"translated:{key}")

        updated = jp_card()
        updated["qa_items"].append({"title": "Q3", "question": "質問3", "answer": "回答3"})

        assert cache.stale_fields("en", "2314", updated) == ["qa_items[2]"]

    def test_source_change_invalidates_only_that_field(self):
        cache = TranslationCache()
        card = jp_card()
        for key, value in field_keys(card):
            cache.put("en", "2314", key, value, f"translated:{key}")

        updated = jp_card()
        updated["arts"][0]["effect"] = "新しい効果"

        assert cache.stale_fields("en", "2314", updated) == ["arts[0].effect"]

    def test_locales_are_independent(self):
        cache = TranslationCache()
        card = jp_card()
        for key, value in field_keys(card):
            cache.put("en", "2314", key, value, "x")
        assert cache.stale_fields("en", "2314", card) == []
        assert len(cache.stale_fields("tc", "2314", card)) == 9


class TestManualCorrections:
    def test_manual_entry_is_not_stale(self):
        """A human fix stands as long as the JP source has not moved.

        This is what supersedes D14's corrections overlay — there is no merge step,
        because a fresh field is simply never re-translated.
        """
        cache = TranslationCache()
        card = jp_card()
        cache.put("en", "2314", "name", card["name"], "IRyS (fixed)", source="manual")

        assert cache.stale_fields("en", "2314", card) == [
            key for key, _ in field_keys(card) if key != "name"
        ]
        entry = cache.get("en", "2314", "name")
        assert entry.value == "IRyS (fixed)"
        assert entry.source == "manual"

    def test_manual_entry_goes_stale_when_source_changes(self):
        """If the JP text is rewritten, the old correction no longer applies."""
        cache = TranslationCache()
        cache.put("en", "2314", "name", "IRyS", "IRyS (fixed)", source="manual")
        assert "name" in cache.stale_fields("en", "2314", {"name": "IRyS v2"})

    def test_manual_count(self):
        cache = TranslationCache()
        cache.put("en", "1", "name", "a", "A", source="manual")
        cache.put("en", "2", "name", "b", "B")
        cache.put("tc", "1", "name", "a", "A", source="manual")
        assert cache.manual_count("en") == 1
        assert cache.manual_count() == 2


class TestPrune:
    def test_removes_deleted_cards(self):
        cache = TranslationCache()
        cache.put("en", "gone", "name", "x", "X")
        cache.put("en", "2314", "name", "IRyS", "IRyS")
        removed = cache.prune("en", {"2314": {"name": "IRyS"}})
        assert removed == 1
        assert cache.get("en", "gone", "name") is None
        assert cache.get("en", "2314", "name") is not None

    def test_removes_deleted_fields(self):
        cache = TranslationCache()
        cache.put("en", "2314", "name", "IRyS", "IRyS")
        cache.put("en", "2314", "qa_items[5]", {"a": 1}, "gone")
        removed = cache.prune("en", {"2314": {"name": "IRyS"}})
        assert removed == 1
        assert cache.get("en", "2314", "qa_items[5]") is None


class TestPersistence:
    def test_round_trip(self, tmp_path):
        cache = TranslationCache()
        cache.put("en", "2314", "name", "IRyS", "IRyS")
        cache.put("en", "2314", "extra", "テキスト", "Text", source="manual")
        path = tmp_path / "cache.json"
        cache.save(path)

        loaded = TranslationCache.load(path)
        assert loaded.get("en", "2314", "name").value == "IRyS"
        assert loaded.get("en", "2314", "extra").source == "manual"
        assert loaded.stale_fields("en", "2314", {"name": "IRyS", "extra": "テキスト"}) == []

    def test_missing_file_is_empty(self, tmp_path):
        assert TranslationCache.load(tmp_path / "nope.json").entries == {}

    def test_version_mismatch_refuses(self, tmp_path):
        path = tmp_path / "cache.json"
        path.write_text('{"version": 99, "locales": {}}', encoding="utf-8")
        with pytest.raises(ValueError, match="version 99"):
            TranslationCache.load(path)


class TestHashing:
    def test_key_order_does_not_change_hash(self):
        assert hash_value({"a": 1, "b": 2}) == hash_value({"b": 2, "a": 1})

    def test_value_change_changes_hash(self):
        assert hash_value("a") != hash_value("b")
