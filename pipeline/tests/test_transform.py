"""Tests for the structured → contract transform.

Each case here is a bug that actually occurred while porting, or an anomaly found by
census over the real 2,448-card dataset. The transform is the step where a wrong mapping
produces *plausible* wrong data, so these pin the shapes rather than the plumbing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from holo_data import mappings
from holo_data.transform import (
    UnmappedReport,
    _arts,
    image_key_from_url,
    to_card,
    transform_cards,
)
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


class TestTransformMatchesTheContract:
    """The transformer's output must validate as a `Card`.

    This is the gate that was missing when `holo-data build` broke (issue #16). The
    contract dropped `cost_count` and the transformer stopped emitting it, but nothing
    asserted the two agreed — so the disagreement was only visible three artifacts
    downstream, in a command `make check` does not run. `make fixtures` and
    `holo-data build` were both broken for two commits with `make check` green.

    `Card` is `extra="forbid"`, so a field the transformer emits and the contract does
    not model fails here rather than in a build nobody runs. The reverse — a required
    field the transformer stops emitting — fails here too.

    The input is a scraper-shaped literal rather than a committed sample: the real
    inputs are gitignored working state (an 8.5 MB scrape artifact), so a test reading
    them would pass on one laptop and skip everywhere else. That is the failure mode
    this test exists to close, not to repeat.
    """

    def _structured_card(self) -> dict:
        """One entry shaped like `cards_structured.json`, exercising the tricky paths.

        Carries a 特攻 icon beside a real cost icon, which is the shape behind F-002:
        the extractor collects both as sibling `<img>` tags, and v1 counted them
        together.
        """
        return {
            "id": "9999",
            "name": "テストホロメン",
            "image_url": (
                "https://hololive-official-cardgame.com/wp-content/images/"
                "cardlist/hBP99/hBP99-001_RR.png"
            ),
            "image_filename": "hBP99-001_RR.png",
            "info": {
                "カードナンバー": "hBP99-001",
                "カードタイプ": "ホロメン",
                "レアリティ": "RR",
                "Bloomレベル": "1st",
                "HP": "150",
                "色": [{"images": [{"alt": "赤", "src": "/images/texticon/type_red.png"}]}],
                "バトンタッチ": [
                    {"images": [{"alt": "◇", "src": "/images/texticon/arts_null.png"}]}
                ],
                "タグ": [{"name": "#EN", "href": "/cardlist/cardsearch?keyword=%23EN"}],
            },
            "card_set": {"value": ["テストセット"], "count": 1},
            "arts": [
                {
                    "name": "テストアーツ",
                    "effect": "テスト効果",
                    "damage": "100+",
                    "cost_icons": [
                        {"alt": "赤", "src": "/images/texticon/arts_red.png"},
                        # Not a cost — the 特攻 marker. Counting it is F-002.
                        {"alt": "紫+50", "src": "/images/texticon/tokkou_50_purple.png"},
                    ],
                    "tokkou": [
                        {"alt": "紫+50", "src": "/images/texticon/tokkou_50_purple.png"}
                    ],
                }
            ],
            "qa_items": [
                {
                    "title": "Q1（2026.01.01）",
                    "question": "質問",
                    "answer": "回答",
                    "related_cards": {
                        "raw_html": "[hBP99-001 ： テスト]",
                        "card_number": ["hBP99-001"],
                    },
                }
            ],
        }

    def test_transform_output_validates_as_a_card(self):
        """The whole point: `to_card` output is a valid `Card`, with no extra keys."""
        card = Card.model_validate(to_card(self._structured_card()))

        assert card.id == "9999"
        assert card.card_type_code == "character"
        assert card.image_key == "hBP99/hBP99-001_RR"

    def test_transform_emits_no_field_the_contract_dropped(self):
        """The exact regression: a dropped field silently surviving in the output.

        Named explicitly rather than left to `extra="forbid"` so the failure says
        *which* field came back, and so removing a field from the contract has a
        matching assertion to update here.
        """
        card = to_card(self._structured_card())

        for art in card.get("arts") or []:
            assert "cost_count" not in art, "F-002 removed `cost_count` from the contract"
        for translation in card["translations"].values():
            for art in translation.get("arts") or []:
                assert "value" not in art, "F-003 removed `value` from `TranslatedArt`"

    def test_the_tokkou_icon_is_not_counted_as_a_cost(self):
        """F-002's cause, pinned: 482 arts got an `unknown` cost type from this icon."""
        card = Card.model_validate(to_card(self._structured_card()))

        assert card.arts[0].cost_types == ["red"]
        assert card.arts[0].special_targets == ["purple"]
        assert card.arts[0].special_values == [50]

    def test_a_notice_entry_also_transforms(self):
        """Notices ride in the same list and must survive the transform (F-020)."""
        notice = to_card(
            {"id": "9998", "name": "お知らせ", "info": {"カードタイプ": "ルール notice"}}
        )
        assert notice["id"] == "9998"


class TestUnmappedReport:
    """What the site printed, kept long enough to say it out loud (issue #19).

    The mapping tables substitute `UNMAPPED` and discard the source string, so this is
    the last point in the pipeline where it exists. Without the report, `build` fails
    with "Input should be 'debut', 'first', 'second' or 'spot'" — it names the four
    values we accept and never `超進化`, the one the site actually printed. The operator
    got a card id and a page to open by hand.

    Verified against the real 2,464-entry scrape: the report is empty, so it stays
    silent on an ordinary run and only speaks when there is something to fix.
    """

    def test_an_unmapped_card_type_is_reported_with_its_source_value(self):
        report = UnmappedReport()
        card = to_card({"id": "1", "info": {"カードタイプ": "サポート・新種別"}}, report)

        assert card["card_type_code"] == "unknown", "the sentinel is still written"
        assert report.rows() == [("card_type", "サポート・新種別", ["1"])]

    def test_an_unmapped_bloom_level_is_reported(self):
        report = UnmappedReport()
        to_card({"id": "1", "info": {"Bloomレベル": "超進化"}}, report)
        assert ("bloom_level", "超進化", ["1"]) in report.rows()

    def test_an_unmapped_colour_is_reported(self):
        report = UnmappedReport()
        to_card({"id": "1", "info": {"色": [{"images": [{"alt": "虹"}], "count": 1}]}}, report)
        assert ("color", "虹", ["1"]) in report.rows()

    def test_a_silently_omitted_value_is_reported_too(self):
        """Skill timing and keyword type *drop* the value rather than substituting.

        No sentinel, so nothing fails validation: the card ships with no timing badge or
        no keyword at all. That is strictly quieter than the four enum fields — it is
        the shape of the bug that cost 1,124 cards their keyword on the first run — so
        it belongs in the same report even though it never blocks a build.
        """
        report = UnmappedReport()
        card = to_card(
            {
                "id": "1",
                "oshi_skill": {"timing": "新タイミング", "name": "x", "effect": "y"},
                "keyword": {"icon": {"alt": "新エフェクト"}, "name": "z"},
            },
            report,
        )

        assert "timing_code" not in (card.get("oshi_skill") or {})
        assert "keyword" not in card
        fields = {row[0] for row in report.rows()}
        assert {"oshi_skill.timing", "keyword.type"} <= fields

    def test_a_mapped_value_is_not_reported(self):
        report = UnmappedReport()
        to_card({"id": "1", "info": {"カードタイプ": "ホロメン"}}, report)
        assert report.is_empty

    def test_cards_sharing_a_value_are_grouped(self):
        """One row per (field, value) — a markup change is one problem, not 500."""
        report = UnmappedReport()
        for card_id in ("1", "2", "3"):
            to_card({"id": card_id, "info": {"カードタイプ": "サポート・新種別"}}, report)

        assert report.rows() == [("card_type", "サポート・新種別", ["1", "2", "3"])]
        assert report.card_count == 3

    def test_rows_lead_with_the_most_affected(self):
        """A markup change should out-rank a single odd card in the output."""
        report = UnmappedReport()
        to_card({"id": "1", "info": {"カードタイプ": "サポート・新種別"}}, report)
        for card_id in ("2", "3", "4"):
            to_card(
                {"id": card_id, "info": {"色": [{"images": [{"alt": "虹"}], "count": 1}]}},
                report,
            )

        assert [row[0] for row in report.rows()] == ["color", "card_type"]

    def test_transform_cards_always_collects_one(self):
        """The report is not optional on the batch path — it is the whole point."""
        cards, report = transform_cards(
            [{"id": "1", "info": {"カードタイプ": "サポート・新種別"}}]
        )
        assert len(cards) == 1
        assert not report.is_empty

    def test_a_clean_batch_reports_nothing(self):
        _cards, report = transform_cards([{"id": "1", "info": {"カードタイプ": "ホロメン"}}])
        assert report.is_empty
        assert report.card_count == 0
