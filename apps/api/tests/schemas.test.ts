/**
 * Input validation at the untrusted boundary (D7).
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  batchParamSchema,
  filterQuerySchema,
  MAX_BATCH,
  searchQuerySchema,
} from "../src/lib/schemas.ts";

test("an unknown locale degrades to the default instead of failing", () => {
  // The site's i18n uses URL prefixes, so a stale link (v1 accepted `sc`, which the
  // data never had) must not turn a whole page into an error.
  assert.equal(searchQuerySchema.parse({ q: "x", locale: "sc" }).locale, "tc");
  assert.equal(searchQuerySchema.parse({ q: "x" }).locale, "tc");
  assert.equal(searchQuerySchema.parse({ q: "x", locale: "en" }).locale, "en");
});

test("an unknown enum value is rejected outright", () => {
  // Unlike locale, a bad colour is a broken client rather than a stale link, and
  // silently dropping it would return results the user did not ask for.
  assert.throws(() => filterQuerySchema.parse({ colors: "chartreuse" }));
});

test("comma-separated params split, and a trailing comma is not an error", () => {
  assert.deepEqual(filterQuerySchema.parse({ colors: "blue,red" }).colors, ["blue", "red"]);
  // A client that joined an array can leave a trailing comma; that is not a request
  // for a card with no colour.
  assert.deepEqual(filterQuerySchema.parse({ colors: "blue," }).colors, ["blue"]);
  assert.equal(filterQuerySchema.parse({}).colors, undefined);
});

test("out-of-range numbers fall back rather than failing", () => {
  assert.equal(filterQuerySchema.parse({ limit: "9999" }).limit, 50);
  assert.equal(filterQuerySchema.parse({ page: "0" }).page, 1);
  assert.equal(filterQuerySchema.parse({ page: "notanumber" }).page, 1);
  assert.equal(filterQuerySchema.parse({ limit: "20" }).limit, 20);
});

test("skip_count is only true for the literal string", () => {
  assert.equal(filterQuerySchema.parse({ skip_count: "true" }).skip_count, true);
  assert.equal(filterQuerySchema.parse({ skip_count: "false" }).skip_count, false);
  assert.equal(filterQuerySchema.parse({}).skip_count, false);
});

test("a batch over the cap is rejected, never truncated", () => {
  // v1 sliced to the first 50 and returned them silently, so a deck longer than 50
  // cards rendered short with no error.
  const ids = Array.from({ length: MAX_BATCH + 1 }, (_, i) => String(i + 1)).join(",");
  const result = batchParamSchema.safeParse(ids);
  assert.equal(result.success, false);
  assert.match(result.error!.issues[0]!.message, /too many values/);

  assert.equal(
    batchParamSchema.parse(
      Array.from({ length: MAX_BATCH }, (_, i) => String(i + 1)).join(","),
    ).length,
    MAX_BATCH,
  );
});

test("batch values must be alphanumeric", () => {
  assert.deepEqual(batchParamSchema.parse("1,2,3"), ["1", "2", "3"]);
  assert.deepEqual(batchParamSchema.parse("hBP01-104,hSD01_001"), [
    "hBP01-104",
    "hSD01_001",
  ]);
  for (const bad of ["1;DROP TABLE cards", "1,2'", "a b"]) {
    assert.equal(batchParamSchema.safeParse(bad).success, false, `accepted ${bad}`);
  }
  // An empty list is a client bug, not an empty result.
  assert.equal(batchParamSchema.safeParse(",,,").success, false);
});

test("search text is trimmed and capped", () => {
  assert.equal(searchQuerySchema.parse({ q: "  フブキ  " }).q, "フブキ");
  // Blank becomes undefined so the route can answer without touching D1.
  assert.equal(searchQuerySchema.parse({ q: "   " }).q, undefined);
  assert.throws(() => searchQuerySchema.parse({ q: "x".repeat(501) }));
});
