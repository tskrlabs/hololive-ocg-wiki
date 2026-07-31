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
  cardByImageKeySql,
  cardKeyByLowercaseSql,
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

test("junction filters use a correlated EXISTS, never a join and never IN (SELECT …)", () => {
  // Two independent constraints, and the shape is the only place both are visible.
  //
  // *Never a join* (ADR 0004): a join against a junction returns one row per matching
  // *value*, so a card matching two requested colours would appear twice and corrupt
  // both the page and the count.
  //
  // *Never `IN (SELECT …)`* (#40): that form makes the id set the driver, so every match
  // is materialised and sorted before LIMIT applies — 4–8× more rows read than needed,
  // and the cost grows with the match set. `EXISTS` correlates against `cards.id`, which
  // lets the walk stop at LIMIT.
  // Three placeholders, not two: `blue, red` expands to `blue, blue_red, red`.
  const where = buildWhere({ ...base, colors: ["blue", "red"] });
  assert.match(
    where.sql,
    /EXISTS \(SELECT 1 FROM card_colors j WHERE j\.card_id = cards\.id AND j\.color_code IN \(\?, \?, \?\)\)/,
  );
  assert.doesNotMatch(where.sql, /JOIN/i);
  assert.doesNotMatch(where.sql, /id IN \(SELECT/);
});

test("every junction filter takes the EXISTS form, not just colours", () => {
  // All three call sites share `buildWhere`, and the tag and set filters are where the
  // measured saving is largest — the top tag went 3,885 → 269 rows, the top set
  // 1,513 → 152, because a big match set is exactly what the old form sorted in full.
  for (const [filters, table, column] of [
    [{ ...base, tag: "JP" }, "card_tags", "tag"],
    [{ ...base, set: "hBP01" }, "card_sets", "set_name"],
  ] as const) {
    const where = buildWhere(filters);
    assert.match(
      where.sql,
      new RegExp(`EXISTS \\(SELECT 1 FROM ${table} j WHERE j\\.card_id = cards\\.id AND j\\.${column} IN`),
    );
  }
});

test("filter groups are OR within and AND across", () => {
  const where = buildWhere({
    ...base,
    colors: ["blue"],
    rarity: ["C", "R"],
    cardTypes: ["character"],
  });
  assert.match(where.sql, /rarity_code IN \(\?, \?\)/);
  // Count only the ANDs *between* groups. Splitting the whole string no longer works:
  // the junction subquery carries its own `AND` correlating j.card_id to cards.id, so
  // a naive split reports one group too many. Collapse nested parens innermost-first
  // until nothing changes, which leaves only the top-level conjunction.
  let topLevel = where.sql;
  for (let flat = ""; flat !== topLevel; ) {
    flat = topLevel;
    topLevel = flat.replace(/\([^()]*\)/g, "…");
  }
  assert.equal(topLevel.split(" AND ").length, 3);
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

test("a card is looked up by its whole image_key, not by set and stem apart", () => {
  // The URL is `/{locale}/card/{set}/{stem}` and `{set}/{stem}` *is* `image_key`
  // (ADR 0009 D6). Splitting the predicate in two would miss the unique index that
  // commit 6 added, which is the difference between a seek and a 2,463-row scan.
  const query = cardByImageKeySql("hSD01/hSD01-001_OSR");
  assert.match(query.sql, /WHERE image_key = \?/);
  assert.deepEqual(query.params, ["hSD01/hSD01-001_OSR"]);
});

test("a card page selects the Q&A payload, unlike a list", () => {
  // 35% of cards carry Q&A and the page renders it — the one place the split payload is
  // worth reassembling.
  assert.match(cardByImageKeySql("hSD01/x").sql, /qa_payload/);
});

test("the case-insensitive lookup returns only a key, and only one", () => {
  // The error path: a wrong-case URL is redirected rather than 404'd. It costs a full
  // scan, so it must stay cheap in what it selects and must not be mistaken for the
  // primary lookup. Verified over the real set that it cannot be ambiguous — lowercasing
  // all 2,463 keys still yields 2,463 distinct values.
  const query = cardKeyByLowercaseSql("HSD01/HSD01-001_OSR");
  assert.match(query.sql, /SELECT image_key FROM cards/);
  assert.match(query.sql, /lower\(image_key\) = lower\(\?\)/);
  assert.match(query.sql, /LIMIT 1/);
  // No payload: this answers "what is the right key", not "what is the card".
  assert.doesNotMatch(query.sql, /payload/);
});
