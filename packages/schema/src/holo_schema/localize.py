"""The projection: `Card` (all locales) -> `LocalizedCard` (one locale).

**This is the reference implementation.** A TypeScript port lives in
`packages/schema/src/localize.ts` because the Worker must run this projection at
request time (D8 stores translations as JSON, so the flattening happens on read, and
the Worker is TypeScript).

Two implementations, one spec. `tests/test_localize.py` writes golden files from this
one; `tests/localize.test.ts` asserts the TypeScript reproduces them exactly. If the
two ever disagree, `make check` fails.

The merge rules, all of which the data forced:

1. **Locale fallback.** A missing locale falls back to the source locale (`ja`) rather
   than returning nothing. All 7 locales are present on all cards today, so this never
   fires — but an 8th locale is added translation-by-translation, and a half-translated
   card should render in Japanese rather than 404.

2. **Arts pair by index, tolerating a short list.** hSD03-009 and hSD04-009 had 2 arts
   but 0 `en` translations. The art is emitted with costs and damage and no name, since
   dropping it would misreport what the card does. F-004 resolved itself and no real
   card has a short list any more — a census over all 2,463 finds zero mismatches in any
   locale — so the **synthetic fixture `9000001` is the only thing covering this
   branch**, in both implementations. Deleting it silently untests a rule that ships.
   See SYNTHETIC_CARD in `scripts/build_fixtures.py`.

3. **Excess translated arts are dropped.** The inverse case does not occur in today's
   data. An art with a name but no cost is not a valid art, so there is nothing
   meaningful to emit.

4. **Absent list fields become empty lists.** `Card` distinguishes "no tags" (absent)
   from "empty tags"; the API does not, because every consumer does `v-if="tags.length"`
   and an optional array just moves the null check into the frontend.
"""

from .card import Card
from .enums import SOURCE_LOCALE, Locale
from .localized import (
    LocalizedArt,
    LocalizedCard,
    LocalizedKeyword,
    LocalizedOshiSkill,
)


def localize(card: Card, locale: Locale) -> LocalizedCard:
    """Project a canonical `Card` into the API's single-locale shape.

    Args:
        card: the canonical card, carrying all locales.
        locale: the language to project into. Falls back to the source locale if the
            card has no translation for it.

    Returns:
        The card as the API serves it, with translation fields flattened to the top
        level and nested data merged.

    Raises:
        ValueError: if the card has neither the requested locale nor the source locale.
            `Card`'s validator makes this unreachable for validated cards.
    """
    translation = card.translations.get(locale)
    resolved: Locale = locale

    if translation is None:
        translation = card.translations.get(SOURCE_LOCALE)
        resolved = SOURCE_LOCALE

    if translation is None:
        raise ValueError(
            f"card {card.id} has no translation for '{locale}' and no "
            f"'{SOURCE_LOCALE}' fallback"
        )

    # --- Arts: zip the language-independent half with the translated half by index ---
    base_arts = card.arts or []
    translated_arts = translation.arts or []
    arts: list[LocalizedArt] = []
    for index, base in enumerate(base_arts):
        translated = translated_arts[index] if index < len(translated_arts) else None
        arts.append(
            LocalizedArt(
                cost_types=base.cost_types,
                damage=base.damage,
                is_plus=base.is_plus,
                special_targets=base.special_targets,
                special_values=base.special_values,
                name=translated.name if translated else None,
                effect=translated.effect if translated else None,
            )
        )

    # --- Keyword: type code from the card, display text from the translation ---
    keyword = None
    if card.keyword is not None:
        keyword = LocalizedKeyword(
            type=card.keyword.type,
            type_code=card.keyword.type_code,
            name=translation.keyword.name if translation.keyword else None,
            effect=translation.keyword.effect if translation.keyword else None,
        )

    # --- Oshi skills: timing code from the card, display text from the translation ---
    oshi_skill = None
    if card.oshi_skill is not None:
        oshi_skill = LocalizedOshiSkill(
            timing_code=card.oshi_skill.timing_code,
            name=translation.oshi_skill.name if translation.oshi_skill else None,
            effect=translation.oshi_skill.effect if translation.oshi_skill else None,
            timing=translation.oshi_skill.timing if translation.oshi_skill else None,
        )

    sp_oshi_skill = None
    if card.sp_oshi_skill is not None:
        sp_oshi_skill = LocalizedOshiSkill(
            timing_code=card.sp_oshi_skill.timing_code,
            name=translation.sp_oshi_skill.name if translation.sp_oshi_skill else None,
            effect=(
                translation.sp_oshi_skill.effect if translation.sp_oshi_skill else None
            ),
            timing=translation.sp_oshi_skill.timing if translation.sp_oshi_skill else None,
        )

    return LocalizedCard(
        id=card.id,
        card_number=card.card_number,
        locale=resolved,
        card_type_code=card.card_type_code,
        rarity_code=card.rarity_code,
        color_codes=card.color_codes or [],
        bloom_level_code=card.bloom_level_code,
        image_key=card.image_key,
        hp=card.hp,
        life=card.life,
        baton_touch_count=card.baton_touch_count,
        baton_touch_types=card.baton_touch_types or [],
        illustrator=card.illustrator,
        card_sets=card.card_sets,
        name=translation.name,
        tags=translation.tags or [],
        ability_text=translation.ability_text,
        extra=translation.extra,
        arts=arts,
        keyword=keyword,
        oshi_skill=oshi_skill,
        sp_oshi_skill=sp_oshi_skill,
        qa_items=translation.qa_items or [],
    )
