/**
 * Parity test: the TypeScript `localize()` must reproduce the Python one exactly.
 *
 * The golden files are written by `scripts/golden.py` from the pydantic reference
 * implementation. This asserts the TypeScript port produces byte-identical output for
 * every fixture card in every locale.
 *
 * This is what makes "the contract is defined once" true for *behaviour* and not just
 * for field names. The two implementations exist because the pipeline is Python (D3)
 * and the Worker is TypeScript (D8 projects at request time); this test is the seam.
 *
 * If it fails: the two implementations disagree. Fix the port — or, if the Python side
 * changed deliberately, run `make golden` and review the diff before committing.
 *
 * Run with `node --test tests/*.test.ts` (Node 22.6+ strips types natively — no
 * ts-node, no vitest, no build step).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { localize, cardImage } from "../src/localize.ts";
import { LOCALES } from "../dist/enums.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = join(HERE, "..");
const REPO_ROOT = join(PACKAGE_ROOT, "..", "..");

const fixtures = JSON.parse(
  readFileSync(join(REPO_ROOT, "fixtures", "cards.json"), "utf-8"),
);

/**
 * Recursively sort object keys so comparison is order-independent.
 * The golden files are written with sort_keys=True; JS object literal order differs.
 */
function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value as Record<string, unknown>)
        .sort()
        .map((key) => [key, sortKeys((value as Record<string, unknown>)[key])]),
    );
  }
  return value;
}

/** Drop undefined-valued keys, matching Python's `exclude_none=True`. */
function prune(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(prune);
  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (item !== undefined && item !== null) out[key] = prune(item);
    }
    return out;
  }
  return value;
}

for (const locale of LOCALES) {
  test(`localize() matches the Python reference for locale "${locale}"`, () => {
    const golden = JSON.parse(
      readFileSync(join(PACKAGE_ROOT, "golden", `localized-${locale}.json`), "utf-8"),
    );

    assert.equal(
      fixtures.cards.length,
      golden.length,
      "fixture and golden card counts differ — run `make golden`",
    );

    for (const [index, card] of fixtures.cards.entries()) {
      const actual = sortKeys(prune(localize(card, locale)));
      const expected = sortKeys(golden[index]);
      assert.deepStrictEqual(
        actual,
        expected,
        `card ${card.id} (${card.card_number}) diverges in locale "${locale}"`,
      );
    }
  });
}

// Merge rule 2 — arts pair by index, tolerating a short translated list.
//
// This used to key on card 446 (hSD03-009: 2 arts, 0 `en` translations). The
// field-level translation cache has since filled it in (F-004), and a census over the
// whole card set finds zero cards with an arts-length mismatch in any locale — so the
// branch has no natural cover left in the data at all.
//
// The synthetic fixture is what covers it now, in both implementations. See
// SYNTHETIC_CARD in packages/schema/scripts/build_fixtures.py and issue #16.
test("arts with no translation keep their costs (synthetic short-arts card)", () => {
  const card = fixtures.cards.find((c: { id: string }) => c.id === "9000001");
  assert.ok(card, "synthetic short-arts fixture missing");
  assert.equal(card.arts.length, 2);
  assert.deepEqual(card.translations.en.arts, []);

  const result = localize(card, "en");
  const arts = result.arts ?? [];
  assert.equal(arts.length, 2, "arts must survive an empty translation list");
  assert.equal(arts[0]?.name, undefined);
  assert.deepEqual(arts[0]?.cost_types, card.arts[0].cost_types);

  // A partially-translated list pairs by index: `tc` has 1 translation for 2 arts.
  const partial = localize(card, "tc").arts ?? [];
  assert.equal(partial.length, 2);
  assert.equal(partial[0]?.name, "技能一");
  assert.equal(partial[1]?.name, undefined, "the unpaired art keeps costs, loses name");
});

test("missing locale falls back to the source locale", () => {
  const card = structuredClone(
    fixtures.cards.find((c: { id: string }) => c.id === "446"),
  );
  delete card.translations.en;
  const result = localize(card, "en");
  assert.equal(result.locale, "ja");
  assert.equal(result.name, card.translations.ja.name);
});

test("fused colour codes survive the projection", () => {
  const card = fixtures.cards.find((c: { id: string }) => c.id === "2263");
  assert.deepStrictEqual(card.color_codes, ["blue_red"]);
  assert.deepStrictEqual(localize(card, "ja").color_codes, ["blue_red"]);
});

test("cardImage composes a URL from the key (D9)", () => {
  assert.equal(
    cardImage("default/hBP01-028_C_02", "https://img.example.com"),
    "https://img.example.com/default/hBP01-028_C_02.webp",
  );
  assert.equal(
    cardImage("a/b", "https://img.example.com/"),
    "https://img.example.com/a/b.webp",
  );
});
