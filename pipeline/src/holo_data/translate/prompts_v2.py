"""Per-kind translation prompts.

**Why the prompt changed at all.** `prompts.json` sends a whole card and asks for a whole
card back, with six bullet points covering every field at once. Two of those bullets are
about not translating names, and the model obeys them 47–81% of the time — which is
issues #20 and #21. Masking (Phase 2) removes the need for those bullets entirely: the
model never sees a name, so it cannot render one inconsistently.

What is left is the observation that the remaining instructions pull in different
directions. An art name is a title — punchy, tonal, often a pun. An effect is rules text —
precise, using the vocabulary that locale's players already read on other cards. A single
prompt asking for both gets a compromise, and the calibration run showed a per-kind prompt
does markedly better on labels: 12/12 clean where the old prompt leaves 47–81% of art
names in Japanese.

**The Chinese framing is kept deliberately.** v1's prompts are written in Traditional
Chinese, and that is a year of tuning about a Japanese card game read by a Chinese-speaking
maintainer. Rewriting them in English would be a silent change to translation quality
dressed up as a refactor, so the per-kind instructions extend that voice rather than
replace it.

**What was dropped, and why it is safe.** Every "do not translate the name" rule, because
masking makes it unnecessary. The `只翻譯 value` instruction, because it caused F-003 — on
four arts the model took it literally and emitted a sibling `value` key rather than
replacing the text. The whole-card JSON envelope, because a unit batch is a flat
`{id: text}` map with nothing to misinterpret.
"""

from __future__ import annotations

from .units import LABEL_KINDS, PROSE_KINDS, QA_KIND

# The language each locale is translated *into*, named as v1 named it.
LOCALE_NAMES = {
    "tc": "繁體中文",
    "en": "英文",
    "ko": "韓文",
    "id": "印尼文",
    "th": "泰文",
    "es": "西班牙文",
}

# Shared preamble. States the domain, the output contract, and the placeholder rule —
# the three things every batch needs regardless of kind.
_HEADER = """你是 hololive OFFICIAL CARD GAME（日文卡牌遊戲）的翻譯者。請將以下內容翻譯成{language}。

**輸出格式**
- 只回覆一個 JSON 物件，key 是輸入的 id，value 是翻譯結果。
- 不要加前言、說明或 ```json 標記。
- 每一項都必須翻譯，不可留下日文原文。

**佔位符規則（最重要）**
- `[[N0]]`、`[[N1]]` 這類標記是角色名稱的佔位符。
- 必須原封不動保留，不可翻譯、不可改寫、不可調換順序、不可刪除。
- 它們會在翻譯後由系統換回正確的角色名稱。
"""

# Per-kind instructions. Each says what the text *is*, because that is what tells the
# model how to translate it — a title and a rules sentence want different registers.
_KIND_RULES = {
    "card_name": """**這批是「卡片名稱」**
- 多為角色名、道具名或活動名，簡短。
- 保持專有名詞的官方寫法；若原文本身是英文或已是官方拼寫，直接沿用。""",
    "art_name": """**這批是「技能／插圖名稱」**
- 是印在卡片上的標題，不是句子。要短、要有力。
- 雙關語、招呼語、口頭禪要翻成同樣有趣的說法，不要直譯解釋。
- 保留語尾符號（～、！！、？）所帶的語氣。""",
    "keyword_name": """**這批是「關鍵字能力名稱」**
- 是印在卡片上的能力標題，簡短有力。
- 同上：雙關與口頭禪要保留趣味，不要直譯解釋。""",
    "skill_name": """**這批是「推し技能名稱」**
- 是必殺技等級的標題，通常誇張、帶氣勢。
- 英文圈習慣全大寫或標題式大小寫時可沿用原文氣勢。""",
    "skill_timing": """**這批是「使用時機」**
- 遊戲術語，如「ターンに1回」。
- 用該語言卡牌圈的標準說法，不要自創。""",
    "tag": """**這批是「標籤」**
- 分類用的短標籤，開頭有 `#`。
- 保留 `#` 開頭。世代名（0期生、1期生）用該語言圈的慣用譯法。""",
    "ability_text": """**這批是「卡片能力文字」**
- 規則文字，要精確。
- 遊戲專用語沿用該語言圈的既有習慣（如英文的 "Archive"、"Cheer"、"Baton Touch"）。
- 條件放後面、限制作為修飾語，貼合卡牌遊戲的閱讀習慣。""",
    "art_effect": """**這批是「技能效果文字」**
- 規則文字，要精確。忠於日文原意與細節，不要增減條件。
- 遊戲專用語沿用該語言圈的既有習慣。
- 條件放後面、限制作為修飾語。""",
    "keyword_effect": """**這批是「關鍵字能力效果」**
- 同技能效果：規則文字，精確優先。
- 遊戲專用語沿用該語言圈的既有習慣。""",
    "skill_effect": """**這批是「推し技能效果」**
- 同上：規則文字，精確優先，不要增減條件。""",
    "extra": """**這批是「補充說明」**
- 卡片上的附註文字，簡短。""",
    QA_KIND: """**這批是「官方問答」**
- 每一項是一個物件，含 title / question / answer。
- 回覆時保持同樣的物件結構，只翻譯文字內容。
- title 常是「Q680（2026.06.26）」這種格式，保留編號與日期。
- **question 與 answer 內可能含有 `[[N0]]` 這類佔位符，必須原封不動保留。**
- related_cards 是原始資料，原封不動保留，不要翻譯。
- 規則用語必須與卡片文字一致。""",
}

# Context block instructions, only added when a batch carries context.
_CONTEXT_NOTE = """
**參考資料**
- 部分項目附有 `context`（卡片名稱、技能名稱），僅供理解代名詞與指涉對象。
- `context` 本身不需要翻譯，也不要出現在回覆中。"""


def kind_rule(kind: str) -> str:
    """The instruction block for one field kind."""
    return _KIND_RULES.get(kind, _KIND_RULES["ability_text"])


def is_prose(kind: str) -> bool:
    return kind in PROSE_KINDS or kind == QA_KIND


def build_prompt(kind: str, locale: str, payload: str, with_context: bool) -> str:
    """Assemble the full prompt for one batch.

    Args:
        kind: the field kind every unit in this batch shares.
        locale: target locale code.
        payload: the JSON batch, already serialised.
        with_context: whether any unit carries a context block.
    """
    language = LOCALE_NAMES.get(locale, locale)
    parts = [
        _HEADER.format(language=language),
        kind_rule(kind),
    ]
    if with_context:
        parts.append(_CONTEXT_NOTE)
    parts.append(f"\n**輸入**\n```json\n{payload}\n```")
    return "\n".join(parts)


def target_locales() -> list[str]:
    return list(LOCALE_NAMES)


__all__ = [
    "LABEL_KINDS",
    "LOCALE_NAMES",
    "PROSE_KINDS",
    "QA_KIND",
    "build_prompt",
    "is_prose",
    "kind_rule",
    "target_locales",
]
