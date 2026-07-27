/**
 * The site's view of the contract.
 *
 * These are the assumptions `apps/web` makes about `@holo/schema` — that the enums it
 * renders filter UI from exist, agree with the data, and are reachable from this
 * workspace. They are cheap, and they pin the two drift bugs v1 actually shipped:
 *
 * - `CARD_BLOOM_LEVELS = ["debut","1st","2nd","spot"]` in `constants/card-data.ts`,
 *   against data that says `first`/`second`. The filter silently matched nothing.
 * - the `HR` rarity missing from the TypeScript union, leaving 24 cards unfilterable in
 *   the live UI.
 *
 * Both existed because the shape was hand-written in a constants file beside the one
 * derived from the data. Phase 5 deletes that file and imports the generated arrays; this
 * asserts the import path works and the values are the data's, which is the whole reason
 * the contract is generated (ADR 0001).
 */

import { describe, expect, it } from "vitest";
import {
  BLOOM_LEVELS,
  CARD_TYPES,
  COLORS,
  DEFAULT_LOCALE,
  FUSED_COLORS,
  LOCALES,
  MAIN_CARD_TYPES,
  OSHI_CARD_TYPES,
  RARITIES,
  YELL_CARD_TYPES,
} from "@holo/schema/enums";

describe("the generated contract is reachable from the site", () => {
  it("exposes every locale the site renders, with tc as the default", () => {
    expect(LOCALES).toEqual(["ja", "en", "tc", "id", "ko", "th", "es"]);
    expect(DEFAULT_LOCALE).toBe("tc");
  });

  it("spells bloom levels as the data does, not as v1's constants file did", () => {
    // v1: ["debut", "1st", "2nd", "spot"] — the filter matched nothing for two of four.
    expect(BLOOM_LEVELS).toEqual(["debut", "first", "second", "spot"]);
    expect(BLOOM_LEVELS).not.toContain("1st");
    expect(BLOOM_LEVELS).not.toContain("2nd");
  });

  it("includes the HR rarity that v1's union omitted", () => {
    // 24 cards were unfilterable in the live UI because this was missing.
    expect(RARITIES).toContain("HR");
  });

  it("includes the card types v1's list had drifted away from", () => {
    // `supportStaff` and `unknown` were absent from v1's constants.
    expect(CARD_TYPES).toContain("supportStaff");
    expect(CARD_TYPES).toContain("unknown");
  });

  it("partitions card types into the three deck sections without overlap", () => {
    const sections = [...OSHI_CARD_TYPES, ...MAIN_CARD_TYPES, ...YELL_CARD_TYPES];
    expect(new Set(sections).size).toBe(sections.length);
    // Every section member is a real card type — a deck section cannot route a card the
    // contract does not know about.
    for (const type of sections) expect(CARD_TYPES).toContain(type);
  });

  it("describes fused colours in terms of real colours", () => {
    // The Worker expands a colour filter through this map so `blue` also matches
    // `blue_red` (F-016). The site drops v1's separate fused checkboxes because of it,
    // so the map has to name colours the filter UI actually offers.
    for (const [fused, parts] of Object.entries(FUSED_COLORS)) {
      expect(COLORS).toContain(fused);
      for (const part of parts ?? []) expect(COLORS).toContain(part);
    }
    expect(FUSED_COLORS.blue_red).toEqual(["blue", "red"]);
  });
});
