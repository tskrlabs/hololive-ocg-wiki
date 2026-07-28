"""Tests for the canonical card contract.

These pin the decisions that would otherwise be re-litigated silently: which enum
members exist, which fields are optional, and which validators must fire.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from holo_schema import (
    BLOOM_LEVEL_VALUES,
    CARD_TYPE_VALUES,
    COLOR_VALUES,
    NON_CARD_TYPES,
    RARITY_VALUES,
    Card,
    CardCollection,
)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "cards.json"


@pytest.fixture(scope="module")
def collection() -> CardCollection:
    return CardCollection.model_validate_json(FIXTURES.read_text(encoding="utf-8"))


def _minimal_card(**overrides) -> dict:
    """The smallest card that validates. Override to test one thing at a time."""
    base = {
        "id": "1",
        "card_number": "hBP01-001",
        "card_type_code": "character",
        "rarity_code": "C",
        "image_key": "hBP01/hBP01-001_C",
        "source_image_url": "https://example.test/hBP01-001_C.png",
        "card_sets": ["Test Set"],
        "translations": {"ja": {"name": "テスト"}},
    }
    base.update(overrides)
    return base


class TestEnums:
    """The enum members that v1's TypeScript got wrong."""

    def test_hr_rarity_exists(self):
        """24 cards use HR; v1's TypeScript union omitted it, so they were unfilterable."""
        assert "HR" in RARITY_VALUES
        assert Card.model_validate(_minimal_card(rarity_code="HR")).rarity_code == "HR"

    def test_unknown_card_type_is_legitimate(self):
        """The scraper writes 'unknown' when it cannot classify; 2 cards have it."""
        assert "unknown" in CARD_TYPE_VALUES
        card = Card.model_validate(_minimal_card(card_type_code="unknown"))
        assert card.card_type_code == "unknown"

    def test_bloom_levels_use_data_spelling(self):
        """v1's constants said 1st/2nd; the data says first/second."""
        assert BLOOM_LEVEL_VALUES == ("debut", "first", "second", "spot")
        assert "1st" not in BLOOM_LEVEL_VALUES

    def test_fused_colors_are_first_class(self):
        """`blue_red` is one printed symbol, not shorthand for two colours."""
        assert "blue_red" in COLOR_VALUES
        assert "white_green" in COLOR_VALUES
        card = Card.model_validate(_minimal_card(color_codes=["blue_red"]))
        assert card.color_codes == ["blue_red"]

    def test_multi_color_array_still_works(self):
        """miComet genuinely has two separate colour symbols."""
        card = Card.model_validate(_minimal_card(color_codes=["red", "blue"]))
        assert card.color_codes == ["red", "blue"]

    def test_unknown_enum_value_rejected(self):
        with pytest.raises(ValidationError):
            Card.model_validate(_minimal_card(rarity_code="NOT_A_RARITY"))


class TestOptionality:
    """Absent fields are omitted, never null — verified by census over 2,448 cards."""

    def test_absent_fields_omitted_from_json(self):
        card = Card.model_validate(_minimal_card())
        payload = card.model_dump(mode="json", exclude_none=True)
        for field in ("hp", "life", "bloom_level_code", "illustrator", "tags"):
            assert field not in payload

    def test_hp_optional(self):
        """733 cards have no HP — only Holomem cards do."""
        assert Card.model_validate(_minimal_card()).hp is None

    def test_colors_optional(self):
        """419 support cards have no colour."""
        assert Card.model_validate(_minimal_card()).color_codes is None


class TestValidators:
    def test_source_locale_required(self):
        """Every card must have `ja` — everything else is translated from it."""
        with pytest.raises(ValidationError, match="source locale"):
            Card.model_validate(
                _minimal_card(translations={"en": {"name": "Test"}})
            )

    def test_card_sets_non_empty(self):
        with pytest.raises(ValidationError, match="card_sets"):
            Card.model_validate(_minimal_card(card_sets=[]))

    def test_extra_keys_rejected(self):
        """An unrecognised key means the source site changed — fail loudly."""
        with pytest.raises(ValidationError):
            Card.model_validate(_minimal_card(surprise_field="x"))

    def test_special_pairs_must_align(self):
        """special_targets and special_values are positional pairs."""
        with pytest.raises(ValidationError, match="positional pairs"):
            Card.model_validate(
                _minimal_card(
                    arts=[
                        {
                            "cost_count": 1,
                            "special_targets": ["red", "blue"],
                            "special_values": [50],
                        }
                    ]
                )
            )

    def test_special_pairs_both_or_neither(self):
        with pytest.raises(ValidationError, match="must both be present or both absent"):
            Card.model_validate(
                _minimal_card(arts=[{"cost_count": 1, "special_targets": ["red"]}])
            )


class TestCollectionValidators:
    def test_duplicate_image_key_rejected(self):
        """The D9 guard: two cards sharing a key would collide as R2 objects.

        v1's data has exactly this bug — hCO01 reprints reuse the original set's image
        filename, so hBP03-044_SR mapped to two different card ids.
        """
        cards = [
            _minimal_card(id="1", image_key="same/key"),
            _minimal_card(id="2", image_key="same/key"),
        ]
        with pytest.raises(ValidationError, match="duplicate image_key"):
            CardCollection(generated_at="2026-01-01T00:00:00Z", cards=cards)

    def test_duplicate_id_rejected(self):
        cards = [
            _minimal_card(id="1", image_key="a/1"),
            _minimal_card(id="1", image_key="b/2"),
        ]
        with pytest.raises(ValidationError, match="duplicate card ids"):
            CardCollection(generated_at="2026-01-01T00:00:00Z", cards=cards)

    def test_card_number_may_repeat(self):
        """card_number is NOT unique — rarity variants share one (hBP01-104 has 9)."""
        cards = [
            _minimal_card(id="1", card_number="hBP01-104", image_key="a/1"),
            _minimal_card(id="2", card_number="hBP01-104", image_key="a/2"),
        ]
        collection = CardCollection(generated_at="2026-01-01T00:00:00Z", cards=cards)
        assert len(collection.cards) == 2


class TestFixtures:
    """The committed fixture set must stay valid and keep covering the edge cases."""

    def test_fixtures_validate(self, collection: CardCollection):
        assert len(collection.cards) > 25

    def test_fixtures_cover_every_card_type(self, collection: CardCollection):
        """Every card type that any real card uses must appear in the fixtures.

        Two exclusions, for different reasons:

        `unknown` is the scraper's placeholder for a type it cannot classify, and since
        F-001 fixed the missing `サポート・スタッフ` mapping, no card carries it. It stays
        in the enum as a safety valve for the next unrecognised type, but there is no
        card to make a fixture from.

        `rulesNotice` (NON_CARD_TYPES) *cannot* appear here — `Card` rejects it outright,
        because it is not a card. It is covered by `pipeline/tests/test_notices.py`
        instead. Subtracting it rather than deleting the assertion is deliberate: the
        test still fails if a genuinely new *card* type is added without a fixture.
        """
        present = {card.card_type_code for card in collection.cards}
        assert present == set(CARD_TYPE_VALUES) - {"unknown"} - set(NON_CARD_TYPES)

    def test_fixtures_cover_every_rarity(self, collection: CardCollection):
        present = {card.rarity_code for card in collection.cards}
        assert present == set(RARITY_VALUES)

    def test_fixtures_include_arts_mismatch_cards(self, collection: CardCollection):
        """hSD03-009 / hSD04-009: 2 arts, 0 `en` translations."""
        ids = {card.id for card in collection.cards}
        assert {"446", "447"} <= ids

    def test_fixtures_include_reprint_collision_pairs(self, collection: CardCollection):
        ids = {card.id for card in collection.cards}
        assert {"726", "2138", "735", "2139"} <= ids

    def test_fixture_image_keys_unique(self, collection: CardCollection):
        keys = [card.image_key for card in collection.cards]
        assert len(keys) == len(set(keys))


class TestImageUrl:
    def test_composes_from_key(self):
        card = Card.model_validate(_minimal_card(image_key="default/hBP01-028_C_02"))
        assert (
            card.image_url("https://img.example.com")
            == "https://img.example.com/default/hBP01-028_C_02.webp"
        )

    def test_trailing_slash_tolerated(self):
        card = Card.model_validate(_minimal_card(image_key="a/b"))
        assert card.image_url("https://img.example.com/") == "https://img.example.com/a/b.webp"
