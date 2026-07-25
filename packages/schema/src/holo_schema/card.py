"""The canonical card contract.

This is the shape `holo-data build` writes to `cards.json`, the seeder reads, and D1
stores. It carries all 7 locales; the single-locale API shape is derived from it by
`localize()` — see `localized.py`.

Everything here was derived by census over v1's 2,448-card `data/cards.json`. Field
optionality reflects what the data actually contains: a field is `Optional` here only
where it is genuinely absent on some cards, and absent fields are *omitted* from JSON
rather than serialised as null (see `model_dump` usage in `scripts/generate.py`).

Naming is snake_case throughout, including in the JSON. v1's `cards.json` was camelCase
while its API and frontend were snake_case; unifying on one convention removes an alias
layer from every model and makes the API shape field-identical to v1's, so the Phase 5
frontend refactors do not have to touch a single field access.
"""

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .annotations import Blob, Column, Derived, FullText
from .enums import (
    BloomLevelCode,
    CardTypeCode,
    ColorCode,
    KeywordTypeCode,
    Locale,
    RarityCode,
    TimingCode,
)

# `extra="forbid"` everywhere is deliberate: an unrecognised key from the scraper is a
# signal that the source site changed, and we want that to fail loudly at build time
# rather than be silently dropped.
_STRICT = ConfigDict(extra="forbid")


class RelatedCards(BaseModel):
    """Cards referenced by a QA entry.

    `raw_html` is the official site's own markup, e.g. "[hBP08-003 ： FUWAMOCO]". It is
    kept because the rendered QA text links card numbers inline and reproducing that
    formatting from the parsed numbers alone would lose the display names.
    """

    model_config = _STRICT

    raw_html: str
    card_number: list[str] = Field(default_factory=list)


class QaItem(BaseModel):
    """One official Q&A entry attached to a card.

    Present on 5,992 of 17,136 card-locale pairs; 13,300 items in total.
    """

    model_config = _STRICT

    title: Annotated[str, FullText(weight=0.5)]
    question: Annotated[str, FullText(weight=0.5)]
    answer: Annotated[str, FullText(weight=0.5)]
    related_cards: Optional[RelatedCards] = None


class Art(BaseModel):
    """The language-independent half of an art: its costs and damage.

    The translated half (name, effect) lives in `Translation.arts` at the same index —
    see `TranslatedArt` for why they are stored apart and how they are paired.
    """

    model_config = _STRICT

    cost_count: int
    cost_types: list[ColorCode] = Field(default_factory=list)
    damage: Optional[int] = None
    is_plus: Optional[bool] = None
    special_targets: Optional[list[ColorCode]] = None
    # Ints in the data (only 30 and 50 occur). v1's worker.ts declared this
    # `special_values?: string[]`, which was wrong in both container and element type.
    special_values: Optional[list[int]] = None

    @model_validator(mode="after")
    def _special_pairs(self) -> "Art":
        """`special_targets` and `special_values` are positional pairs.

        Both appear on exactly 482 arts in v1's data and are read together ("+50 damage
        against white"), so a length mismatch means one side was dropped in parsing.
        """
        targets = self.special_targets
        values = self.special_values
        if (targets is None) != (values is None):
            raise ValueError(
                "special_targets and special_values must both be present or both absent"
            )
        if targets is not None and values is not None and len(targets) != len(values):
            raise ValueError(
                f"special_targets ({len(targets)}) and special_values ({len(values)}) "
                "must have equal length — they are positional pairs"
            )
        return self


class TranslatedArt(BaseModel):
    """The localised half of an art: what it is called and what it says.

    Paired with `Art` by list index. That pairing is fragile and the data proves it —
    hSD03-009 and hSD04-009 each have 2 entries in `Card.arts` but 0 in their `en`
    translation. `localize()` defines the merge rule and tolerates the short list; both
    cards are golden-file fixtures so the behaviour stays pinned.
    """

    model_config = _STRICT

    name: Annotated[str, FullText(weight=2.0)]
    effect: Annotated[Optional[str], FullText()] = None
    # Present on exactly 4 arts, all `tc`, all holding what looks like a translation of
    # `name` (e.g. name "おつルーナ" / value "辛苦啦露娜～"). Modelled so those 4 cards
    # validate; `localize()` ignores it. Phase 1 should decide whether the scraper
    # should be writing it at all.
    value: Optional[str] = None


class Keyword(BaseModel):
    """The language-independent half of a card's keyword ability."""

    model_config = _STRICT

    type: str
    type_code: KeywordTypeCode


class TranslatedKeyword(BaseModel):
    """The localised half of a card's keyword ability."""

    model_config = _STRICT

    name: Annotated[str, FullText()]
    effect: Annotated[str, FullText()]


class OshiSkill(BaseModel):
    """The language-independent half of an oshi skill.

    Only `timing_code` is language-independent. Note there is no `cost` field: v1's
    `types/card.ts`, `cloudflare/worker.ts` and `schema.sql` all declared one, but no
    card in the dataset has ever carried it. It was dead weight in three places.
    """

    model_config = _STRICT

    timing_code: TimingCode


class TranslatedOshiSkill(BaseModel):
    """The localised half of an oshi skill."""

    model_config = _STRICT

    name: Annotated[str, FullText(weight=1.5)]
    effect: Annotated[str, FullText()]
    # The human-readable rendering of `OshiSkill.timing_code` ("Once per turn").
    # Absent on ~7% of skills, where the official site omits it.
    timing: Optional[str] = None


class Translation(BaseModel):
    """Everything about a card that depends on the language it is read in.

    One of these per locale, for all 7 locales, on every card.

    Note `ability_text` and `extra` are mutually exclusive in the data (483 cards have
    `ability_text`, 2,639 card-locale pairs have `extra`, and zero have both). They are
    modelled as separate optional fields rather than one union because they mean
    different things: `ability_text` is a support card's rules text, `extra` is a
    supplementary note on a Holomem.
    """

    model_config = _STRICT

    name: Annotated[str, FullText(weight=3.0)]
    tags: Optional[list[str]] = None
    ability_text: Annotated[Optional[str], FullText()] = None
    extra: Annotated[Optional[str], FullText()] = None
    arts: Optional[list[TranslatedArt]] = None
    keyword: Optional[TranslatedKeyword] = None
    oshi_skill: Optional[TranslatedOshiSkill] = None
    sp_oshi_skill: Optional[TranslatedOshiSkill] = None
    qa_items: Optional[list[QaItem]] = None


class Card(BaseModel):
    """A single card, in every language.

    This is the canonical contract. Defined once here; the JSON Schema, the TypeScript
    `Card` type, and (in Phase 3) the D1 DDL are all generated from it.
    """

    model_config = _STRICT

    # --- Identity ---
    #
    # `id` is the scraper's own numeric-string id and is the only unique key.
    # `card_number` is NOT unique: 2,448 cards share 1,228 distinct numbers, because
    # rarity variants of the same card (hBP01-104 has 9) all carry one number. Any
    # lookup keyed on card_number returns a list — v1's /api/cards/by-card-numbers
    # endpoint already accounts for this.
    id: Annotated[str, Column(primary_key=True)]
    card_number: Annotated[str, Column(indexed=True), FullText(weight=2.0)]

    # --- Filterable attributes (real D1 columns per D8) ---
    card_type_code: Annotated[CardTypeCode, Column(indexed=True)]
    rarity_code: Annotated[RarityCode, Column(indexed=True)]
    # Absent on 419 cards, all support types — support cards have no colour.
    color_codes: Annotated[Optional[list[ColorCode]], Column(indexed=True, json_array=True)] = None
    # Absent on 733 cards — only Holomem cards bloom.
    bloom_level_code: Annotated[Optional[BloomLevelCode], Column(indexed=True)] = None

    # --- Images (decision D9) ---
    #
    # `image_key` is the CDN-agnostic identifier, e.g. "default/hBP01-028_C_02". The URL
    # is composed at render time by a `cardImage()` helper, so changing CDN host or
    # image format does not require touching a single database row. v1 stored
    # "card_images/default/hBP01-028_C_02.png" — folder layout and extension baked in.
    image_key: Annotated[str, Column()]
    # The official site's URL for this card's image. Retained as provenance: it is what
    # `holo-data publish` re-downloads from, and it disambiguates reprints (two cards
    # can share an image filename but never a source URL).
    source_image_url: Annotated[str, Column()]

    # --- Stats ---
    # Absent on the 733 non-Holomem cards.
    hp: Annotated[Optional[int], Column(sql_type="INTEGER")] = None
    # Present only on the 250 oshi cards.
    life: Annotated[Optional[int], Column(sql_type="INTEGER")] = None
    baton_touch_count: Annotated[Optional[int], Column(sql_type="INTEGER")] = None
    # Every value in the data is "null" (the colourless code) — the game does not yet
    # print a coloured baton touch cost. Typed as ColorCode anyway; it is the same
    # domain, and hardcoding Literal["null"] would break on the first coloured one.
    baton_touch_types: Annotated[Optional[list[ColorCode]], Column(json_array=True)] = None

    # --- Provenance ---
    illustrator: Annotated[Optional[str], Column(), FullText()] = None
    # Always present, never empty. Usually 1 set, but up to 17 for reprinted cards.
    card_sets: Annotated[list[str], Column(json_array=True)]

    # The card's tags in the source language, unprefixed: ["EN", "Promise", "歌"].
    # Distinct from `Translation.tags`, which holds the *localised* tag with a display
    # prefix ("#歌" -> "#노래"). Not a duplicate: 268 card-locale pairs translate the tag
    # text, and 236 cards have tags that vary across locales. This field is the stable
    # identity ("all cards tagged 食べ物"); Translation.tags is what gets displayed.
    tags: Annotated[Optional[list[str]], Column(json_array=True), FullText()] = None

    # --- Language-independent nested data ---
    arts: Annotated[Optional[list[Art]], Blob()] = None
    keyword: Annotated[Optional[Keyword], Blob()] = None
    oshi_skill: Annotated[Optional[OshiSkill], Blob()] = None
    sp_oshi_skill: Annotated[Optional[OshiSkill], Blob()] = None

    # --- Localised data ---
    #
    # Per D8 this is one JSON column, not 7 rows: ~48,700 rows collapse to ~2,500, and
    # adding an 8th locale costs zero extra rows.
    translations: Annotated[dict[Locale, Translation], Blob()]

    @field_validator("card_sets")
    @classmethod
    def _sets_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("card_sets must not be empty — every card belongs to a set")
        return v

    @model_validator(mode="after")
    def _source_locale_present(self) -> "Card":
        """The source language must always be present.

        Every other locale is translated from `ja`; a card without it cannot be
        re-translated or corrected.
        """
        from .enums import SOURCE_LOCALE

        if SOURCE_LOCALE not in self.translations:
            raise ValueError(
                f"card {self.id} is missing the source locale '{SOURCE_LOCALE}'"
            )
        return self

    def image_url(self, base_url: str, extension: str = "webp") -> str:
        """Compose this card's CDN URL (decision D9).

        The one place the key → URL mapping lives. v1 copy-pasted a `getImagePath()`
        helper verbatim across three components; per the architecture review that
        duplication is retired by having exactly one composer.

        Args:
            base_url: CDN origin, e.g. "https://img.hololive-ocg-wiki.tskrlabs.com".
            extension: image format. WebP only in production per D9 — PNG stays a
                local pipeline intermediate and is never uploaded.

        Returns:
            The full URL, e.g.
            "https://img.hololive-ocg-wiki.tskrlabs.com/default/hBP01-028_C_02.webp".
        """
        return f"{base_url.rstrip('/')}/{self.image_key}.{extension}"


class CardCollection(BaseModel):
    """The full published card set — the root shape of `cards.json`.

    A wrapper rather than a bare list so the artifact can carry provenance. v1's
    `cards.json` was a top-level array, which left no room to record which pipeline run
    produced it; `status.json` had to be consulted separately.
    """

    model_config = _STRICT

    # ISO-8601 UTC timestamp of the `holo-data build` run that produced this file.
    generated_at: str
    # Schema contract version. Bumped when the card shape changes in a way that would
    # break a consumer, so the seeder can refuse an artifact it does not understand.
    schema_version: int = 1
    cards: list[Card]

    @model_validator(mode="after")
    def _keys_unique(self) -> "CardCollection":
        """`id` and `image_key` must both be unique across the collection.

        The `image_key` check is the Phase 2 guard promised by D9. v1's data has two
        genuine collisions — hBP03-044_SR and hBP03-055_SR each map to two different
        card ids, because hCO01 reprints reuse the original set's image filename. Under
        D9 those pairs would silently overwrite each other in R2. Failing here means
        Phase 2 cannot ship that bug: a colliding pair must be given distinct keys
        (e.g. by including the source set) before `publish` will run.
        """
        seen_ids: set[str] = set()
        dupe_ids: set[str] = set()
        for card in self.cards:
            if card.id in seen_ids:
                dupe_ids.add(card.id)
            seen_ids.add(card.id)
        if dupe_ids:
            raise ValueError(f"duplicate card ids: {sorted(dupe_ids)}")

        by_key: dict[str, list[str]] = {}
        for card in self.cards:
            by_key.setdefault(card.image_key, []).append(card.id)
        collisions = {k: v for k, v in by_key.items() if len(v) > 1}
        if collisions:
            detail = "; ".join(
                f"{key} <- card ids {ids}" for key, ids in sorted(collisions.items())
            )
            raise ValueError(
                f"duplicate image_key across {len(collisions)} key(s): {detail}. "
                "Each card needs its own R2 object; give reprints a distinct key."
            )
        return self
