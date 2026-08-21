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


MAX_BATCH = 50
"""Most ids or card numbers one batch request may carry.

A shared API constraint, so it lives in the contract rather than on one side of it. The
Worker rejects an over-cap request with 400 (v1 sliced to the first 50 and said nothing,
so a deck longer than 50 cards rendered short with no error); the site chunks its
requests to fit. Those two numbers must agree, and a legal deck already exceeds this —
1 oshi + 50 main + 20 yell is 71 cards — so the disagreement would be reached in normal
use, not at some edge.
"""


# --- Card type ---------------------------------------------------------------
#
# 13 distinct values across 2,448 cards, plus `supportStaff` (see below). v1's
# `types/card.ts` listed only 12.
#
# `supportStaff` was added in Phase 1. The two cards that carried "unknown" in v1's live
# data (both hBP07-091, ライブスタッフ / "Live Staff") are `サポート・スタッフ` — a real
# card type that was simply missing from the pipeline's mapping table, so it fell through
# to the placeholder. See docs/archive/findings.md F-001.
#
# **"unknown" is deliberately NOT a member**, as of issue #19. It was one until then, on
# the reasoning that a scraper degrading gracefully beats it crashing — but the pipeline
# writes it as the fallback at eight sites across four enums, and this was the only enum
# that accepted it. So the same event, the site printing a value we have no mapping for,
# stopped the build in three fields and shipped silently in the fourth. The absorbing
# card was then excluded from every deck section (see the deck sections below) with
# nothing counting, printing or alerting on it: not merely unmonitored but silent, with
# no baseline anyone would notice moving.
#
# That is F-001's own shape. Those two ライブスタッフ cards sat in v1's live database as
# `unknown` from the day they shipped and were found by a census run by hand during the
# v2 port, not by anything the pipeline said.
#
# Graceful degradation is still available, but it is now a thing the operator chooses
# rather than a thing that happens quietly: `holo-data transform` names the source value
# the site printed, and `build --allow-unknown-enums` ships the rest without it. That
# artifact records what it dropped and `publish`/`seed` refuse it, so the escape hatch
# unblocks `build` alone and never reaches the site.
#
# `support` and `supportLocation` are NOT members for a related reason: the pipeline can
# emit them but no card has ever used them, so admitting them would mean shipping enum
# values with no evidence behind them. If a Location card ever appears, `build` fails
# loudly — which is now what happens for *any* unrecognised type, not just that one.
#
# `rulesNotice` was added by the 2,464-card data refresh, and it is not a card. The
# official site publishes format-legality notices *into the card list*: id 2459
# (デッキ構築ルール, `sele08/sele08_teaching`) states which products are legal for the
# Selection Cup and how card-number matching works. It has a card's envelope — id, name,
# image, card_sets, ability text — but no card number and no rarity, and its raw type is
# the bare `サポート` the paragraph above says must fail loudly. It did fail loudly,
# which is how it was found.
#
# It is modelled rather than excluded because it is the *legend* for a field we already
# store: the same update added 「【使用可能カード】セレクションカップ」 to ~660 existing
# cards' `card_sets`, and this notice is the only place the site explains what that
# means. A deck simulator needs exactly this record to answer "is this deck legal for
# this format?". See docs/archive/findings.md F-020.

CardTypeCode = Literal[
    "buzzCharacter",
    "character",
    "oshiCharacter",
    "rulesNotice",
    "supportCheer",
    "supportEvent",
    "supportEventLimited",
    "supportFan",
    "supportItem",
    "supportItemLimited",
    "supportMascot",
    "supportStaff",
    "supportStaffLimited",
    "supportTool",
]

CARD_TYPE_VALUES: tuple[CardTypeCode, ...] = get_args(CardTypeCode)

# Types that are not playable cards. Named rather than compared inline so every
# consumer asks one question — the deck sections below, counts, and any future
# format-legality check. A rules notice is *correctly classified* as a non-card, which
# is what distinguishes it from a card we failed to classify — and the latter no longer
# reaches the contract at all (#19).
NON_CARD_TYPES: tuple[CardTypeCode, ...] = ("rulesNotice",)


# --- Deck sections -----------------------------------------------------------
#
# Which card types go in which deck section. v1 kept these as CARD_TYPE_OSHI /
# CARD_TYPE_MAIN / CARD_TYPE_YELL in constants/card-data.ts. They live here so the
# deck rules derive from the same enum as everything else (see architecture review
# Candidate 03, Phase 5).
#
# `rulesNotice` is deliberately absent from all three: it is not a card at all
# (NON_CARD_TYPES), so no section can ever hold it. Leaving it out here is what makes the
# deck builder structurally unable to add it, rather than relying on every consumer to
# filter.
#
# "unknown" used to be absent for a weaker version of the same reason — an unclassified
# card cannot be routed, and dropping it into MAIN would be a guess. That is now moot:
# the value is not in the enum, so such a card never reaches the site to be routed (#19).
# This left `rulesNotice` as the only type in no section, which is why the deck tests
# exercise the null path with it.

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
    "supportStaff",
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
# 7 distinct values. A dual-colour card carries two of them, in printed order.
#
# **The source spells dual-colour two different ways, and they mean the same thing.**
# FUWAMOCO and SorAZ get one <img alt="青赤"> of a pre-composited pair; miComet gets two
# separate <img> tags. F-007 checked all three against the card images: every one prints
# the same form, two separate badges on a gold ribbon. So the split is an artifact of the
# source HTML, not a fact about the game, and `transform` normalises `青赤` to
# `["blue", "red"]` at the point of extraction — the one place that difference exists.
#
# ADR 0013 made that change. Until then `blue_red` and `white_green` were their own enum
# values, which cost a query-layer expansion (a "blue" filter had to also match
# `blue_red`, F-016), a filter-UI exclusion list, and a low-resolution icon the official
# site exports at 88x110 against 330x410 for every other colour (#22). Normalising
# retired all three at once.
#
# **A file size was mistaken for evidence.** F-007 and this comment both once cited
# `type_blue_red.png`'s 4.2 KB as proof that `blue_red` was a fused *single* symbol. It
# was not: `white_green` is equally "fused" and is full-size, and the 88px asset is
# itself a picture of two badges. An upstream export mistake shaped the contract's
# reading of the domain for two phases. See F-023 / #22.
#
# "null" is the game's colourless concept (無色 / "None"), a real domain value — not a
# serialisation accident. i18n/locales/*.json translates it in all 7 languages.

ColorCode = Literal[
    "blue",
    "green",
    "null",
    "purple",
    "red",
    "white",
    "yellow",
]

COLOR_VALUES: tuple[ColorCode, ...] = get_args(ColorCode)

COLOR_PAIRS: dict[tuple[ColorCode, ...], str] = {
    ("blue", "red"): "blue_red",
    ("red", "blue"): "blue_red",
    ("white", "green"): "white_green",
    ("green", "white"): "white_green",
}
"""The dual-colour pairs that have a name of their own, for **display only**.

`青赤` is a colour identity the game names, and a card bearing it should read "Blue-Red"
rather than "Blue, Red" — so the name survives even though the storage no longer does.
The i18n key is `colors.{name}`, unchanged from when these were enum values.

Both orders map to one name deliberately. The badges are printed blue-then-red on
FUWAMOCO and red-then-blue on miComet, and the pair is the same identity either way —
but the *stored* order is the printed order, because that is what the icons render from.
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
