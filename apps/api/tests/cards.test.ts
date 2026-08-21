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
  cardsByIdsSql,
  filterCountSql,
  filterPageSql,
  firstCardPerNumberSql,
  setCodeRange,
  type CardFilters,
} from "../src/db/cards.ts";

const base: CardFilters = { page: 1, limit: 50 };

test("a colour filter binds exactly what was asked for, with nothing expanded", () => {
  // This replaces the `expandColors` test, and pins the reason it is gone. `blue_red`
  // used to be its own stored code, so a `blue` filter had to be widened to also match
  // it (F-016); ADR 0013 normalised it to `["blue", "red"]` at extraction, so a
  // dual-colour card holds a `blue` row and the plain filter hits it.
  //
  // Asserting the bound parameters, not just the SQL shape: an expansion reintroduced
  // upstream would leave this regex matching while binding a code that no longer exists
  // in the column, which is a filter that silently returns nothing.
  const one = buildWhere({ ...base, colors: ["blue"] });
  assert.deepEqual(one.params, ["blue"]);
  assert.match(one.sql, /j\.color_code IN \(\?\)/);

  const two = buildWhere({ ...base, colors: ["blue", "red"] });
  assert.deepEqual(two.params, ["blue", "red"]);
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
  // Two placeholders for two colours — one each, since ADR 0013 removed the expansion.
  const where = buildWhere({ ...base, colors: ["blue", "red"] });
  assert.match(
    where.sql,
    /EXISTS \(SELECT 1 FROM card_colors j WHERE j\.card_id = cards\.id AND j\.color_code IN \(\?, \?\)\)/,
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

test("a set code filters by card_number range, not LIKE", () => {
  // The range is what makes the existing `idx_cards_card_number` a *seek*. Measured on
  // production: `SEARCH cards USING INDEX idx_cards_card_number` for the page and
  // `SEARCH … USING COVERING INDEX` for the count. `LIKE 'hBP03-%'` degrades to a scan,
  // because SQLite cannot prove a bound parameter is prefix-shaped.
  const where = buildWhere({ ...base, setCode: "hBP03" });
  assert.match(where.sql, /card_number >= \? AND card_number < \?/);
  assert.doesNotMatch(where.sql, /LIKE/);
  assert.deepEqual(where.params, ["hBP03-", "hBP03."]);
});

test("the set-code range stops before the next card number", () => {
  // `.` is the codepoint after `-`, so the range covers every `hBP03-…` and nothing
  // else. Pinned because an off-by-one here is silent: a wider bound would fold a
  // neighbouring set in, and every count on the page would be quietly wrong.
  const { from, to } = setCodeRange("hBP03");
  assert.ok(from < "hBP03-001" && "hBP03-999" < to);
  // The set beneath it in sort order is excluded at both ends.
  assert.ok("hBP02-999" < from);
  assert.ok(to < "hBP04-001");
});

test("set code and product set are AND'd, not alternatives", () => {
  // Two taxonomies over one word: hBP03 is 283 cards, the "Elite Spark" product 244,
  // overlapping in 229. "hBP03 cards that shipped in Twin Wafers" is a real question,
  // and only both dimensions together can answer it.
  const where = buildWhere({ ...base, setCode: "hBP03", set: "ツインウエハース" });
  assert.match(where.sql, /card_number >= \?/);
  assert.match(where.sql, /EXISTS \(SELECT 1 FROM card_sets/);
  assert.match(where.sql, / AND /);
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

test("a search binds one parameter however many cards it matched", () => {
  // D1 caps a query at 100 bound parameters, so `id IN (?, ?, …)` turned every popular
  // search into a 500 — `hBP03`, `hBP01`, `ホロメン` and `エール` all failed in production
  // while `hSD01` (65 matches) worked (issue #66). The count, not the shape, was the
  // bug, so this asserts the count.
  for (const size of [1, 100, 101, 2463]) {
    const ids = Array.from({ length: size }, (_, i) => String(i + 1));
    const where = buildWhere(base, ids);
    assert.equal(where.params.length, 1, `${size} ids must bind 1 parameter`);
    assert.deepEqual(JSON.parse(where.params[0] as string), ids);
  }
});

test("the search id set is passed to json_each, not correlated against it", () => {
  // `IN (SELECT …)` here, though #40 replaced exactly that form with EXISTS for the
  // junctions. A junction has an index to correlate against; `json_each` has none, so
  // the EXISTS form rescans the array per card — measured on production over the 283
  // hBP03 ids, 169,940 rows read against 1,132 for this form.
  const where = buildWhere(base, ["1", "2"]);
  assert.match(where.sql, /id IN \(SELECT value FROM json_each\(\?\)\)/);
  assert.doesNotMatch(where.sql, /EXISTS \(SELECT 1 FROM json_each/);
});

test("a batch id lookup binds one parameter too", () => {
  // The same cap through the other door: `/api/cards/search` re-fetches the ids the
  // index returned, so `limit=101` was a 500 where `limit=100` was not.
  const ids = Array.from({ length: 200 }, (_, i) => String(i + 1));
  const built = cardsByIdsSql(ids);
  assert.equal(built.params.length, 1);
  assert.match(built.sql, /id IN \(SELECT value FROM json_each\(\?\)\)/);
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
