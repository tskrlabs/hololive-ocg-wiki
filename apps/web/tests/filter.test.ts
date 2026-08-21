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
  FILTER_SECTIONS,
  FILTERABLE_COLORS,
  isActive,
  matchSetCode,
  pendingSections,
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
  it("offers every colour, with no fused symbol to exclude", () => {
    // This used to assert an exclusion list. v1 gave blue_red and white_green their own
    // checkboxes and its filter then missed those cards under `blue` (F-016); the Worker
    // answered that by expanding the query. ADR 0013 removed the codes instead — a
    // dual-colour card holds a row per badge, so it appears under each of its colours
    // with nothing excluded here and nothing expanded there.
    expect(FILTERABLE_COLORS).not.toContain("blue_red");
    expect(FILTERABLE_COLORS).not.toContain("white_green");
    expect(FILTERABLE_COLORS).toContain("blue");
    expect(FILTERABLE_COLORS).toContain("null");
    expect(FILTERABLE_COLORS).toHaveLength(COLORS.length);
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

/**
 * Per-group pending markers (D10, #36 §5).
 *
 * The rail shows all seven groups at once, so the single global dot the sheet's trigger
 * carried is too coarse: it says something is uncommitted without saying *what*. Inside a
 * sheet that was adequate, because the sheet showed one group at a time and closed on
 * Apply.
 */
describe("pendingSections", () => {
  it("reports nothing when the draft matches what is applied", () => {
    expect(pendingSections(createEmpty(), createEmpty())).toEqual([]);
  });

  it("names only the group that changed", () => {
    const applied = createEmpty();
    const draft = createEmpty();
    draft.colors.blue = true;

    expect(pendingSections(draft, applied)).toEqual(["colors"]);
  });

  it("names several at once, in panel order", () => {
    // Order matters: the markers are read down the rail, so a stable order is what makes
    // "three groups are pending" checkable at a glance.
    const applied = createEmpty();
    const draft = createEmpty();
    draft.bloomLevel.first = true;
    draft.name = "白上フブキ";
    draft.rarity.HR = true;

    expect(pendingSections(draft, applied)).toEqual(["name", "rarity", "bloomLevel"]);
  });

  it("ignores search, which applies immediately rather than through the draft", () => {
    // Search is debounced and separate from the draft filters (#36 §5); forcing it
    // through Apply would be a regression, so it can never be pending.
    const applied = createEmpty();
    const draft = createEmpty();
    draft.search = "フブキ";

    expect(pendingSections(draft, applied)).toEqual([]);
  });

  it("clears once the draft is applied", () => {
    const draft = createEmpty();
    draft.set = "hBP01";

    expect(pendingSections(draft, createEmpty())).toEqual(["set"]);
    // The applied state is a copy of the draft — which is what `applyFilters` does.
    expect(pendingSections(draft, structuredClone(draft))).toEqual([]);
  });

  it("reports a group turned back off, not just one turned on", () => {
    // Un-ticking a box that *is* applied is equally uncommitted, and a marker that only
    // appears when adding a filter would leave the removal invisible.
    const applied = createEmpty();
    applied.colors.blue = true;
    const draft = structuredClone(applied);
    draft.colors.blue = false;

    expect(pendingSections(draft, applied)).toEqual(["colors"]);
  });

  it("covers every group the panel renders", () => {
    // A section added to the filter but missed here would never show a marker — it would
    // simply be a group whose edits are silently uncommitted.
    const applied = createEmpty();
    for (const section of FILTER_SECTIONS) {
      const draft = createEmpty();
      const value = draft[section];
      if (typeof value === "string") {
        (draft[section] as string) = "changed";
      } else {
        const first = Object.keys(value)[0]!;
        (value as Record<string, boolean>)[first] = true;
      }
      expect(pendingSections(draft, applied), section).toEqual([section]);
    }
    // name, tag, setCode, set, colors, cardTypes, rarity, bloomLevel. The loop above is
    // what proves each one works; this is the canary that says a section was *added*, so
    // whoever adds the next one is made to check it renders a group too.
    expect(FILTER_SECTIONS).toHaveLength(8);
  });

  it("set code and product set are independent sections", () => {
    // They are different taxonomies over the same word "set": `setCode` is the card
    // number's prefix (hBP03, 283 cards), `set` is the product a card shipped in
    // ("Elite Spark", 244 cards, overlapping in 229). Setting one must not touch the
    // other — a single control answering both questions is what this rules out.
    const applied = createEmpty();
    const draft = createEmpty();
    draft.setCode = "hBP03";

    expect(pendingSections(draft, applied)).toEqual(["setCode"]);
    expect(draft.set).toBe("");
  });

  it("the set code is sent as set_code, the API's spelling", () => {
    // The query string is snake_case and the filter shape is camelCase; sending `setCode`
    // would be silently ignored by the Worker, which is the worst shape — a filter that
    // looks applied and constrains nothing.
    const filter = createEmpty();
    filter.setCode = "hBP03";

    const params = toApiParams(filter);
    expect(params.set_code).toBe("hBP03");
    expect(params.setCode).toBeUndefined();
  });
});

describe("recognising a typed set code", () => {
  const CODES = ["hBP01", "hBP03", "hSD01", "hPR", "hY01"];

  it("matches a whole code, whatever the casing", () => {
    // The index is already case-insensitive — `hbp03` finds hBP03 cards today — so the
    // routing rule must be too, or typing lowercase would behave differently from
    // typing it in the printed form.
    expect(matchSetCode("hBP03", CODES)).toBe("hBP03");
    expect(matchSetCode("hbp03", CODES)).toBe("hBP03");
    expect(matchSetCode("  hBP03  ", CODES)).toBe("hBP03");
  });

  it("leaves a partial or unknown code to free-text search", () => {
    // `hBP` is a prefix of nine codes and `hBP3` of none. Routing either would turn a
    // half-typed query into a confident empty result; as searches they keep behaving
    // exactly as they do today.
    expect(matchSetCode("hBP", CODES)).toBeUndefined();
    expect(matchSetCode("hBP3", CODES)).toBeUndefined();
    expect(matchSetCode("hBP99", CODES)).toBeUndefined();
    expect(matchSetCode("", CODES)).toBeUndefined();
  });

  it("does not route a full card number", () => {
    // `hBP03-004` is a card, not a set — it stays a search, which finds that card.
    expect(matchSetCode("hBP03-004", CODES)).toBeUndefined();
  });

  it("routes nothing when the artifact has no codes", () => {
    // An artifact published before set codes existed. Every query stays a search rather
    // than the rule silently matching nothing in a way that looks like a broken filter.
    expect(matchSetCode("hBP03", [])).toBeUndefined();
  });
});
