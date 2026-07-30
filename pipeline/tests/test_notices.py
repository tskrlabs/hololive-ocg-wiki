"""Rules notices — the non-card entries the official site publishes into its card list.

Every case here is behaviour the 2,464-card refresh actually exercised. Id 2459
(デッキ構築ルール) is a Selection Cup format-legality notice: no card number, no rarity,
and the bare `サポート` card type. It failed `build` loudly on first contact, which is
the contract working; these tests pin the resolution so it stays working.

See `holo_schema.notice` for why a notice is not a `Card`, and docs/archive/findings.md F-020.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from holo_schema import Card, Notice, NoticeCollection
from holo_schema.enums import (
    MAIN_CARD_TYPES,
    NON_CARD_TYPES,
    OSHI_CARD_TYPES,
    YELL_CARD_TYPES,
)
from holo_data import build as build_module
from holo_data.transform import is_notice, to_card, to_notice
from holo_data.translate.cache import TranslationCache


# The real shape id 2459 arrives in, reduced to what the transform reads.
NOTICE_SOURCE = {
    "id": "2459",
    "name": "デッキ構築ルール",
    "image_url": (
        "https://hololive-official-cardgame.com/wp-content/images/cardlist/"
        "sele08/sele08_teaching.png"
    ),
    "image_filename": "sele08_teaching.png",
    "info": {
        "カードタイプ": "サポート",
        "能力テキスト": "※本説明用カードはデッキ登録できません。",
        # The site renders a missing number as the literal string "null".
        "カードナンバー": "null",
    },
    "card_set": {"value": ["【使用可能カード】セレクションカップ"]},
}


class TestClassification:
    def test_bare_support_type_becomes_a_rules_notice(self):
        """`サポート` with no subtype is the notice signature.

        No printed card has ever used the bare type — every real support card carries a
        subtype (`サポート・イベント`, `サポート・ツール`, …).
        """
        entry = to_card(NOTICE_SOURCE)
        assert entry["card_type_code"] == "rulesNotice"
        assert is_notice(entry)

    def test_a_real_card_is_not_a_notice(self):
        entry = to_card({"id": "1", "info": {"カードタイプ": "ホロメン"}})
        assert entry["card_type_code"] == "character"
        assert not is_notice(entry)

    def test_literal_null_card_number_is_dropped(self):
        """Storing the string "null" would put it in an indexed column and the FTS
        index, where it would match a search for the word."""
        entry = to_card(NOTICE_SOURCE)
        assert "card_number" not in entry


class TestNoticeIsNotACard:
    def test_card_rejects_a_notice_type(self):
        """The split is enforced at the contract, not only by the caller.

        If a notice ever reached `Card`, it would be stored as a card row with a
        fabricated number and rarity — the silent lie the separate model prevents.
        """
        entry = to_card(NOTICE_SOURCE)
        entry["card_number"] = "hXX-001"
        entry["rarity_code"] = "C"
        with pytest.raises(ValidationError, match="not a card"):
            Card.model_validate(entry)

    def test_card_number_and_rarity_stay_required_for_cards(self):
        """The notice must not have loosened the contract for real cards.

        A scraper regression that stopped parsing rarity across hundreds of cards has to
        keep failing loudly — that is the invariant option C was chosen to protect.
        """
        entry = to_card({"id": "1", "info": {"カードタイプ": "ホロメン"}})
        entry.update(
            image_key="x/y", source_image_url="http://x", card_sets=["s"]
        )
        with pytest.raises(ValidationError):
            Card.model_validate(entry)

    def test_no_deck_section_can_hold_a_notice(self):
        """Structural, not a consumer-side filter (Phase 5's F-019 lesson)."""
        for section in (OSHI_CARD_TYPES, MAIN_CARD_TYPES, YELL_CARD_TYPES):
            for non_card in NON_CARD_TYPES:
                assert non_card not in section


class TestProjection:
    def test_ability_text_becomes_the_body(self):
        entry = to_card(NOTICE_SOURCE)
        notice = Notice.model_validate(to_notice(entry))
        assert notice.translations["ja"].name == "デッキ構築ルール"
        assert "デッキ登録できません" in notice.translations["ja"].body

    def test_card_only_fields_are_dropped_not_nulled(self):
        entry = to_card(NOTICE_SOURCE)
        projected = to_notice(entry)
        for field in ("card_number", "rarity_code", "card_type_code", "hp"):
            assert field not in projected

    def test_card_sets_is_kept(self):
        """The shared vocabulary is the join: this value is what the same update added
        to ~660 existing cards, and the notice is what explains it."""
        notice = Notice.model_validate(to_notice(to_card(NOTICE_SOURCE)))
        assert notice.card_sets == ["【使用可能カード】セレクションカップ"]

    def test_source_locale_is_required(self):
        with pytest.raises(ValidationError, match="source locale"):
            Notice.model_validate(
                {
                    "id": "1",
                    "image_key": "x/y",
                    "source_image_url": "http://x",
                    "translations": {"en": {"name": "x"}},
                }
            )


class TestBuildSplit:
    def test_notices_are_split_out_and_not_counted_as_cards(self):
        card = to_card(
            {
                "id": "1",
                "name": "テスト",
                "image_url": (
                    "https://hololive-official-cardgame.com/wp-content/images/"
                    "cardlist/hBP01/hBP01-001_C.png"
                ),
                "image_filename": "hBP01-001_C.png",
                "info": {
                    "カードタイプ": "ホロメン",
                    "レアリティ": "C",
                    "カードナンバー": "hBP01-001",
                },
                "card_set": {"value": ["テストセット"]},
            }
        )
        notice = to_card(NOTICE_SOURCE)

        collection, notices, report = build_module.build(
            [card, notice], TranslationCache(), []
        )

        assert collection is not None and notices is not None
        assert report.total == 1, "the notice must not inflate the card count"
        assert report.notice_count == 1
        assert [c.id for c in collection.cards] == ["1"]
        assert [n.id for n in notices.notices] == ["2459"]

    def test_a_build_with_no_notices_still_produces_a_collection(self):
        """`notices.json` is always written, so a consumer can tell "none" from
        "missing" without treating a 404 as success."""
        card = to_card(
            {
                "id": "1",
                "name": "テスト",
                "image_url": (
                    "https://hololive-official-cardgame.com/wp-content/images/"
                    "cardlist/hBP01/hBP01-001_C.png"
                ),
                "image_filename": "hBP01-001_C.png",
                "info": {
                    "カードタイプ": "ホロメン",
                    "レアリティ": "C",
                    "カードナンバー": "hBP01-001",
                },
                "card_set": {"value": ["テストセット"]},
            }
        )
        _, notices, report = build_module.build([card], TranslationCache(), [])
        assert notices is not None and notices.notices == []
        assert report.notice_count == 0


class TestNoticeCollection:
    def test_duplicate_ids_are_rejected(self):
        entry = to_notice(to_card(NOTICE_SOURCE))
        with pytest.raises(ValidationError, match="duplicate notice id"):
            NoticeCollection(generated_at="2026-07-28T00:00:00Z", notices=[entry, entry])
