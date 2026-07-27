/**
 * Response helpers — one place that decides how long anything is cached.
 *
 * Caching is not a nicety here: it is the protection for both metered resources. D1
 * reads breached the 5M/day free tier once already (F-014), and Workers requests are
 * capped at 100k/day, above which the site stops serving. v1's `checkRateLimit()`
 * pretended to guard that and unconditionally returned `true`; it is deleted rather
 * than ported, and these headers are what actually stands in its place.
 *
 * TTLs are set against how often the data really changes — a reseed, typically weekly —
 * rather than v1's 5 minutes, which allowed 288 origin hits per unique query per day.
 * `Cache-Control` alone, no `caches.default`: for a GET the edge honours the header, and
 * the manual match/put pair only duplicated it while adding a `waitUntil` to every
 * handler.
 */

import type { Context } from "hono";

/** Card data. Changes only when the maintainer reseeds. */
export const CARD_TTL = 3600;

/** Dropdown values. Change even less often, and are served from a static R2 object. */
export const FILTER_OPTIONS_TTL = 86400;

export function cached<T>(c: Context, body: T, ttl: number = CARD_TTL): Response {
  c.header("Cache-Control", `public, max-age=${ttl}`);
  return c.json(body as object);
}

/**
 * An error response.
 *
 * The message is ours, never the underlying exception's: v1 leaked `D1_ERROR` and SQL
 * text to clients before sanitising it, and the sanitiser was a substring match over
 * error messages. Handlers here raise `HTTPException` with text written for a reader.
 */
export function failure(c: Context, status: 400 | 404 | 500, message: string): Response {
  return c.json({ error: message }, status);
}
