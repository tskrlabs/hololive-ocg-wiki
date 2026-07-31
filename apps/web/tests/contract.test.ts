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
  FILTERABLE_CARD_TYPES,
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
    // `supportStaff` was absent from v1's constants, so such a card matched no deck
    // section and silently vanished when added.
    expect(CARD_TYPES).toContain("supportStaff");

    // `unknown` was the other drift, and it is now absent here *by decision* rather
    // than by oversight: it is the scraper's fallback for a card it cannot classify,
    // and issue #19 removed it from the contract so such a card stops the build instead
    // of shipping into no deck section, counted and announced by nothing.
    expect(CARD_TYPES).not.toContain("unknown");
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

/**
 * Every enum member the filter UI renders has a string in every locale
 * ([#58](https://github.com/tskrlabs/hololive-ocg-wiki/issues/58)).
 *
 * This is the seam the generated contract cannot cover on its own, and it had **two live
 * gaps**: `cardTypes.supportStaff` and `rarity.HR` were absent from all seven locale
 * files, so both chips rendered their own i18n key — a literal `cardTypes.supportStaff` —
 * in every language, in production.
 *
 * The reason it survived is worth stating, because the tests above look like they cover
 * it and do not. The enums are *generated*, so `createEmpty()` correctly produced a
 * checkbox for each member and `filter.test.ts` asserted exactly that; the checkbox was
 * real, the test passed, and the label was a raw key. The translations are hand-written
 * and nothing compared the two halves. `make check` was green the whole time.
 *
 * `rarity.HR` is the sharper case: ADR 0001 records `HR` as one of the drift bugs the
 * generated contract was built to end, and the test above asserts `RARITIES` contains it.
 * It did. It simply had no name to render.
 *
 * A hand audit is not the answer either — it found `supportStaff` and missed `HR`.
 */
describe("the filter UI can name every enum member it offers (#58)", () => {
  const LOCALE_STRINGS = import.meta.glob("../i18n/locales/*.json", {
    eager: true,
    import: "default",
  }) as Record<string, Record<string, Record<string, string>>>;

  /** `group` is the i18n block; `members` the generated enum it must cover. */
  const COVERAGE: [string, readonly string[]][] = [
    ["cardTypes", FILTERABLE_CARD_TYPES],
    ["rarity", RARITIES],
    ["bloomLevel", BLOOM_LEVELS],
    ["colors", COLORS],
  ];

  it("has a locale file for every locale the contract declares", () => {
    // Otherwise the sweep below could pass by simply not looking at a language.
    const found = Object.keys(LOCALE_STRINGS)
      .map((path) => path.split("/").pop()!.replace(".json", ""))
      .sort();
    expect(found).toEqual([...LOCALES].sort());
  });

  for (const [group, members] of COVERAGE) {
    it(`names every ${group} in all seven locales`, () => {
      const missing: string[] = [];

      for (const [path, strings] of Object.entries(LOCALE_STRINGS)) {
        const locale = path.split("/").pop()!.replace(".json", "");
        for (const member of members) {
          if (!strings[group]?.[member]) missing.push(`${locale}.${group}.${member}`);
        }
      }

      expect(missing).toEqual([]);
    });
  }
});
