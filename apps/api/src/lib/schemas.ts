/**
 * Input validation (D7).
 *
 * Zod guards the untrusted boundary — query strings and path params — replacing v1's
 * hand-rolled `validateAndSanitizeString` / `validateStringArray` / `validateInteger`
 * trio. The enum members come from `@holo/schema/enums`, which is generated from the
 * same pydantic models as the database, so a new rarity cannot be accepted by the API
 * and rejected by the contract.
 *
 * **Output is deliberately not validated here.** `localize()` returns `LocalizedCard` by
 * construction and is pinned byte-for-byte against the Python reference by the golden
 * files; re-checking that per request would spend CPU on every card to re-prove what
 * `make check` proves once.
 */

import { z } from "zod";
import {
  BLOOM_LEVELS,
  CARD_TYPES,
  COLORS,
  DEFAULT_LOCALE,
  LOCALES,
  MAX_BATCH,
  RARITIES,
} from "@holo/schema/enums";

/**
 * The batch cap comes from the contract, not from a literal here.
 *
 * The site has to chunk its requests to the same number this endpoint rejects above, and
 * a legal deck already exceeds it (1 oshi + 50 main + 20 yell = 71 cards) — so two
 * copies of the value would be reached in normal use, not at some edge.
 */
export { MAX_BATCH };

/** Longest accepted search string, matching v1's cap. */
const MAX_QUERY = 500;

/**
 * The requested language, falling back to the default rather than failing.
 *
 * `.catch()` and not just `.default()`: an unrecognised locale degrades to `tc` instead
 * of 400-ing, matching v1's `validateLocale`. The site's i18n uses URL prefixes, so a
 * stale link or a locale the site once served (v1's list included `sc`, which the data
 * never had) would otherwise turn a whole page into an error instead of showing the
 * card in the default language.
 */
const locale = z
  .enum(LOCALES as unknown as [string, ...string[]])
  .default(DEFAULT_LOCALE)
  .catch(DEFAULT_LOCALE);

/**
 * A comma-separated query parameter, e.g. `colors=blue,red`.
 *
 * Empty segments are dropped rather than rejected: `colors=blue,` is a trailing comma
 * from a client that joined an array, not a request for a card with no colour.
 */
const csv = <T extends readonly string[]>(values: T) =>
  z
    .string()
    .optional()
    .transform((raw) => (raw ? raw.split(",").filter(Boolean) : undefined))
    .pipe(z.array(z.enum(values as unknown as [string, ...string[]])).max(20).optional());

/** A trimmed, length-capped free-text value; blank becomes undefined. */
const text = (max: number) =>
  z
    .string()
    .trim()
    .max(max)
    .optional()
    .transform((value) => (value ? value : undefined));

const positiveInt = (max: number, fallback: number) =>
  z.coerce.number().int().min(1).max(max).catch(fallback);

export const searchQuerySchema = z.object({
  q: text(MAX_QUERY),
  locale,
  limit: positiveInt(200, 100),
});

/**
 * A set code — `hBP03`, `hSD01`, `hPR`.
 *
 * Constrained by shape rather than to a list of the 36 that exist today: the codes live
 * in the build artifact, not in the contract, so a new set would otherwise mean editing
 * the Worker to accept cards it is already serving. The pattern is tight enough that
 * anything reaching `setCodeRange` is a plausible code, and an implausible one returns
 * an empty page rather than an error — which is the same thing an unknown `tag` or `set`
 * does.
 *
 * Anchored and length-capped so it cannot be used to smuggle a range bound.
 */
const setCode = z
  .string()
  .trim()
  .regex(/^[A-Za-z]{1,6}\d{0,3}$/)
  .max(9)
  .optional()
  .transform((value) => (value ? value : undefined));

export const filterQuerySchema = z.object({
  search: text(MAX_QUERY),
  name: text(200),
  tag: text(100),
  set: text(500),
  set_code: setCode,
  colors: csv(COLORS),
  cardTypes: csv(CARD_TYPES),
  rarity: csv(RARITIES),
  bloomLevel: csv(BLOOM_LEVELS),
  locale,
  page: positiveInt(1000, 1),
  limit: positiveInt(200, 50),
  // Infinite scroll already has the total from page 1; skipping the count saves a whole
  // D1 round-trip per scroll. Unlike v1 the response omits `total` rather than
  // returning -1 as a sentinel.
  skip_count: z
    .string()
    .optional()
    .transform((value) => value === "true"),
});

export const localeQuerySchema = z.object({ locale });

/**
 * A comma-separated batch of ids or card numbers from the URL *path*.
 *
 * Over the cap this **fails** rather than truncating. v1 sliced to the first 50 and
 * returned them silently, so a deck longer than 50 cards rendered short with no error —
 * the worst failure mode available to a deck builder.
 */
export const batchParamSchema = z
  .string()
  .transform((raw) => raw.split(",").map((part) => part.trim()).filter(Boolean))
  .pipe(
    z
      .array(z.string().regex(/^[a-zA-Z0-9_-]+$/, "must be alphanumeric").max(50))
      .min(1, "at least one value is required")
      .max(MAX_BATCH, `too many values: the maximum is ${MAX_BATCH}`),
  );

/** A single card number from the path. */
export const cardNumberParamSchema = z
  .string()
  .trim()
  .min(1)
  .max(50)
  .regex(/^[a-zA-Z0-9_-]+$/, "must be alphanumeric");

/**
 * One segment of an `image_key` — a set folder or a card stem (ADR 0009 D6).
 *
 * The same character class as a card number, and that is a measured fact rather than an
 * assumption: across all 2,463 keys, **zero** segments require percent-encoding, every
 * key is exactly `set/stem`, and the longest segment is well inside 50. So a segment that
 * fails this regex cannot name a real card, and rejecting it here keeps a malformed URL
 * from reaching D1 at all.
 *
 * Case is preserved, not normalised: the stored form is canonical (`hSD01/hSD01-001_OSR`)
 * and the route redirects a wrong-case URL rather than resolving it silently.
 */
export const imageKeySegmentSchema = z
  .string()
  .trim()
  .min(1)
  .max(50)
  .regex(/^[a-zA-Z0-9_-]+$/, "must be alphanumeric");
