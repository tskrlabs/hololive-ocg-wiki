"""Tests for the canonical card contract.

These pin the decisions that would otherwise be re-litigated silently: which enum
members exist, which fields are optional, and which validators must fire.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from holo_schema import (
    BLOOM_LEVEL_VALUES,
    CARD_TYPE_VALUES,
    COLOR_VALUES,
    RARITY_VALUES,
    Card,
    CardCollection,
)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "cards.json"

# The corpus generator, imported for its *rules* — see TestFixtures. Importing it does
# not pull in the pipeline: `_default_source()` imports `holo_data.paths` lazily, so
# `holo-schema` stays installable and testable on its own.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_fixtures  # noqa: E402


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

    def test_unknown_card_type_is_rejected(self):
        """The scraper's fallback must not validate (issue #19).

        `unknown` was a legal member until #19. The pipeline writes it at eight sites
        across four enums and this was the only one that accepted it, so an unrecognised
        value from the site stopped the build in three fields and shipped silently in the
        fourth — where the card was then excluded from every deck section, counted by
        nothing and printed by nothing.

        That is F-001's shape: two ライブスタッフ cards sat in v1's live data as
        `unknown` from the day they shipped, found by a hand-run census during the v2
        port rather than by anything the pipeline said.

        The graceful-degradation argument the member was added for is now served by
        `build --allow-unknown-enums`, which drops such cards and records that it did —
        an operator's choice, not a silent default.
        """
        assert "unknown" not in CARD_TYPE_VALUES

        with pytest.raises(ValidationError) as exc:
            Card.model_validate(_minimal_card(card_type_code="unknown"))
        assert exc.value.errors()[0]["type"] == "literal_error"

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
                            "cost_types": ["red"],
                            "special_targets": ["red", "blue"],
                            "special_values": [50],
                        }
                    ]
                )
            )

    def test_special_pairs_both_or_neither(self):
        with pytest.raises(ValidationError, match="must both be present or both absent"):
            Card.model_validate(
                _minimal_card(arts=[{"cost_types": ["red"], "special_targets": ["red"]}])
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
    """The committed corpus must still satisfy the rules that selected it.

    **This is the drift gate** (issue #16). `fixtures/cards.json` is generated, but its
    generator's input — `holo-data build` output — is gitignored working state, so
    `make check` cannot re-run the generator and byte-compare. That is what let a
    generated file and the generator claiming to produce it disagree for two commits
    with `make check` green.

    So these assert the *invariants* rather than the bytes: every coverage rule the
    generator encodes is satisfied by the committed corpus, and every pinned anomaly is
    present. Both run from a fresh clone with no source data and no Python pipeline.

    The rules come from `build_fixtures.py` itself rather than being restated here. A
    second copy of the list is exactly how the previous version of this file ended up
    asserting the opposite of what the generator's rules said.
    """

    def test_fixtures_validate(self, collection: CardCollection):
        assert len(collection.cards) > 25

    def test_every_coverage_rule_is_satisfied(self, collection: CardCollection):
        """Each rule the generator selects for must have at least one card covering it.

        Fails if a rule stops being covered — whether because the source data changed,
        the selection changed, or someone hand-edited the corpus.
        """
        uncovered = [
            label
            for label, predicate in build_fixtures._coverage_rules()
            if not any(predicate(card) for card in collection.cards)
        ]
        assert not uncovered, (
            f"the committed corpus no longer covers: {', '.join(uncovered)} — "
            "regenerate with `make fixtures`, or delete the rule if it has become "
            "unsatisfiable (and say why, as F-001 and F-020 did)"
        )

    def test_every_pinned_card_is_present(self, collection: CardCollection):
        """The pinned anomalies are the bugs the contract must survive.

        Coverage selection would not necessarily pick any of them, so losing one is
        silent: the corpus still covers every enum, and a real production bug stops
        being pinned.
        """
        ids = {card.id for card in collection.cards}
        missing = {
            cid: reason
            for cid, reason in build_fixtures.PINNED.items()
            if cid not in ids
        }
        assert not missing, f"pinned cards missing from the corpus: {missing}"

    def test_the_synthetic_short_arts_card_is_present(self, collection: CardCollection):
        """No real card can cover `localize()` merge rule 2 any more.

        A census over all 2,463 cards finds zero arts-length mismatches in any locale,
        so this fixture is the only thing exercising that branch — in Python *and*
        TypeScript. Asserted separately from the coverage rules because it is not
        selected by one: it is appended unconditionally.
        """
        by_id = {card.id: card for card in collection.cards}
        card = by_id.get(build_fixtures.SYNTHETIC_ID)
        assert card is not None, "the synthetic short-arts fixture is gone"
        assert len(card.arts or []) == 2
        assert len(card.translations["en"].arts or []) == 0, (
            "the short translated arts list is the whole point of this fixture"
        )

    def test_the_corpus_holds_no_other_synthetic_card(self, collection: CardCollection):
        """One synthetic fixture, deliberately.

        The corpus is real data plus one documented exception; a second would mean the
        selection had quietly become hand-curated. Ids run 1..2457, so anything in the
        reserved range is synthetic by construction.
        """
        synthetic = {card.id for card in collection.cards if int(card.id) >= 9000000}
        assert synthetic == {build_fixtures.SYNTHETIC_ID}

    def test_card_ids_txt_matches_the_corpus(self, collection: CardCollection):
        """The committed id list is the reviewable form of the selection.

        If it disagrees with cards.json, a PR that changed which cards are fixtures
        showed up as the wrong diff — which is the property the list exists to give.
        """
        listed = {
            line.split()[0]
            for line in (FIXTURES.parent / "card-ids.txt").read_text("utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        assert listed == {card.id for card in collection.cards}

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
