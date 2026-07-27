/**
 * Query shapes.
 *
 * Phase 3's expensive bugs were both *shapes* — a skip-scan and a full-table delete —
 * and neither was visible in the values a query returned. These assert the shape, which
 * is why they can run with no database.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  buildWhere,
  expandColors,
  filterCountSql,
  filterPageSql,
  firstCardPerNumberSql,
  type CardFilters,
} from "../src/db/cards.ts";

const base: CardFilters = { page: 1, limit: 50 };

test("a filtered colour expands to the fused codes containing it", () => {
  // `blue_red` is one printed icon, stored as printed. Without expansion a `blue`
  // filter silently misses those cards — measured on the real set: 5 for blue_red, 2
  // for white_green. v1 had no expansion and its blue filter was quietly incomplete.
  assert.deepEqual(expandColors(["blue"]), ["blue", "blue_red"]);
  assert.deepEqual(expandColors(["red"]), ["blue_red", "red"]);
  assert.deepEqual(expandColors(["green"]), ["green", "white_green"]);
  assert.deepEqual(expandColors(["white"]), ["white", "white_green"]);
  // A colour with no fused partner is unchanged, and no duplicates when both halves
  // of a fused pair are requested.
  assert.deepEqual(expandColors(["purple"]), ["purple"]);
  assert.deepEqual(expandColors(["blue", "red"]), ["blue", "blue_red", "red"]);
});

test("junction filters use IN (SELECT …), never a join", () => {
  // A join against a junction returns one row per matching *value*, so a card matching
  // two requested colours would appear twice and corrupt both the page and the count.
  // ADR 0004 calls this out specifically.
  const where = buildWhere({ ...base, colors: ["blue", "red"] });
  assert.match(where.sql, /id IN \(SELECT card_id FROM card_colors WHERE color_code IN/);
  assert.doesNotMatch(where.sql, /JOIN/i);
});

test("filter groups are OR within and AND across", () => {
  const where = buildWhere({
    ...base,
    colors: ["blue"],
    rarity: ["C", "R"],
    cardTypes: ["character"],
  });
  assert.match(where.sql, /rarity_code IN \(\?, \?\)/);
  assert.equal(where.sql.split(" AND ").length, 3);
});

test("the name filter matches the source-locale column", () => {
  // The ja name is the stable per-character identity; 41% of characters are spelled
  // inconsistently in at least one locale (F-015).
  const where = buildWhere({ ...base, name: "白上フブキ" });
  assert.match(where.sql, /name_ja = \?/);
  assert.deepEqual(where.params, ["白上フブキ"]);
});

test("a search matching nothing yields no cards, not every card", () => {
  // The subtle one: an empty id list must not simply omit the condition, which would
  // turn "no results" into "the whole table".
  const where = buildWhere(base, []);
  assert.equal(where.sql, "WHERE 1 = 0");
});

test("count and page queries share exactly one WHERE clause", () => {
  // If these drift, the page shows one set of cards and the total counts another.
  const filters: CardFilters = { ...base, colors: ["blue"], rarity: ["C"] };
  const page = filterPageSql(filters);
  const count = filterCountSql(filters);
  const clause = /WHERE (.*?)(?: ORDER BY|$)/;
  assert.equal(page.sql.match(clause)?.[1], count.sql.match(clause)?.[1]);
});

test("pagination binds limit and offset last", () => {
  const built = filterPageSql({ ...base, page: 3, limit: 20, rarity: ["C"] });
  assert.deepEqual(built.params.slice(-2), [20, 40]);
});

test("ordering is total, so pages cannot overlap or skip", () => {
  // card_number is not unique — 2,448 cards share 1,228 numbers — so ordering by it
  // alone leaves ties in an arbitrary order that LIMIT/OFFSET can slice inconsistently.
  assert.match(filterPageSql(base).sql, /ORDER BY card_number, id/);
});

test("the first card per number is chosen numerically", () => {
  // Ids are numeric *strings*: a lexicographic min picks "1000" over "999".
  assert.match(firstCardPerNumberSql(["hBP01-104"]).sql, /min\(CAST\(id AS INTEGER\)\)/);
});

test("list queries never select the Q&A payload", () => {
  // Q&A is 53% of the translation bytes and nothing in a card tile renders it.
  assert.doesNotMatch(filterPageSql(base).sql, /qa_payload/);
});
