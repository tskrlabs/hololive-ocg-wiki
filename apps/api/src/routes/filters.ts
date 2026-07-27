/**
 * `/api/filter-options` — the dropdown values, served from R2.
 *
 * Not from D1. The answer is identical for every user until the next reseed, and v1
 * computed it per call with four `SELECT DISTINCT` full scans — on the endpoint family
 * whose read count breached the free tier (F-014, ADR 0004). `holo-data build` writes
 * these files beside `cards.json`, so they cannot describe a different card set than
 * the one that shipped.
 *
 * v1's second options endpoint, `/api/static-filters`, is **gone**. It returned card
 * types, rarities, colours and bloom levels — enum values the contract already owns and
 * `@holo/schema/enums` already generates. v1's own frontend never called it; it read a
 * hand-maintained `constants/card-data.ts` that had drifted from the data (missing the
 * `HR` rarity, and `1st`/`2nd` where the data says `first`/`second`). Phase 5 imports
 * the generated arrays instead, which is the whole point of defining the contract once.
 */

import { Hono } from "hono";

import type { Env } from "../types.ts";
import { localeQuerySchema } from "../lib/schemas.ts";
import { failure, FILTER_OPTIONS_TTL } from "../lib/respond.ts";

export const filters = new Hono<{ Bindings: Env }>();

filters.get("/filter-options", async (c) => {
  const { locale } = localeQuerySchema.parse(c.req.query());

  const object = await c.env.ARTIFACTS.get(`filter-options/${locale}.json`);
  if (!object) {
    // The artifact is missing rather than the request being wrong — a working directory
    // built before Phase 4, or a publish that has not run yet.
    return failure(c, 404, `no filter options published for locale "${locale}"`);
  }

  // Streamed straight through rather than parsed and re-serialised — the Worker has no
  // reason to look inside, so the bytes R2 holds are the bytes the client gets.
  c.header("Cache-Control", `public, max-age=${FILTER_OPTIONS_TTL}`);
  c.header("Content-Type", "application/json; charset=utf-8");
  return c.body(object.body);
});
