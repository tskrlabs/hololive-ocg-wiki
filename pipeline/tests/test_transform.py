"""Tests for the structured → contract transform.

Each case here is a bug that actually occurred while porting, or an anomaly found by
census over the real 2,448-card dataset. The transform is the step where a wrong mapping
produces *plausible* wrong data, so these pin the shapes rather than the plumbing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from holo_data import mappings
from holo_data.transform import _arts, image_key_from_url, to_card
from holo_schema import Card
from holo_schema.enums import CARD_TYPE_VALUES


def _card_with_type(card_type: str) -> dict:
    """A card that is valid in every respect except the type under test."""
    return {
        "id": "9999",
        "card_number": "hBP99-001",
        "card_type_code": card_type,
        "rarity_code": "C",
        "image_key": "default/hBP99-001_C",
        "source_image_url": "https://example.invalid/hBP99-001_C.png",
        "card_sets": ["hBP99"],
        "translations": {"ja": {"name": "テスト"}},
    }


class TestImageKey:
    def test_uses_set_folder_from_official_url(self):
        """The set folder is what makes reprints distinct (D9)."""
        key = image_key_from_url(
            "https://hololive-official-cardgame.com/wp-content/images/cardlist/hBP08/hBP01-028_C_02.png",
            "hBP01-028_C_02.png",
        )
        assert key == "hBP08/hBP01-028_C_02"

    def test_reprints_get_distinct_keys(self):
        """hBP03-044_SR.png exists under two sets as two different cards.

        v1 stored the same `image_path` for both, so one overwrote the other. Under D9
        they would have collided as R2 objects.
        """
        original = image_key_from_url(
            "https://hololive-official-cardgame.com/wp-content/images/cardlist/hBP03/hBP03-044_SR.png",
            "hBP03-044_SR.png",
        )
        reprint = image_key_from_url(
            "https://hololive-official-cardgame.com/wp-content/images/cardlist/hCO01/hBP03-044_SR.png",
            "hBP03-044_SR.png",
        )
        assert original != reprint
        assert original == "hBP03/hBP03-044_SR"
        assert reprint == "hCO01/hBP03-044_SR"

    def test_falls_back_without_set_folder(self):
        assert image_key_from_url("https://example.test/x.png", "x.png") == "default/x"

    def test_none_when_no_image(self):
        assert image_key_from_url(None, None) is None


class TestArts:
    def test_tokkou_icon_is_not_a_cost_type(self):
        """The extractor puts the 特攻 icon in `cost_icons` too.

        Mapping it as a colour yields `unknown` and fails validation on 482 cards.
        """
        base, _ = _arts(
            {
                "arts": [
                    {
                        "cost_icons": [
                            {"alt": "白", "src": "/x/arts_white.png"},
                            {"alt": "◇", "src": "/x/arts_null.png"},
                            {"alt": "紫+50", "src": "/x/tokkou_50_purple.png"},
                        ],
                        "damage": "70+",
                        "tokkou": [
                            {"alt": "紫+50", "src": "/x/tokkou_50_purple.png"}
                        ],
                    }
                ]
            }
        )
        assert base[0]["cost_types"] == ["white", "null"]

    def test_special_targets_parsed_from_alt_and_filename(self):
        """Alt text is colour+bonus ("紫+50"); the amount comes from the filename."""
        base, _ = _arts(
            {
                "arts": [
                    {
                        "cost_icons": [{"alt": "白", "src": "/x/arts_white.png"}],
                        "tokkou": [
                            {"alt": "紫+50", "src": "/x/tokkou_50_purple.png"}
                        ],
                    }
                ]
            }
        )
        assert base[0]["special_targets"] == ["purple"]
        assert base[0]["special_values"] == [50]

    def test_no_cost_count_is_emitted(self):
        """v1's `cost_count` was `len(cost_icons)`, so it counted the 特攻 icon too.

        v2 does not emit the field at all — `cost_types` is the cost list and its length
        is the count, which cannot drift from it (F-002). The art below is the case that
        used to disagree: 2 icons, 1 real cost.
        """
        base, _ = _arts(
            {
                "arts": [
                    {
                        "cost_icons": [
                            {"alt": "白", "src": "/x/arts_white.png"},
                            {"alt": "紫+50", "src": "/x/tokkou_50_purple.png"},
                        ],
                        "tokkou": [{"alt": "紫+50", "src": "/x/tokkou_50_purple.png"}],
                    }
                ]
            }
        )
        assert "cost_count" not in base[0]
        assert base[0]["cost_types"] == ["white"]

    def test_plus_damage(self):
        base, _ = _arts(
            {"arts": [{"cost_icons": [], "damage": "70+"}]}
        )
        assert base[0]["damage"] == 70
        assert base[0]["is_plus"] is True

    def test_translated_half_is_split_out(self):
        base, translated = _arts(
            {"arts": [{"cost_icons": [], "name": "ハイRyS！", "effect": "効果"}]}
        )
        assert "name" not in base[0]
        assert translated[0] == {"name": "ハイRyS！", "effect": "効果"}


class TestKeyword:
    def test_type_comes_from_icon_alt_not_name(self):
        """`name` is the ability's title; the *type* is the icon's alt text.

        Reading `name` here dropped the keyword on all 1,124 cards that have one.
        """
        card = to_card(
            {
                "id": "4",
                "keyword": {
                    "icon": {"alt": "コラボエフェクト", "src": "/x/collabEF.png"},
                    "name": "レッツダンス！",
                    "effect": "このターンの間…",
                },
            }
        )
        assert card["keyword"] == {
            "type": "コラボエフェクト",
            "type_code": "collab_effect",
        }
        assert card["translations"]["ja"]["keyword"]["name"] == "レッツダンス！"

    def test_unmapped_keyword_type_is_dropped(self):
        card = to_card(
            {"id": "1", "keyword": {"icon": {"alt": "新しい"}, "name": "x"}}
        )
        assert "keyword" not in card


class TestTags:
    def test_card_tags_unprefixed_translation_tags_prefixed(self):
        """Both are kept — they genuinely differ on 268 card-locale pairs (ADR 0001)."""
        card = to_card(
            {"id": "1", "info": {"タグ": [{"name": "#EN"}, {"name": "#歌"}]}}
        )
        assert card["tags"] == ["EN", "歌"]
        assert card["translations"]["ja"]["tags"] == ["#EN", "#歌"]


class TestColors:
    def test_fused_colour_is_one_code(self):
        """`青赤` is a single printed symbol, not two colours (ADR 0001)."""
        card = to_card(
            {
                "id": "1",
                "info": {"色": [{"images": [{"alt": "青赤"}], "count": 1}]},
            }
        )
        assert card["color_codes"] == ["blue_red"]

    def test_two_colours_stay_two(self):
        card = to_card(
            {
                "id": "1",
                "info": {"色": [{"images": [{"alt": "赤"}, {"alt": "青"}], "count": 2}]},
            }
        )
        assert card["color_codes"] == ["red", "blue"]

    def test_colourless(self):
        card = to_card(
            {"id": "1", "info": {"色": [{"images": [{"alt": "◇"}], "count": 1}]}}
        )
        assert card["color_codes"] == ["null"]


class TestCardType:
    def test_unmapped_becomes_unknown(self):
        """`unknown` is a documented, legitimate code — the scraper's safety valve.

        No card carries it today (F-001 fixed the last two by adding the missing
        `サポート・スタッフ` mapping), which is what makes it a *silent* channel — see
        docs/archive/findings.md F-024.
        """
        card = to_card({"id": "1", "info": {"カードタイプ": "新種別"}})
        assert card["card_type_code"] == "unknown"

    def test_mapping_may_exceed_the_contract_deliberately(self):
        """`CARD_TYPE` emits a code `CardTypeCode` rejects, and that is the point.

        `サポート・ロケーション → supportLocation` is a mapping for a string the official
        site has never printed — a census of all 2,464 scraped cards finds fourteen
        distinct card types and that is not one of them. It is kept anyway: a card
        carrying it would be a genuinely new mechanic, and stopping the build beats
        shipping it as `unknown`, which validates and is then excluded from every deck
        section with nothing to announce it.

        This is not hypothetical. Bare `サポート` was the same kind of evidence-free
        mapping until the 2,464-card refresh printed it, and that entry is what caught
        the Selection Cup notice (F-020) — the first and only time the guard has fired.

        Two assertions because two different tidy-ups would disarm it, and `make check`
        would stay green through either: deleting the mapping entry (the card silently
        becomes `unknown`), or widening the enum to accept it (the card silently
        validates). See docs/archive/findings.md F-008.
        """
        assert "サポート・ロケーション" in mappings.CARD_TYPE, (
            "the mapping entry is the guard — without it a Location card becomes "
            "`unknown` and ships silently (findings.md F-008)"
        )
        emitted = mappings.CARD_TYPE["サポート・ロケーション"]
        assert emitted not in CARD_TYPE_VALUES, (
            "the divergence is deliberate — admitting this code to the enum makes a "
            "genuinely new card type validate instead of failing loudly"
        )

        with pytest.raises(ValidationError) as exc:
            Card.model_validate(_card_with_type(emitted))
        assert any(
            error["type"] == "literal_error" and error["loc"] == ("card_type_code",)
            for error in exc.value.errors()
        )

    @pytest.mark.parametrize(
        "japanese,expected",
        [
            ("ホロメン", "character"),
            ("推しホロメン", "oshiCharacter"),
            ("エール", "supportCheer"),
        ],
    )
    def test_known_types(self, japanese, expected):
        card = to_card({"id": "1", "info": {"カードタイプ": japanese}})
        assert card["card_type_code"] == expected


class TestBloomLevel:
    def test_uses_data_spelling(self):
        """v1's frontend constant said `1st`/`2nd`; the data says `first`/`second`."""
        card = to_card({"id": "1", "info": {"Bloomレベル": "1st"}})
        assert card["bloom_level_code"] == "first"


class TestSkills:
    def test_timing_code_split_from_translation(self):
        card = to_card(
            {
                "id": "1",
                "oshi_skill": {
                    "name": "スキル",
                    "effect": "効果",
                    "timing": "ターンに1回",
                },
            }
        )
        assert card["oshi_skill"] == {"timing_code": "once_per_turn"}
        assert card["translations"]["ja"]["oshi_skill"]["timing"] == "ターンに1回"

    def test_no_cost_field(self):
        """v1 declared `cost` in three places; no card has ever had it."""
        card = to_card(
            {"id": "1", "oshi_skill": {"name": "x", "cost": "-2", "timing": "ターンに1回"}}
        )
        assert "cost" not in card["oshi_skill"]
