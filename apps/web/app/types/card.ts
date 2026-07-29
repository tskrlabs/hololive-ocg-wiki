/**
 * The card shape, re-exported from the generated contract (D5, ADR 0001).
 *
 * **This file declares nothing.** v1 hand-wrote a `Card` type here, the fourth copy of a
 * shape also written out in Python, `schema.sql` and `worker.ts` — and it had measurably
 * drifted: the `HR` rarity was missing from the rarity union, leaving 24 cards
 * unfilterable in the live UI; `supportStaff` and `unknown` were absent from the card
 * types (`unknown` was later removed from the contract by issue #19, so only
 * `supportStaff` remains as drift); and a commented-out `Translations` block described a
 * schema that no longer existed.
 *
 * `LocalizedCard` is what every endpoint returns — one locale, translations flattened to
 * the top. The alias keeps v1's call sites reading naturally, since to this app a card
 * *is* the localized one; nothing here ever sees the canonical 7-locale `Card`.
 *
 * Differences from v1's hand-written type, all deliberate:
 *
 * - `image_path` / `image_url` → `image_key` (D9). Compose URLs with `useCardImage()`.
 * - `card_type` / `color` / `rarity` / `set_name` are gone — v1 carried translated
 *   display strings beside their codes, but the UI renders the codes through i18n
 *   (`$t('cardTypes.' + card.card_type_code)`) and never read them.
 * - `qaItems` is gone; it was a camelCase duplicate of `qa_items` in the same type.
 * - `locale` is new, so a cached response cannot be mistaken for another locale's.
 */

import type { LocalizedCard } from "@holo/schema";

export type Card = LocalizedCard;
export type CardCollection = Card[];

export type { Locale as Locales } from "@holo/schema/enums";
export type {
  BloomLevelCode,
  CardTypeCode,
  ColorCode,
  KeywordTypeCode,
  RarityCode,
  TimingCode,
} from "@holo/schema/enums";

export type {
  LocalizedArt,
  LocalizedKeyword,
  LocalizedOshiSkill,
  QaItem,
} from "@holo/schema";
