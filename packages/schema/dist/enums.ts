/**
 * DO NOT EDIT — generated from the pydantic models in packages/schema/src/holo_schema/.
 *
 * Regenerate with `make generate`. `make check` fails if this file is stale.
 */

// --- Enum types ---

export type Locale = "ja" | "en" | "tc" | "id" | "ko" | "th" | "es";
export type CardTypeCode = "buzzCharacter" | "character" | "oshiCharacter" | "supportCheer" | "supportEvent" | "supportEventLimited" | "supportFan" | "supportItem" | "supportItemLimited" | "supportMascot" | "supportStaff" | "supportStaffLimited" | "supportTool" | "unknown";
export type RarityCode = "C" | "HR" | "OC" | "OSR" | "OUR" | "P" | "R" | "RR" | "S" | "SEC" | "SR" | "SY" | "U" | "UR";
export type ColorCode = "blue" | "blue_red" | "green" | "null" | "purple" | "red" | "white" | "white_green" | "yellow";
export type BloomLevelCode = "debut" | "first" | "second" | "spot";
export type KeywordTypeCode = "bloom_effect" | "collab_effect" | "gift";
export type TimingCode = "once_per_game" | "once_per_turn";

// --- Enum values, for filter UIs and validation ---

export const LOCALES: readonly Locale[] = ["ja", "en", "tc", "id", "ko", "th", "es"] as const;
export const CARD_TYPES: readonly CardTypeCode[] = ["buzzCharacter", "character", "oshiCharacter", "supportCheer", "supportEvent", "supportEventLimited", "supportFan", "supportItem", "supportItemLimited", "supportMascot", "supportStaff", "supportStaffLimited", "supportTool", "unknown"] as const;
export const RARITIES: readonly RarityCode[] = ["C", "HR", "OC", "OSR", "OUR", "P", "R", "RR", "S", "SEC", "SR", "SY", "U", "UR"] as const;
export const COLORS: readonly ColorCode[] = ["blue", "blue_red", "green", "null", "purple", "red", "white", "white_green", "yellow"] as const;
export const BLOOM_LEVELS: readonly BloomLevelCode[] = ["debut", "first", "second", "spot"] as const;
export const KEYWORD_TYPES: readonly KeywordTypeCode[] = ["bloom_effect", "collab_effect", "gift"] as const;
export const TIMINGS: readonly TimingCode[] = ["once_per_game", "once_per_turn"] as const;

// --- Domain constants ---

export const SOURCE_LOCALE: Locale = "ja";
export const DEFAULT_LOCALE: Locale = "tc";
export const SCHEMA_VERSION = 1;

// --- Deck sections (see architecture review Candidate 03) ---

export const OSHI_CARD_TYPES: readonly CardTypeCode[] = ["oshiCharacter"] as const;
export const MAIN_CARD_TYPES: readonly CardTypeCode[] = ["buzzCharacter", "character", "supportEvent", "supportEventLimited", "supportFan", "supportItem", "supportItemLimited", "supportMascot", "supportStaff", "supportStaffLimited", "supportTool"] as const;
export const YELL_CARD_TYPES: readonly CardTypeCode[] = ["supportCheer"] as const;

/**
 * Fused dual-colour symbols and the colours they contain.
 *
 * `blue_red` is a single printed symbol, not shorthand for `[blue, red]` —
 * the card bears one icon. Use this when filtering so a "blue" filter also
 * matches `blue_red`, but never to rewrite the stored value.
 */
export const FUSED_COLORS: Partial<Record<ColorCode, readonly ColorCode[]>> = {
  blue_red: ["blue", "red"],
  white_green: ["white", "green"],
};
