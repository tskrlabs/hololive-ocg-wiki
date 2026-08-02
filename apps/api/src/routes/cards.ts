/**
 * The card endpoints.
 *
 * Route order is not load-bearing here. v1 tested `/api/cards/:id` *last*, because
 * `path.startsWith("/api/cards/")` would otherwise swallow `/api/cards/search` — a
 * correctness property that lived in the order of an if-chain. The detail route is
 * constrained to digits instead, so the collision is impossible however the file is
 * arranged. Card ids are numeric strings, an invariant the seeder already enforces
 * because the FTS rowid depends on it.
 */

import { Hono } from "hono";

import type { Env } from "../types.ts";
import {
  cardByIdSql,
  cardByImageKeySql,
  cardKeyByLowercaseSql,
  cardsByCardNumberSql,
  cardsByIdsSql,
  filterCountSql,
  filterPageSql,
  firstCardPerNumberSql,
  rowToCard,
  type CardRow,
} from "../db/cards.ts";
import { searchSql } from "../db/fts.ts";
import {
  batchParamSchema,
  cardNumberParamSchema,
  filterQuerySchema,
  imageKeySegmentSchema,
  localeQuerySchema,
  searchQuerySchema,
} from "../lib/schemas.ts";
import { cached, failure } from "../lib/respond.ts";
import type { Locale } from "@holo/schema/enums";

export const cards = new Hono<{ Bindings: Env }>();

/**
 * `/api/cards-list/:ids` — several cards by id, for the deck builder.
 *
 * Its own router because the path is a *sibling* of `/api/cards`, not a child: v1 chose
 * `cards-list` rather than `cards/list`, and Phase 4 keeps the URL so Phase 5's
 * frontend does not have to change.
 */
export const cardsList = new Hono<{ Bindings: Env }>();

/** Run a prepared statement and project every row into the requested locale. */
async function fetchCards(
  env: Env,
  query: { sql: string; params: unknown[] },
  locale: Locale,
) {
  const { results } = await env.DB.prepare(query.sql)
    .bind(...query.params)
    .all<CardRow>();
  return results.map((row) => rowToCard(row, locale));
}

// GET /api/cards/search — free-text over all 7 locales at once.
cards.get("/search", async (c) => {
  const query = searchQuerySchema.parse(c.req.query());
  if (!query.q) return cached(c, { cards: [] });

  const built = searchSql(query.q, query.limit);
  const ids = await c.env.DB.prepare(built.sql)
    .bind(...built.params)
    .all<{ id: string }>();

  if (ids.results.length === 0) return cached(c, { cards: [] });

  // Re-fetch in the id order the index returned, so ranking survives the second query.
  const order = new Map(ids.results.map((row, index) => [String(row.id), index]));
  const found = await fetchCards(
    c.env,
    cardsByIdsSql(ids.results.map((row) => String(row.id))),
    query.locale as Locale,
  );
  found.sort((a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0));

  return cached(c, { cards: found });
});

// GET /api/cards/filter — the paginated, faceted list behind the main card grid.
cards.get("/filter", async (c) => {
  const query = filterQuerySchema.parse(c.req.query());

  // A search term inside a filter is resolved against FTS first and intersected, rather
  // than joined: `cards_fts` cannot be joined to `cards` without dragging the whole
  // index into the plan.
  // No limit: the count under the search box is the whole point of this endpoint's
  // `total`, and a capped id set makes it report the cap (issue #66).
  let searchIds: string[] | undefined;
  if (query.search) {
    const built = searchSql(query.search);
    const matched = await c.env.DB.prepare(built.sql)
      .bind(...built.params)
      .all<{ id: string }>();
    searchIds = matched.results.map((row) => String(row.id));
  }

  const filters = { ...query, page: query.page, limit: query.limit };
  const page = filterPageSql(filters, searchIds);
  const found = await fetchCards(c.env, page, query.locale as Locale);

  // `total` is omitted, not -1, when the client says it already has the count.
  if (query.skip_count) return cached(c, { cards: found });

  const count = filterCountSql(filters, searchIds);
  const totals = await c.env.DB.prepare(count.sql)
    .bind(...count.params)
    .first<{ total: number }>();

  return cached(c, { cards: found, total: totals?.total ?? 0 });
});

// GET /api/cards-list/:ids — several cards by id, in the order requested.
cardsList.get("/:ids", async (c) => {
  const parsed = batchParamSchema.safeParse(c.req.param("ids"));
  if (!parsed.success) {
    return failure(c, 400, parsed.error.issues[0]?.message ?? "invalid card ids");
  }
  const { locale } = localeQuerySchema.parse(c.req.query());

  const found = await fetchCards(c.env, cardsByIdsSql(parsed.data), locale as Locale);

  // Return them in the order asked for: the deck builder renders a deck list, and a
  // deck's order is the client's, not the database's.
  const position = new Map(parsed.data.map((id, index) => [id, index]));
  found.sort((a, b) => (position.get(a.id) ?? 0) - (position.get(b.id) ?? 0));

  return cached(c, { cards: found });
});

// GET /api/cards/by-card-numbers/:numbers — one representative card per number.
// Registered before the `:id` route for readability; the digit constraint is what
// actually keeps them apart.
cards.get("/by-card-numbers/:numbers", async (c) => {
  const parsed = batchParamSchema.safeParse(c.req.param("numbers"));
  if (!parsed.success) {
    return failure(c, 400, parsed.error.issues[0]?.message ?? "invalid card numbers");
  }
  const { locale } = localeQuerySchema.parse(c.req.query());
  return cached(c, {
    cards: await fetchCards(c.env, firstCardPerNumberSql(parsed.data), locale as Locale),
  });
});

// GET /api/cards/filter-by-card-number/:number — every printing of one number.
cards.get("/filter-by-card-number/:number", async (c) => {
  const parsed = cardNumberParamSchema.safeParse(c.req.param("number"));
  if (!parsed.success) return failure(c, 400, "invalid card number");

  const { locale } = localeQuerySchema.parse(c.req.query());
  return cached(c, {
    cards: await fetchCards(c.env, cardsByCardNumberSql(parsed.data), locale as Locale),
  });
});

/**
 * GET /api/cards/by-key/:set/:stem — one card by its `image_key` (ADR 0009 D6).
 *
 * The lookup behind a card URL: `/{locale}/card/{set}/{stem}` is `image_key` verbatim, so
 * a card page resolves through here rather than deriving an id client-side — which would
 * have meant shipping a 2,463-entry key→id map to every visitor.
 *
 * Registered before `/:id`, though the digit constraint on that route is what actually
 * keeps them apart; `by-key` contains no digits at its first segment position anyway.
 *
 * Returns the same `{ card }` shape as `/api/cards/:id`, Q&A included, because a card
 * *page* shows Q&A where a list tile does not.
 *
 * **A wrong-case key gets a `canonical` field rather than a card.** Matching is
 * case-sensitive because the stored form is canonical and an index only serves exact
 * matches; rather than 404 a URL that differs only in casing, the miss path asks once
 * more case-insensitively and reports the correct key. The caller (the card-page route,
 * commit 10) turns that into a 301. Verified over the real set: lowercasing all 2,463
 * keys still yields 2,463 distinct values, so this can never be ambiguous.
 */
cards.get("/by-key/:set/:stem", async (c) => {
  const set = imageKeySegmentSchema.safeParse(c.req.param("set"));
  const stem = imageKeySegmentSchema.safeParse(c.req.param("stem"));
  if (!set.success || !stem.success) return failure(c, 400, "invalid card key");

  const { locale } = localeQuerySchema.parse(c.req.query());
  const imageKey = `${set.data}/${stem.data}`;

  const query = cardByImageKeySql(imageKey);
  const row = await c.env.DB.prepare(query.sql)
    .bind(...query.params)
    .first<CardRow>();

  if (row) return cached(c, { card: rowToCard(row, locale as Locale) });

  // Only now — an exact miss is the rare path, and this second query is a full scan.
  const alternate = cardKeyByLowercaseSql(imageKey);
  const canonical = await c.env.DB.prepare(alternate.sql)
    .bind(...alternate.params)
    .first<{ image_key: string }>();

  if (canonical) {
    // 404 with a `canonical` field: the key as given does not identify a card, and the
    // caller decides whether that becomes a redirect or a not-found screen.
    return c.json({ error: "card not found", canonical: canonical.image_key }, 404);
  }

  return failure(c, 404, "card not found");
});

// GET /api/cards/:id — one card, with its Q&A.
cards.get("/:id{[0-9]+}", async (c) => {
  const { locale } = localeQuerySchema.parse(c.req.query());
  const query = cardByIdSql(c.req.param("id"));
  const row = await c.env.DB.prepare(query.sql)
    .bind(...query.params)
    .first<CardRow>();

  if (!row) return failure(c, 404, "card not found");
  return cached(c, { card: rowToCard(row, locale as Locale) });
});
