/**
 * The filter shape, **derived** from the contract's enums rather than written out.
 *
 * v1 spelled this shape three incompatible ways — an object-of-booleans here, four
 * string arrays in `constants/card-data.ts`, and inline `{white: false, …}` literals in
 * five more places. Because the enum was written twice, the two spellings could disagree,
 * and they did: `CARD_BLOOM_LEVELS = ["debut","1st","2nd","spot"]` against a type saying
 * `debut|first|second|spot`, so two of four bloom filters silently matched nothing.
 *
 * Mapped types over `COLORS` / `CARD_TYPES` / `RARITIES` / `BLOOM_LEVELS` make that class
 * of bug unrepresentable: adding a rarity to the pydantic models regenerates the enum,
 * and this shape follows without an edit. v1's version also used boxed `Boolean` rather
 * than `boolean`, which accepts an object and is truthy even when it wraps `false`.
 *
 * Candidate 02 (ADR 0006) deepens the *module* around this shape — one `createEmpty()`,
 * one `toApiParams()`, one `isActive()`. This file is the shape it operates on.
 */

import type {
  BloomLevelCode,
  CardTypeCode,
  ColorCode,
  RarityCode,
} from "@holo/schema/enums";

/** Every member of an enum mapped to a checkbox state. */
type Flags<T extends string> = Record<T, boolean>;

export type ColorFilter = Flags<ColorCode>;
export type CardTypeFilter = Flags<CardTypeCode>;
export type RarityFilter = Flags<RarityCode>;
export type BloomLevelFilter = Flags<BloomLevelCode>;

export type FilterOptions = {
  search: string;
  name: string;
  tag: string;
  set: string;
  /**
   * The set code — `hBP03`. A *different* dimension from `set`, not a spelling of it.
   *
   * `set` filters on the product a card shipped in (`ブースターパック「エリートスパーク」`);
   * this filters on the prefix of its card number. They overlap without agreeing —
   * hBP03 is 283 cards, Elite Spark is 244, and only 229 are both — so collapsing them
   * would make one control give two different answers.
   */
  setCode: string;
  colors: ColorFilter;
  cardTypes: CardTypeFilter;
  rarity: RarityFilter;
  bloomLevel: BloomLevelFilter;
};

/**
 * One `/api/filter-options` entry: a source-locale value with a translated label.
 *
 * `value` is what the API is queried with and `label` is what the user reads — they
 * differ for names, where the filter keys on `name_ja` because 41% of characters are
 * spelled inconsistently across their own cards (F-015).
 */
export type FilterOption = { value: string; label: string };

export type FilterOptionsResponse = {
  names: FilterOption[];
  tags: FilterOption[];
  sets: FilterOption[];
  /**
   * The set codes, where `value` and `label` are both the code.
   *
   * Optional because the site may be served against an artifact built before set codes
   * existed — R2 holds whatever the last publish wrote, and a Worker deploy does not
   * republish it. The picker renders nothing rather than `undefined.length` throwing.
   */
  set_codes?: FilterOption[];
};
