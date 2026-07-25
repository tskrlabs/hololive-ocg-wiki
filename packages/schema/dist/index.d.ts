/**
 * DO NOT EDIT — generated from the pydantic models in packages/schema/src/holo_schema/.
 *
 * Regenerate with `make generate`. `make check` fails if this file is stale.
 */

// The canonical contract — what the pipeline writes and D1 stores.
export type {
  Card,
  CardCollection,
  Art,
  Keyword,
  OshiSkill,
  Translation,
  Translations,
  TranslatedArt,
  TranslatedKeyword,
  TranslatedOshiSkill,
  QaItem,
  RelatedCards,
} from './card.d.ts';

// The API response shape — one card, one locale, flattened.
export type {
  LocalizedCard,
  LocalizedArt,
  LocalizedKeyword,
  LocalizedOshiSkill,
} from './localized-card.d.ts';

// Enum types and their runtime values.
export * from './enums.ts';
