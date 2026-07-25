"""The API response shape — one card, one locale, flattened.

This is a *projection* of `Card`, not an independent contract. It exists because the
API serves one language at a time: sending all 7 translations to render one would be
roughly 7x the payload for no benefit.

The projection is defined once, in `localize.py`. v1 had it hand-written inside
`enrichCardDataBatch` (worker.ts:266) as a set of SQL joins with no shared definition,
which is how the API and the frontend types drifted apart.

Field names here match v1's `types/card.ts` exactly where the field still exists, so
the Phase 5 frontend refactors do not have to touch field accesses. The differences are
all cases where v1 was wrong or the field is gone — documented per-field below.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict

from .card import QaItem
from .enums import (
    BloomLevelCode,
    CardTypeCode,
    ColorCode,
    KeywordTypeCode,
    Locale,
    RarityCode,
    TimingCode,
)

_STRICT = ConfigDict(extra="forbid")


class LocalizedArt(BaseModel):
    """An art with its costs and its translated text merged into one object.

    In `Card` these are two parallel lists (`Card.arts` and `Translation.arts`) paired
    by index. Merging them is the main job `localize()` does.
    """

    model_config = _STRICT

    cost_count: int
    cost_types: list[ColorCode] = []
    damage: Optional[int] = None
    is_plus: Optional[bool] = None
    special_targets: Optional[list[ColorCode]] = None
    special_values: Optional[list[int]] = None
    # Absent when the locale has fewer translated arts than the card has arts —
    # hSD03-009 and hSD04-009 in `en`. The art is still returned with its costs and
    # damage, just unnamed, because dropping it would misreport the card's abilities.
    name: Optional[str] = None
    effect: Optional[str] = None


class LocalizedKeyword(BaseModel):
    """A keyword with its type and translated text merged."""

    model_config = _STRICT

    type: str
    type_code: KeywordTypeCode
    name: Optional[str] = None
    effect: Optional[str] = None


class LocalizedOshiSkill(BaseModel):
    """An oshi skill with its timing and translated text merged.

    No `cost` field — v1 declared one in three places and no card ever had it.
    """

    model_config = _STRICT

    timing_code: TimingCode
    name: Optional[str] = None
    effect: Optional[str] = None
    timing: Optional[str] = None


class LocalizedCard(BaseModel):
    """A card as the API returns it: one locale, translations flattened to the top.

    Differences from v1's `types/card.ts`, all deliberate:

    - `image_path` / `image_url` are replaced by `image_key` (D9). The frontend composes
      the URL with a `cardImage()` helper instead of reading a baked-in path.
    - `card_type` / `color` / `rarity` / `set_name` are gone. v1 carried these as
      translated display strings alongside their codes, but the frontend renders the
      codes through i18n (`$t('cardTypes.' + item.card_type_code)`) and never read them.
    - `qaItems` is gone; it was a camelCase duplicate of `qa_items` in the same type.
    - `locale` is new: the response says which language it is in, so a cached response
      cannot be mistaken for another locale's.
    """

    model_config = _STRICT

    # --- Identity and provenance ---
    id: str
    card_number: str
    locale: Locale

    # --- Codes ---
    card_type_code: CardTypeCode
    rarity_code: RarityCode
    color_codes: list[ColorCode] = []
    bloom_level_code: Optional[BloomLevelCode] = None

    # --- Image (D9) ---
    image_key: str

    # --- Stats ---
    hp: Optional[int] = None
    life: Optional[int] = None
    baton_touch_count: Optional[int] = None
    baton_touch_types: list[ColorCode] = []

    # --- Provenance ---
    illustrator: Optional[str] = None
    card_sets: list[str] = []

    # --- Flattened translation fields ---
    name: Optional[str] = None
    tags: list[str] = []
    ability_text: Optional[str] = None
    extra: Optional[str] = None

    # --- Merged nested data ---
    arts: list[LocalizedArt] = []
    keyword: Optional[LocalizedKeyword] = None
    oshi_skill: Optional[LocalizedOshiSkill] = None
    sp_oshi_skill: Optional[LocalizedOshiSkill] = None
    qa_items: list[QaItem] = []
