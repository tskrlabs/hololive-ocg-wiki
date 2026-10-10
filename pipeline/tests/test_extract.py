"""Tests for the HTML -> structured extraction, on snippets of real card markup.

The first tests of `extract_structured_data`. They exist because of 推しステージスキル: the
site added a third skill block with hBP07, the extractor read only the two classes it
named, and the new rules text was dropped without a word for three sets.
"""

from __future__ import annotations

import pytest

from holo_data.scrape.extract import UnknownSkillBlock, extract_structured_data

# hBP07-001, trimmed. A stage skill with no timing bracket, then an oshi skill.
WATAME = """
<div class="txt-Inner center-Txtarea">
  <div class="info"><dl><dt>カードタイプ</dt><dd>推しホロメン</dd></dl></div>
  <div class="stage skill"><p>推しステージスキル</p><p><span>ドドドライブ</span>自分の〈角巻わため〉がアーツを使った時、自分のデッキの上から1枚をホロパワーにする。</p></div>
  <div class="oshi skill"><p>推しスキル</p><p>[ホロパワー:-6]<span>角ドリルしたろか？</span>[ターンに1回]このターンの間、自分のステージの〈角巻わため〉全員のアーツ+100。</p></div>
  <div class="illustrator"><p class="number">カードナンバー：<span>hBP07-001</span></p></div>
</div>
"""


def _stage(effect: str) -> str:
    return WATAME.replace(
        "自分の〈角巻わため〉がアーツを使った時、自分のデッキの上から1枚をホロパワーにする。",
        effect,
    )


class TestOshiStageSkill:
    def test_is_extracted_alongside_the_oshi_skill(self):
        data = extract_structured_data(WATAME)

        stage = data["oshi_stage_skill"]
        assert stage["name"] == "ドドドライブ"
        assert stage["effect"].startswith("自分の〈角巻わため〉がアーツを使った時")
        assert "timing" not in stage
        assert data["oshi_skill"]["name"] == "角ドリルしたろか？"

    def test_a_timing_bracket_is_read_like_an_oshi_skill(self):
        """17 of the first 51 printings open with [ターンに1回]; it stays in `effect`."""
        data = extract_structured_data(_stage("[ターンに1回]自分のデッキを2枚引く。"))

        stage = data["oshi_stage_skill"]
        assert stage["timing"] == "ターンに1回"
        assert stage["effect"] == "[ターンに1回]自分のデッキを2枚引く。"


class TestUnknownSkillBlocks:
    def test_an_unread_skill_div_is_refused(self):
        """The guard that would have caught 推しステージスキル at the first hBP07 scrape."""
        html = WATAME.replace('class="stage skill"', 'class="ex skill"')

        with pytest.raises(UnknownSkillBlock, match=r"div\.ex\.skill.*推しステージスキル"):
            extract_structured_data(html)

    def test_a_card_with_no_skills_passes(self):
        html = '<div class="info"><dl><dt>カードタイプ</dt><dd>サポート・アイテム</dd></dl></div>'
        assert "oshi_stage_skill" not in extract_structured_data(html)
