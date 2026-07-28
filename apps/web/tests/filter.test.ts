/**
 * The filter module's pure core (Candidate 02, ADR 0006 Q5).
 *
 * `createEmpty`, `isActive` and `toApiParams` are plain functions with no Vue and no DOM,
 * which is the point of the refactor — v1's equivalents were welded into a composable and
 * could only be exercised by rendering the filter panel.
 *
 * The bugs these pin are ones v1 actually shipped: two of four bloom filters matched
 * nothing because the enum was spelled twice and the copies disagreed, and 24 cards were
 * unfilterable because a rarity was missing from one of them.
 */

import { describe, expect, it } from "vitest";
import {
  BLOOM_LEVELS,
  COLORS,
  FILTERABLE_CARD_TYPES,
  NON_CARD_TYPES,
  RARITIES,
} from "@holo/schema/enums";

import {
  createEmpty,
  FILTERABLE_COLORS,
  isActive,
  toApiParams,
} from "../app/composables/filter-states";

describe("createEmpty", () => {
  it("covers every enum member, so no filter can be missing a checkbox", () => {
    const filter = createEmpty();
    expect(Object.keys(filter.colors).sort()).toEqual([...COLORS].sort());
    expect(Object.keys(filter.cardTypes).sort()).toEqual(
      [...FILTERABLE_CARD_TYPES].sort(),
    );
    expect(Object.keys(filter.rarity).sort()).toEqual([...RARITIES].sort());
    expect(Object.keys(filter.bloomLevel).sort()).toEqual([...BLOOM_LEVELS].sort());
  });

  it("offers no checkbox for a non-card type", () => {
    // Rules notices are served by /api/notices and never appear in an /api/cards
    // response, so a checkbox for one would always return zero results — the
    // always-dead-UI shape of F-019. See F-020.
    const filter = createEmpty();
    for (const nonCard of NON_CARD_TYPES) {
      expect(filter.cardTypes).not.toHaveProperty(nonCard);
    }
    expect(NON_CARD_TYPES.length).toBeGreaterThan(0);
  });

  it("starts with everything off", () => {
    const filter = createEmpty();
    expect(isActive(filter)).toBe(false);
    expect(toApiParams(filter)).toEqual({});
  });

  it("returns a fresh object each call, not a shared one", () => {
    const a = createEmpty();
    const b = createEmpty();
    a.colors.blue = true;
    expect(b.colors.blue).toBe(false);
  });
});

describe("FILTERABLE_COLORS", () => {
  it("omits the fused symbols, which the Worker expands instead", () => {
    // v1 gave blue_red and white_green their own checkboxes, and its colour filter then
    // missed those cards under `blue` and `red` (F-016). The Worker expands through
    // FUSED_COLORS now, so a separate checkbox would be a second, worse path.
    expect(FILTERABLE_COLORS).not.toContain("blue_red");
    expect(FILTERABLE_COLORS).not.toContain("white_green");
    expect(FILTERABLE_COLORS).toContain("blue");
    expect(FILTERABLE_COLORS).toContain("null");
    expect(FILTERABLE_COLORS).toHaveLength(COLORS.length - 2);
  });
});

describe("isActive", () => {
  it("ignores whitespace-only text", () => {
    const filter = createEmpty();
    filter.name = "   ";
    expect(isActive(filter)).toBe(false);
  });

  it("is true for any set flag or any text", () => {
    for (const mutate of [
      (f: ReturnType<typeof createEmpty>) => (f.colors.blue = true),
      (f: ReturnType<typeof createEmpty>) => (f.rarity.HR = true),
      (f: ReturnType<typeof createEmpty>) => (f.bloomLevel.first = true),
      (f: ReturnType<typeof createEmpty>) => (f.cardTypes.supportStaff = true),
      (f: ReturnType<typeof createEmpty>) => (f.search = "フブキ"),
    ]) {
      const filter = createEmpty();
      mutate(filter);
      expect(isActive(filter)).toBe(true);
    }
  });
});

describe("toApiParams", () => {
  it("omits empty sections rather than sending them blank", () => {
    // An empty `colors=` would be a request for cards with no colour; an absent one is
    // "no constraint". The API treats them differently.
    const filter = createEmpty();
    filter.colors.blue = true;
    expect(toApiParams(filter)).toEqual({ colors: ["blue"] });
  });

  it("trims text and drops whitespace-only values", () => {
    const filter = createEmpty();
    filter.name = "  白上フブキ  ";
    filter.tag = "   ";
    expect(toApiParams(filter)).toEqual({ name: "白上フブキ" });
  });

  it("sends only the flags that are on", () => {
    const filter = createEmpty();
    filter.rarity.HR = true;
    filter.rarity.SR = true;
    filter.bloomLevel.first = true;
    const params = toApiParams(filter);
    expect((params.rarity as string[]).sort()).toEqual(["HR", "SR"]);
    // `first`, not `1st` — v1's constants file said the latter and the filter silently
    // matched nothing.
    expect(params.bloomLevel).toEqual(["first"]);
  });

  it("emits every section together", () => {
    const filter = createEmpty();
    filter.search = "hBP01";
    filter.set = "hBP01";
    filter.colors.white = true;
    filter.cardTypes.oshiCharacter = true;
    expect(toApiParams(filter)).toEqual({
      search: "hBP01",
      set: "hBP01",
      colors: ["white"],
      cardTypes: ["oshiCharacter"],
    });
  });
});
