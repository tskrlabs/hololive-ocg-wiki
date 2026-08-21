"""Tests for the `Card` -> `LocalizedCard` projection.

The merge rules here are the spec that `src/localize.ts` must reproduce. Each test
names the real card that forced the rule.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from holo_schema import LOCALE_VALUES, Card, CardCollection, localize

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
        """The synthetic fixture has 2 arts but 0 `en` translated arts.

        The arts must still be returned — with costs and damage, without a name —
        because dropping them would misreport what the card does.

        This used to key on card 446 (hSD03-009), the card that forced the rule. The
        field-level translation cache has since filled it in (F-004), and a census over
        the whole card set finds **zero** cards with an arts-length mismatch in any
        locale — so the branch has no natural cover left in the data at all, and a
        synthetic fixture is the only way to keep it tested. See SYNTHETIC_CARD in
        `scripts/build_fixtures.py` and issue #16.
        """
        card = by_id["9000001"]
        assert len(card.arts or []) == 2
        assert len(card.translations["en"].arts or []) == 0

        result = localize(card, "en")
        assert len(result.arts) == 2
        assert result.arts[0].cost_types == card.arts[0].cost_types
        assert result.arts[0].name is None

    def test_partial_translation_list_pairs_by_index(self, by_id: dict):
        """A list shorter than `arts` but not empty: `tc` has 1 translation for 2 arts.

        The unpaired art keeps its costs and loses only its name — the same rule as an
        empty list, exercised at the boundary between the two.
        """
        card = by_id["9000001"]
        assert len(card.translations["tc"].arts or []) == 1

        result = localize(card, "tc")
        assert len(result.arts) == 2
        assert result.arts[0].name == "技能一"
        assert result.arts[1].name is None
        assert result.arts[1].cost_types == card.arts[1].cost_types

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

    def test_a_dual_colour_pair_survives_the_projection(self, by_id: dict):
        """Both codes and their printed order, or the card renders the wrong badges.

        `青赤` normalises to a pair at extraction (ADR 0013), so what reaches `localize`
        is two codes; dropping either would leave a dual-colour card showing one icon.
        """
        card = by_id["2263"]
        assert card.color_codes == ["blue", "red"]
        assert localize(card, "ja").color_codes == ["blue", "red"]

    def test_the_opposite_printed_order_is_not_normalised_away(self, by_id: dict):
        """miComet prints red-then-blue where FUWAMOCO prints blue-then-red."""
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


class TestOriginalLabels:
    """The show-original toggle's payload.

    Emitted only where the source and the shown locale differ, so the +14% response cost
    is a ceiling rather than a constant — and so the frontend's check is
    `v-if="card.original"` with no per-field emptiness test.
    """

    def _card(self, **en):
        base = {
            "id": "1",
            "card_number": "hSD01-001",
            "card_type_code": "character",
            "rarity_code": "C",
            "image_key": "hSD01/hSD01-001_C",
            "source_image_url": "https://example.test/x.png",
            "card_sets": ["セット"],
            "arts": [{"cost_types": ["red"]}],
            "translations": {
                "ja": {
                    "name": "白上フブキ",
                    "tags": ["#EN"],
                    "arts": [{"name": "こんこん"}],
                },
                "en": {"name": "白上フブキ", "tags": ["#EN"], "arts": [{"name": "こんこん"}]},
            },
        }
        base["translations"]["en"].update(en)
        return Card.model_validate(base)

    def test_absent_on_a_source_locale_request(self):
        """Nothing to compare against; sending it would be pure waste."""
        assert localize(self._card(), "ja").original is None

    def test_absent_when_nothing_was_translated(self):
        """Every label identical, so the toggle has nothing to reveal."""
        assert localize(self._card(), "en").original is None

    def test_carries_the_source_name_when_it_differs(self):
        card = self._card(name="Shirakami Fubuki")

        original = localize(card, "en").original

        assert original is not None
        assert original.name == "白上フブキ"

    def test_omits_fields_that_match(self):
        """The art name was left in Japanese, so there is nothing to reveal about it."""
        original = localize(self._card(name="Shirakami Fubuki"), "en").original

        assert original.art_names == []
        assert original.keyword_name is None

    def test_art_names_are_positional_against_the_shown_arts(self):
        card = self._card(arts=[{"name": "Konkon"}])

        original = localize(card, "en").original

        assert original.art_names == ["こんこん"]

    def test_tags_are_all_or_nothing(self):
        """A partially-shown tag list reads as a data error, not a partial translation."""
        card = self._card(tags=["#EN-translated"])

        original = localize(card, "en").original

        assert original.tags == ["#EN"]

    def test_skill_names_are_carried(self):
        base = {
            "id": "1",
            "card_number": "hSD01-001",
            "card_type_code": "oshiCharacter",
            "rarity_code": "OSR",
            "image_key": "hSD01/hSD01-001_OSR",
            "source_image_url": "https://example.test/x.png",
            "card_sets": ["セット"],
            "oshi_skill": {"timing_code": "once_per_turn"},
            "translations": {
                "ja": {"name": "X", "oshi_skill": {"name": "秩序の先駆者", "effect": "効果"}},
                "en": {"name": "X", "oshi_skill": {"name": "Order's Pioneer", "effect": "Effect"}},
            },
        }

        original = localize(Card.model_validate(base), "en").original

        assert original.oshi_skill_name == "秩序の先駆者"
