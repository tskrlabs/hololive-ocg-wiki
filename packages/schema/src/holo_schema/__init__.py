"""The card contract for hololive-ocg-wiki.

Defined once here as pydantic models. The JSON Schema, the TypeScript types, and (from
Phase 3) the D1 DDL are all generated from these — see `scripts/generate.py`.

    from holo_schema import Card, CardCollection, localize

    collection = CardCollection.model_validate_json(raw)
    card = collection.cards[0]
    api_shape = localize(card, "en")
"""

from .annotations import Blob, Column, Derived, FullText
from .card import (
    Art,
    Card,
    CardCollection,
    Keyword,
    OshiSkill,
    QaItem,
    RelatedCards,
    TranslatedArt,
    TranslatedKeyword,
    TranslatedOshiSkill,
    Translation,
)
from .enums import (
    BLOOM_LEVEL_VALUES,
    CARD_TYPE_VALUES,
    COLOR_VALUES,
    DEFAULT_LOCALE,
    FUSED_COLORS,
    KEYWORD_TYPE_VALUES,
    LOCALE_VALUES,
    MAIN_CARD_TYPES,
    OSHI_CARD_TYPES,
    RARITY_VALUES,
    SOURCE_LOCALE,
    TIMING_VALUES,
    YELL_CARD_TYPES,
    BloomLevelCode,
    CardTypeCode,
    ColorCode,
    KeywordTypeCode,
    Locale,
    RarityCode,
    TimingCode,
)
from .localize import localize
from .localized import (
    LocalizedArt,
    LocalizedCard,
    LocalizedKeyword,
    LocalizedOshiSkill,
)

SCHEMA_VERSION = 1
"""Bumped when the card shape changes in a way that breaks a consumer."""

__all__ = [
    # Canonical models
    "Art",
    "Card",
    "CardCollection",
    "Keyword",
    "OshiSkill",
    "QaItem",
    "RelatedCards",
    "TranslatedArt",
    "TranslatedKeyword",
    "TranslatedOshiSkill",
    "Translation",
    # API projection
    "LocalizedArt",
    "LocalizedCard",
    "LocalizedKeyword",
    "LocalizedOshiSkill",
    "localize",
    # Enum types
    "BloomLevelCode",
    "CardTypeCode",
    "ColorCode",
    "KeywordTypeCode",
    "Locale",
    "RarityCode",
    "TimingCode",
    # Enum values
    "BLOOM_LEVEL_VALUES",
    "CARD_TYPE_VALUES",
    "COLOR_VALUES",
    "KEYWORD_TYPE_VALUES",
    "LOCALE_VALUES",
    "RARITY_VALUES",
    "TIMING_VALUES",
    # Domain constants
    "DEFAULT_LOCALE",
    "FUSED_COLORS",
    "MAIN_CARD_TYPES",
    "OSHI_CARD_TYPES",
    "SOURCE_LOCALE",
    "YELL_CARD_TYPES",
    # Storage annotations
    "Blob",
    "Column",
    "Derived",
    "FullText",
    "SCHEMA_VERSION",
]
