"""Closed enums for the card contract.

Every member here was derived from v1's 2,448-card `data/cards.json` by census, not
from v1's TypeScript. Where the two disagreed, the data won — see the notes below.

These are `Literal` unions rather than `enum.Enum` so that pydantic emits a plain
JSON Schema `enum` (which `json-schema-to-typescript` renders as a TS string union)
instead of a `$ref` to a named definition with a wrapper object.

The `*_VALUES` tuples are the runtime counterpart. They are exported to TypeScript by
`scripts/generate.py` so the frontend can iterate them for filter UIs. v1 kept a
hand-written copy in `constants/card-data.ts` that had drifted from the data in two
ways (see `BLOOM_LEVEL_VALUES` and `RARITY_VALUES`); that file is deleted in Phase 5.
"""

from typing import Literal, get_args

# --- Locales -----------------------------------------------------------------
#
# All 7 locales are present on all 2,448 cards. `ja` is the source language: it is the
# only locale without a `_source_hash`, because it is scraped rather than translated.

Locale = Literal["ja", "en", "tc", "id", "ko", "th", "es"]

LOCALE_VALUES: tuple[Locale, ...] = get_args(Locale)

SOURCE_LOCALE: Locale = "ja"
"""The language cards are scraped in. Every other locale is translated from it."""

DEFAULT_LOCALE: Locale = "tc"
"""The site's default locale. Matches v1's `DEFAULT_LOCALE` in worker.ts."""


# --- Card type ---------------------------------------------------------------
#
# 13 distinct values across 2,448 cards. v1's `types/card.ts` listed only 12 — it was
# missing "unknown", which the scraper writes when it cannot classify a card. Two
# cards carry it today (both hBP07-091, a "Live Staff" card). It is a legitimate,
# documented member: the scraper degrading gracefully is better than it crashing, and
# modelling it means `holo-data build` does not fail on cards we already ship.

CardTypeCode = Literal[
    "buzzCharacter",
    "character",
    "oshiCharacter",
    "supportCheer",
    "supportEvent",
    "supportEventLimited",
    "supportFan",
    "supportItem",
    "supportItemLimited",
    "supportMascot",
    "supportStaffLimited",
    "supportTool",
    "unknown",
]

CARD_TYPE_VALUES: tuple[CardTypeCode, ...] = get_args(CardTypeCode)


# --- Deck sections -----------------------------------------------------------
#
# Which card types go in which deck section. v1 kept these as CARD_TYPE_OSHI /
# CARD_TYPE_MAIN / CARD_TYPE_YELL in constants/card-data.ts. They live here so the
# deck rules derive from the same enum as everything else (see architecture review
# Candidate 03, Phase 5).
#
# Note "unknown" is deliberately absent from all three: an unclassified card cannot be
# routed to a section, and silently dropping it into MAIN would be a guess.

OSHI_CARD_TYPES: tuple[CardTypeCode, ...] = ("oshiCharacter",)

YELL_CARD_TYPES: tuple[CardTypeCode, ...] = ("supportCheer",)

MAIN_CARD_TYPES: tuple[CardTypeCode, ...] = (
    "buzzCharacter",
    "character",
    "supportEvent",
    "supportEventLimited",
    "supportFan",
    "supportItem",
    "supportItemLimited",
    "supportMascot",
    "supportStaffLimited",
    "supportTool",
)


# --- Rarity ------------------------------------------------------------------
#
# 14 distinct values. v1's `types/card.ts` and `constants/card-data.ts` both listed 13
# — both were missing "HR", which 24 cards use. Because the frontend built its rarity
# filter from that constant, those 24 cards were unfilterable in the live UI.

RarityCode = Literal[
    "C",
    "HR",
    "OC",
    "OSR",
    "OUR",
    "P",
    "R",
    "RR",
    "S",
    "SEC",
    "SR",
    "SY",
    "U",
    "UR",
]

RARITY_VALUES: tuple[RarityCode, ...] = get_args(RarityCode)


# --- Colour ------------------------------------------------------------------
#
# 9 distinct values. `blue_red` and `white_green` are *fused dual-colour symbols* as
# printed on the card, not shorthand for a two-element array — the game renders each
# as a single icon (public/icons/type_blue_red.webp is a distinct 4.2 KB asset, vs
# ~20 KB for each single-colour icon).
#
# This matters because the data contains BOTH `["blue_red"]` (5 FUWAMOCO cards) and
# `["red", "blue"]` (3 miComet cards). They are different things: one card bears one
# fused symbol, the other bears two separate symbols. Normalising the fused codes into
# arrays would render two icons and a comma where the card shows one icon.
#
# Consequence for Phase 4: a "red" filter must also match fused codes containing red.
# That is a query-layer rule, deliberately not a contract-layer one.
#
# "null" is the game's colourless concept (無色 / "None"), a real domain value — not a
# serialisation accident. i18n/locales/*.json:100 translates it in all 7 languages.

ColorCode = Literal[
    "blue",
    "blue_red",
    "green",
    "null",
    "purple",
    "red",
    "white",
    "white_green",
    "yellow",
]

COLOR_VALUES: tuple[ColorCode, ...] = get_args(ColorCode)

FUSED_COLORS: dict[ColorCode, tuple[ColorCode, ...]] = {
    "blue_red": ("blue", "red"),
    "white_green": ("white", "green"),
}
"""Fused colour symbols and the colours they contain.

For Phase 4 filtering only — a card with `["blue_red"]` should match a "blue" filter.
This is NOT a normalisation table: the fused code stays as-is in the card data.
"""


# --- Bloom level -------------------------------------------------------------
#
# 4 distinct values (plus absent, on 733 non-Holomem cards).
#
# v1's `constants/card-data.ts:60` said ["debut", "1st", "2nd", "spot"] while the data
# and `types/card.ts` said debut/first/second/spot. The two spellings coexisted only
# because the enum was written twice; the frontend's bloom filter was built from the
# wrong one. The data's spelling is authoritative.

BloomLevelCode = Literal["debut", "first", "second", "spot"]

BLOOM_LEVEL_VALUES: tuple[BloomLevelCode, ...] = get_args(BloomLevelCode)


# --- Keyword type ------------------------------------------------------------
#
# 3 distinct values, on 1,124 cards.

KeywordTypeCode = Literal["bloom_effect", "collab_effect", "gift"]

KEYWORD_TYPE_VALUES: tuple[KeywordTypeCode, ...] = get_args(KeywordTypeCode)


# --- Skill timing ------------------------------------------------------------
#
# In today's data this is perfectly correlated with the skill kind: every one of the
# 250 oshi skills is `once_per_turn` and every one of the 230 SP oshi skills is
# `once_per_game`. The field is modelled as a real enum rather than derived from the
# kind, because that correlation is a fact about the current card pool, not a rule of
# the game.

TimingCode = Literal["once_per_game", "once_per_turn"]

TIMING_VALUES: tuple[TimingCode, ...] = get_args(TimingCode)
