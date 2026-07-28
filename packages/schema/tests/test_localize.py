"""Tests for the `Card` -> `LocalizedCard` projection.

The merge rules here are the spec that `src/localize.ts` must reproduce. Each test
names the real card that forced the rule.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from holo_schema import LOCALE_VALUES, CardCollection, localize

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PACKAGE_ROOT.parent.parent / "fixtures" / "cards.json"
GOLDEN_DIR = PACKAGE_ROOT / "golden"


@pytest.fixture(scope="module")
def collection() -> CardCollection:
    return CardCollection.model_validate_json(FIXTURES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(collection: CardCollection) -> dict:
    return {card.id: card for card in collection.cards}


class TestGoldenFiles:
    """The golden files must match what localize() produces right now.

    If this fails, either localize() changed (regenerate with `make golden` and review
    the diff) or something upstream broke.
    """

    @pytest.mark.parametrize("locale", LOCALE_VALUES)
    def test_golden_matches(self, collection: CardCollection, locale: str):
        path = GOLDEN_DIR / f"localized-{locale}.json"
        assert path.exists(), f"missing golden file — run `make golden`"

        expected = json.loads(path.read_text(encoding="utf-8"))
        actual = [
            localize(card, locale).model_dump(mode="json", exclude_none=True)
            for card in collection.cards
        ]
        # Round-trip through JSON so key ordering matches the file's sort_keys=True.
        actual = json.loads(json.dumps(actual, sort_keys=True))
        expected = json.loads(json.dumps(expected, sort_keys=True))
        assert actual == expected


class TestArtsMerge:
    """Arts pair by index between Card.arts and Translation.arts."""

    def test_short_translation_list_tolerated(self, by_id: dict):
        """hSD03-009 has 2 arts but 0 `en` translated arts.

        The arts must still be returned — with costs and damage, without a name —
        because dropping them would misreport what the card does.
        """
        card = by_id["446"]
        assert len(card.arts or []) == 2
        assert len(card.translations["en"].arts or []) == 0

        result = localize(card, "en")
        assert len(result.arts) == 2
        assert result.arts[0].cost_types == card.arts[0].cost_types
        assert result.arts[0].name is None

    def test_translated_arts_merge_by_position(self, by_id: dict):
        card = by_id["446"]
        result = localize(card, "ja")
        translated = card.translations["ja"].arts or []
        assert len(result.arts) == len(card.arts or [])
        for index, art in enumerate(result.arts):
            assert art.name == translated[index].name
            assert art.cost_types == card.arts[index].cost_types


class TestLocaleFallback:
    def test_missing_locale_falls_back_to_source(self, by_id: dict):
        card = by_id["446"].model_copy(deep=True)
        del card.translations["en"]
        result = localize(card, "en")
        assert result.locale == "ja"
        assert result.name == card.translations["ja"].name

    def test_resolved_locale_reported(self, by_id: dict):
        """The response says which language it is in, so a cached response is unambiguous."""
        card = by_id["446"]
        assert localize(card, "tc").locale == "tc"


class TestFlattening:
    def test_translation_fields_hoisted(self, by_id: dict):
        card = by_id["446"]
        result = localize(card, "ja")
        assert result.name == card.translations["ja"].name

    def test_absent_lists_become_empty(self, by_id: dict):
        """The API does not distinguish "no tags" from "empty tags"."""
        card = next(c for c in by_id.values() if not c.tags)
        result = localize(card, "ja")
        assert result.tags == [] or isinstance(result.tags, list)
        assert isinstance(result.arts, list)
        assert isinstance(result.qa_items, list)

    def test_no_cost_on_oshi_skill(self, by_id: dict):
        """v1 declared oshi_skill.cost in three places; no card ever had it."""
        card = next(c for c in by_id.values() if c.oshi_skill is not None)
        result = localize(card, "ja")
        assert not hasattr(result.oshi_skill, "cost")

    def test_fused_color_preserved(self, by_id: dict):
        """`blue_red` must survive the projection intact — it renders as one icon."""
        card = by_id["2263"]
        assert card.color_codes == ["blue_red"]
        assert localize(card, "ja").color_codes == ["blue_red"]

    def test_multi_color_preserved(self, by_id: dict):
        card = by_id["1218"]
        assert localize(card, "ja").color_codes == ["red", "blue"]


class TestAllFixturesProject:
    """Every fixture card must project into every locale without raising."""

    def test_every_card_every_locale(self, collection: CardCollection):
        for card in collection.cards:
            for locale in LOCALE_VALUES:
                result = localize(card, locale)
                assert result.id == card.id
                assert result.image_key == card.image_key
