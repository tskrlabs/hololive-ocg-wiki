/**
 * DO NOT EDIT — generated from the pydantic models in packages/schema/src/holo_schema/.
 *
 * Regenerate with `make generate`. `make check` fails if this file is stale.
 */

// --- Enum types ---

export type Locale = "ja" | "en" | "tc" | "id" | "ko" | "th" | "es";
export type CardTypeCode = "buzzCharacter" | "character" | "oshiCharacter" | "rulesNotice" | "supportCheer" | "supportEvent" | "supportEventLimited" | "supportFan" | "supportItem" | "supportItemLimited" | "supportMascot" | "supportStaff" | "supportStaffLimited" | "supportTool";
export type RarityCode = "C" | "HR" | "OC" | "OSR" | "OUR" | "P" | "R" | "RR" | "S" | "SEC" | "SR" | "SY" | "U" | "UR";
export type ColorCode = "blue" | "green" | "null" | "purple" | "red" | "white" | "yellow";
export type BloomLevelCode = "debut" | "first" | "second" | "spot";
export type KeywordTypeCode = "bloom_effect" | "collab_effect" | "gift";
export type TimingCode = "once_per_game" | "once_per_turn";

// --- Enum values, for filter UIs and validation ---

export const LOCALES: readonly Locale[] = ["ja", "en", "tc", "id", "ko", "th", "es"] as const;
/** Every card type, including non-card entries. For validation.
 *  For a filter UI use `FILTERABLE_CARD_TYPES` — see below. */
export const CARD_TYPES: readonly CardTypeCode[] = ["buzzCharacter", "character", "oshiCharacter", "rulesNotice", "supportCheer", "supportEvent", "supportEventLimited", "supportFan", "supportItem", "supportItemLimited", "supportMascot", "supportStaff", "supportStaffLimited", "supportTool"] as const;
export const RARITIES: readonly RarityCode[] = ["C", "HR", "OC", "OSR", "OUR", "P", "R", "RR", "S", "SEC", "SR", "SY", "U", "UR"] as const;
export const COLORS: readonly ColorCode[] = ["blue", "green", "null", "purple", "red", "white", "yellow"] as const;
export const BLOOM_LEVELS: readonly BloomLevelCode[] = ["debut", "first", "second", "spot"] as const;
export const KEYWORD_TYPES: readonly KeywordTypeCode[] = ["bloom_effect", "collab_effect", "gift"] as const;
export const TIMINGS: readonly TimingCode[] = ["once_per_game", "once_per_turn"] as const;

// --- Domain constants ---

export const SOURCE_LOCALE: Locale = "ja";
export const DEFAULT_LOCALE: Locale = "tc";
export const SCHEMA_VERSION = 1;

/** Most ids or card numbers one batch request may carry. The Worker
 *  400s above this; the site chunks to fit. A legal deck (1 + 50 + 20)
 *  already exceeds it, so the two must agree. */
export const MAX_BATCH = 50;

// --- Non-card entries ---

/**
 * Types in `CARD_TYPES` that are not playable cards.
 *
 * The official site publishes format-legality notices into its card list
 * (F-020). They are stored as `Notice`s and served by /api/notices, never
 * as cards — so no `/api/cards` response can contain one.
 */
export const NON_CARD_TYPES: readonly CardTypeCode[] = ["rulesNotice"] as const;

/**
 * What a card-type filter should offer.
 *
 * `CARD_TYPES` minus the non-card entries. Building a filter from the full
 * list would show a checkbox that always returns zero results — the same
 * class of always-dead UI as F-019, and equally invisible to a test that
 * only checks pure functions.
 */
export const FILTERABLE_CARD_TYPES: readonly CardTypeCode[] = ["buzzCharacter", "character", "oshiCharacter", "supportCheer", "supportEvent", "supportEventLimited", "supportFan", "supportItem", "supportItemLimited", "supportMascot", "supportStaff", "supportStaffLimited", "supportTool"] as const;

// --- Deck sections (see architecture review Candidate 03) ---

export const OSHI_CARD_TYPES: readonly CardTypeCode[] = ["oshiCharacter"] as const;
export const MAIN_CARD_TYPES: readonly CardTypeCode[] = ["buzzCharacter", "character", "supportEvent", "supportEventLimited", "supportFan", "supportItem", "supportItemLimited", "supportMascot", "supportStaff", "supportStaffLimited", "supportTool"] as const;
export const YELL_CARD_TYPES: readonly CardTypeCode[] = ["supportCheer"] as const;

/**
 * Dual-colour pairs that have a name of their own, keyed on the joined
 * codes (`"blue,red"`). Display only — storage is the two codes, in
 * printed order (ADR 0013).
 *
 * A card bearing this pair reads "Blue-Red" rather than "Blue, Red",
 * because the game names the combination. The i18n key is `colors.{name}`.
 * Both orders map to one name: the pair is the same identity either way.
 */
export const COLOR_PAIRS: Readonly<Record<string, string>> = {
  "blue,red": "blue_red",
  "red,blue": "blue_red",
  "white,green": "white_green",
  "green,white": "white_green",
};
