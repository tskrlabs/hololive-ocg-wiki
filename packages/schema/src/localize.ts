/**
 * The projection: `Card` (all locales) -> `LocalizedCard` (one locale).
 *
 * **Port of `src/holo_schema/localize.py`.** That file is the reference implementation
 * and carries the full reasoning for each merge rule; this is the copy the Worker runs,
 * because D8 stores translations as JSON and the flattening therefore happens on read,
 * inside the Worker, in TypeScript.
 *
 * Two implementations, one spec. `tests/localize.test.ts` asserts this reproduces the
 * golden files that the Python side generates. If they diverge, `make check` fails.
 *
 * When editing this file, edit `localize.py` in the same commit.
 */

import type { Card } from "../dist/card.d.ts";
import type { LocalizedCard, LocalizedArt } from "../dist/localized-card.d.ts";
import { SOURCE_LOCALE, type Locale } from "../dist/enums.ts";

/**
 * Project a canonical card into the API's single-locale shape.
 *
 * @param card - the canonical card, carrying all locales.
 * @param locale - the language to project into. Falls back to the source locale if the
 *   card has no translation for it.
 * @returns the card as the API serves it, with translation fields flattened.
 * @throws if the card has neither the requested locale nor the source locale.
 */
export function localize(card: Card, locale: Locale): LocalizedCard {
  const translations = card.translations as Record<string, Card["translations"][string]>;

  let translation = translations[locale];
  let resolved: Locale = locale;

  if (translation === undefined) {
    translation = translations[SOURCE_LOCALE];
    resolved = SOURCE_LOCALE;
  }

  if (translation === undefined) {
    throw new Error(
      `card ${card.id} has no translation for '${locale}' and no '${SOURCE_LOCALE}' fallback`,
    );
  }

  // --- Arts: zip the language-independent half with the translated half by index ---
  //
  // The translated list may be shorter (hSD03-009 and hSD04-009 have 2 arts but 0 `en`
  // translations). Emit the art anyway, unnamed — dropping it would misreport the card.
  const baseArts = card.arts ?? [];
  const translatedArts = translation.arts ?? [];
  const arts: LocalizedArt[] = baseArts.map((base, index) => {
    const translated = translatedArts[index];
    return {
      cost_count: base.cost_count,
      cost_types: base.cost_types ?? [],
      ...(base.damage !== undefined && { damage: base.damage }),
      ...(base.is_plus !== undefined && { is_plus: base.is_plus }),
      ...(base.special_targets !== undefined && { special_targets: base.special_targets }),
      ...(base.special_values !== undefined && { special_values: base.special_values }),
      ...(translated?.name !== undefined && { name: translated.name }),
      ...(translated?.effect !== undefined && { effect: translated.effect }),
    };
  });

  // --- Keyword: type code from the card, display text from the translation ---
  const keyword = card.keyword
    ? {
        type: card.keyword.type,
        type_code: card.keyword.type_code,
        ...(translation.keyword?.name !== undefined && { name: translation.keyword.name }),
        ...(translation.keyword?.effect !== undefined && {
          effect: translation.keyword.effect,
        }),
      }
    : undefined;

  // --- Oshi skills: timing code from the card, display text from the translation ---
  const oshiSkill = card.oshi_skill
    ? {
        timing_code: card.oshi_skill.timing_code,
        ...(translation.oshi_skill?.name !== undefined && {
          name: translation.oshi_skill.name,
        }),
        ...(translation.oshi_skill?.effect !== undefined && {
          effect: translation.oshi_skill.effect,
        }),
        ...(translation.oshi_skill?.timing !== undefined && {
          timing: translation.oshi_skill.timing,
        }),
      }
    : undefined;

  const spOshiSkill = card.sp_oshi_skill
    ? {
        timing_code: card.sp_oshi_skill.timing_code,
        ...(translation.sp_oshi_skill?.name !== undefined && {
          name: translation.sp_oshi_skill.name,
        }),
        ...(translation.sp_oshi_skill?.effect !== undefined && {
          effect: translation.sp_oshi_skill.effect,
        }),
        ...(translation.sp_oshi_skill?.timing !== undefined && {
          timing: translation.sp_oshi_skill.timing,
        }),
      }
    : undefined;

  return {
    id: card.id,
    card_number: card.card_number,
    locale: resolved,
    card_type_code: card.card_type_code,
    rarity_code: card.rarity_code,
    color_codes: card.color_codes ?? [],
    ...(card.bloom_level_code !== undefined && { bloom_level_code: card.bloom_level_code }),
    image_key: card.image_key,
    ...(card.hp !== undefined && { hp: card.hp }),
    ...(card.life !== undefined && { life: card.life }),
    ...(card.baton_touch_count !== undefined && {
      baton_touch_count: card.baton_touch_count,
    }),
    baton_touch_types: card.baton_touch_types ?? [],
    ...(card.illustrator !== undefined && { illustrator: card.illustrator }),
    card_sets: card.card_sets,
    name: translation.name,
    tags: translation.tags ?? [],
    ...(translation.ability_text !== undefined && {
      ability_text: translation.ability_text,
    }),
    ...(translation.extra !== undefined && { extra: translation.extra }),
    arts,
    ...(keyword !== undefined && { keyword }),
    ...(oshiSkill !== undefined && { oshi_skill: oshiSkill }),
    ...(spOshiSkill !== undefined && { sp_oshi_skill: spOshiSkill }),
    qa_items: translation.qa_items ?? [],
  } as LocalizedCard;
}

/**
 * Compose a card's CDN URL from its key (decision D9).
 *
 * The one place the key -> URL mapping lives on the TypeScript side. v1 copy-pasted a
 * `getImagePath()` helper verbatim across three components; per the architecture review
 * that duplication is retired by having exactly one composer.
 *
 * @param imageKey - e.g. "default/hBP01-028_C_02"
 * @param baseUrl - CDN origin, e.g. "https://img.hololive-ocg-wiki.tskrlabs.com"
 * @param extension - image format. WebP only in production per D9.
 */
export function cardImage(
  imageKey: string,
  baseUrl: string,
  extension = "webp",
): string {
  return `${baseUrl.replace(/\/$/, "")}/${imageKey}.${extension}`;
}
