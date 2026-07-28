"""Japanese source values → the contract's codes.

Ported from v1's `4-to-i18n.py`. These tables are the translation between what the
official site prints and what `packages/schema` defines, and they must stay exact — a
wrong entry silently produces `unknown` for a whole class of cards.

Note `BLOOM_LEVEL` maps `1st`/`2nd` to `first`/`second`. v1's frontend kept a *separate*
hand-written list using `1st`/`2nd` (`constants/card-data.ts:60`), which is why the
bloom filter was built from the wrong spelling — see ADR 0001. This table is the correct
one, and the frontend now derives its list from the generated enums instead.
"""

from __future__ import annotations

CARD_TYPE: dict[str, str] = {
    "ホロメン": "character",
    "Buzzホロメン": "buzzCharacter",
    "推しホロメン": "oshiCharacter",
    "サポート・イベント": "supportEvent",
    "サポート・イベント・LIMITED": "supportEventLimited",
    "サポート・アイテム": "supportItem",
    "サポート・アイテム・LIMITED": "supportItemLimited",
    "サポート・ファン": "supportFan",
    "サポート・ツール": "supportTool",
    "サポート・ロケーション": "supportLocation",
    "エール": "supportCheer",
    "サポート・マスコット": "supportMascot",
    "サポート・スタッフ": "supportStaff",
    "サポート・スタッフ・LIMITED": "supportStaffLimited",
    "サポート": "rulesNotice",
}
"""Card type. Unmapped values become `unknown` — a documented, legitimate code.

`サポート・スタッフ` was missing here until Phase 1, which is why hBP07-091 (ライブスタッフ,
2 cards) shows as `unknown` in v1's live data. See docs/findings.md F-001.

Note `サポート・ロケーション` maps to a code the contract's enum does not accept. That is
deliberate: no card has ever used it, so a card that did would be a genuinely new type
and should fail `build` loudly rather than validate silently.

`サポート` — the bare type, with no subtype — was in that same category until the
2,464-card refresh, when it turned up on id 2459 (デッキ構築ルール): a Selection Cup
format-legality notice the official site publishes *into* the card list. It maps to
`rulesNotice` now.

That mapping is an inference — the type alone does not prove a thing is a notice — and
it is safe only because the contract checks the other half. `Card._card_fields_present`
rejects a `rulesNotice` that carries a `card_number`, so if the site ever prints a real
bare-`サポート` *card*, it fails `build` loudly exactly as before. The classification is
one signal; the validator is what keeps a wrong guess from shipping."""

COLOR: dict[str, str] = {
    "白": "white",
    "赤": "red",
    "青": "blue",
    "緑": "green",
    "黄": "yellow",
    "紫": "purple",
    "白緑": "white_green",
    "青赤": "blue_red",
    "◇": "null",
}
"""Colour. `白緑` and `青赤` are **fused dual-colour symbols** printed as a single icon —
not shorthand for two colours. `◇` is the game's colourless concept. See ADR 0001."""

BLOOM_LEVEL: dict[str, str] = {
    "Debut": "debut",
    "1st": "first",
    "2nd": "second",
    "Spot": "spot",
}

TIMING: dict[str, str] = {
    "ターンに1回": "once_per_turn",
    "ゲームに1回": "once_per_game",
}
"""Oshi skill timing, extracted from the `[ターンに1回]` marker in the skill text."""

KEYWORD_TYPE: dict[str, str] = {
    "コラボエフェクト": "collab_effect",
    "ブルームエフェクト": "bloom_effect",
    "ギフト": "gift",
}

# Field labels as they appear in the site's <dt> elements. Lists because the site has
# used more than one label for the same field over time.
LABELS: dict[str, list[str]] = {
    "card_type": ["カードタイプ", "Card Type"],
    "color": ["色", "Color"],
    "bloom_level": ["Bloomレベル", "Bloom Level"],
    "hp": ["HP"],
    "life": ["LIFE"],
    "tags": ["タグ", "Tags"],
    "rarity": ["レアリティ", "Rarity"],
    "illustrator": ["イラストレーター", "Illustrator", "illustrator"],
    "ability_text": ["能力テキスト", "Ability Text", "ability_text"],
    "extra": ["エクストラ", "Extra", "extra"],
    "baton_touch": ["バトンタッチ", "Baton Touch"],
    "arts": ["アーツ", "Arts", "arts"],
    "card_number": ["カードナンバー", "Card Number", "card_number"],
}
