/**
 * The deck's rules and its wire format (Candidate 03, ADR 0006 Q5 and Q11).
 *
 * Two things are pinned here, and the second matters more than the first.
 *
 * **The rules** — 1 oshi / 50 main / 20 yell — had no home in v1 at all. They were magic
 * numbers typed into templates, the status-colour ternary was copied six times across two
 * files, and the store enforced nothing: `addCardToDeck` pushed unconditionally, so a
 * 60-card main deck was reachable and only the badge turned red.
 *
 * **The wire format was frozen** (Q11), and **ADR 0014 amended it once** — the only time,
 * and for the one reason the freeze anticipated. `localStorage["hololive-ocg-wiki-decks"]`
 * holds a `Deck[]` in every existing user's browser, and the base64 deck code lives in
 * Discord messages that never expire. A failure here is not a style regression — it is
 * someone's saved decks, or a link that has already been shared.
 *
 * What changed: a card reference is an `image_key`, not the official site's id, because
 * the site reuses its ids (#83) and an id-keyed deck silently resolved to the *wrong*
 * cards after a renumbering. Field names, the count-map form and the base64 envelope are
 * untouched; `cardRefFormat` is additive, and legacy codes are translated on decode
 * forever rather than being rewritten.
 */

import { describe, expect, it } from "vitest";

import * as deckCode from "../app/composables/deckCode";
import { refForId } from "../app/composables/cardRefs";
import {
  SECTIONS,
  addToSection,
  copiesOf,
  isDeckLegal,
  removeFromSection,
  sectionByKey,
  sectionForCardType,
  sectionStatus,
} from "../app/composables/deckSections";
import type { Deck } from "../app/types/deck";

const deck = (over: Partial<Deck> = {}): Deck => ({
  id: "test-deck",
  name: "テストデッキ",
  author: "someone",
  oshiCardIds: [],
  mainCardIds: [],
  yellCardIds: [],
  version: "0.9.0",
  ...over,
});

describe("sectionForCardType", () => {
  it("routes each card type to exactly one section", () => {
    expect(sectionForCardType("oshiCharacter")?.key).toBe("oshi");
    expect(sectionForCardType("supportCheer")?.key).toBe("yell");
    expect(sectionForCardType("character")?.key).toBe("main");
    // v1's hand-written list omitted this one, so such a card matched no section and
    // silently vanished when added.
    expect(sectionForCardType("supportStaff")?.key).toBe("main");
  });

  it("refuses to place a non-card", () => {
    // `rulesNotice` is not a card at all — it is a format-legality notice the official
    // site publishes into its card list (F-020) — so no section can ever hold it. This
    // is what makes the deck builder structurally unable to add one.
    //
    // It used to be `unknown` here, the scraper's fallback for a card it could not
    // classify. That value left `CardTypeCode` in issue #19, so `rulesNotice` is now
    // the only type in no section and the null path needs it to stay exercised.
    expect(sectionForCardType("rulesNotice")).toBeNull();
  });
});

describe("the section limits", () => {
  it("are the game's: 1 oshi, 50 main, 20 yell", () => {
    expect(sectionByKey("oshi").limit).toBe(1);
    expect(sectionByKey("main").limit).toBe(50);
    expect(sectionByKey("yell").limit).toBe(20);
  });

  it("are enforced on add, which v1 never did", () => {
    const main = sectionByKey("main");
    const full = deck({ mainCardIds: Array<string>(50).fill("1") });

    const result = addToSection(full, main, "2", 5);
    expect(result.added).toBe(0);
    expect(result.ids).toHaveLength(50);
  });

  it("adds only up to the limit when asked for more", () => {
    const yell = sectionByKey("yell");
    const almost = deck({ yellCardIds: Array<string>(18).fill("1") });

    const result = addToSection(almost, yell, "2", 5);
    expect(result.added).toBe(2);
    expect(result.ids).toHaveLength(20);
  });
});

describe("sectionStatus", () => {
  it("distinguishes empty, partial, complete and over", () => {
    const oshi = sectionByKey("oshi");
    expect(sectionStatus(deck(), oshi)).toBe("empty");
    expect(sectionStatus(deck({ oshiCardIds: ["1"] }), oshi)).toBe("complete");
    expect(sectionStatus(deck({ oshiCardIds: ["1", "2"] }), oshi)).toBe("over");

    const main = sectionByKey("main");
    expect(sectionStatus(deck({ mainCardIds: ["1"] }), main)).toBe("partial");
  });

  it("can report `over` for a deck loaded from storage", () => {
    // The limits are enforced on add, but a deck imported from a code or written by an
    // older build can still exceed them — the badge has to be able to say so.
    const over = deck({ mainCardIds: Array<string>(60).fill("1") });
    expect(sectionStatus(over, sectionByKey("main"))).toBe("over");
  });
});

describe("removeFromSection", () => {
  it("removes the requested number of copies, from the end", () => {
    const d = deck({ mainCardIds: ["1", "2", "1", "3", "1"] });
    const { ids, removed } = removeFromSection(d, sectionByKey("main"), "1", 2);
    expect(removed).toBe(2);
    expect(ids).toEqual(["1", "2", "3"]);
  });

  it("removes every copy when no amount is given", () => {
    const d = deck({ mainCardIds: ["1", "2", "1"] });
    const { ids, removed } = removeFromSection(d, sectionByKey("main"), "1");
    expect(removed).toBe(2);
    expect(ids).toEqual(["2"]);
  });

  it("is a no-op for a card that is not there", () => {
    const d = deck({ mainCardIds: ["1"] });
    const { ids, removed } = removeFromSection(d, sectionByKey("main"), "9");
    expect(removed).toBe(0);
    expect(ids).toEqual(["1"]);
  });
});

describe("copiesOf and isDeckLegal", () => {
  it("counts duplicates within a section", () => {
    const d = deck({ mainCardIds: ["1", "1", "2"] });
    expect(copiesOf(d, sectionByKey("main"), "1")).toBe(2);
  });

  it("calls a deck legal only when every section is exactly at its limit", () => {
    expect(isDeckLegal(deck())).toBe(false);
    const legal = deck({
      oshiCardIds: ["1"],
      mainCardIds: Array<string>(50).fill("2"),
      yellCardIds: Array<string>(20).fill("3"),
    });
    expect(isDeckLegal(legal)).toBe(true);
  });
});

describe("removing a slot with no card behind it (ADR 0014)", () => {
  it("finds the reference without being told its section", () => {
    // Every other mutation picks a section via `sectionForCardType`, which needs a Card.
    // An unresolved slot has none, so removal has to search. Without this a withdrawn
    // card is stuck in the deck permanently.
    const held = deck({
      oshiCardIds: ["hSD01/hSD01-001_OSR"],
      mainCardIds: ["hEB01/hBP01-051_UR_02", "x", "hEB01/hBP01-051_UR_02"],
      yellCardIds: ["y"],
    });

    const section = sectionByKey("main");
    const { ids, removed } = removeFromSection(
      held,
      section,
      "hEB01/hBP01-051_UR_02",
    );

    expect(removed).toBe(2);
    expect(ids).toEqual(["x"]);
  });

  it("leaves the other sections alone", () => {
    // The scan runs across all three, so a reference that is not in a section must come
    // back untouched rather than emptying it.
    const held = deck({ mainCardIds: ["a", "b"], yellCardIds: ["c"] });
    const { ids, removed } = removeFromSection(held, sectionByKey("yell"), "a");

    expect(removed).toBe(0);
    expect(ids).toEqual(["c"]);
  });
});

describe("the deck code — a frozen format (Q11)", () => {
  it("round-trips a deck", () => {
    // References are `image_key`s now (ADR 0014), and the deck carries the format it is
    // written in. A round trip must preserve both.
    const original = deck({
      oshiCardIds: ["hSD01/hSD01-001_OSR"],
      mainCardIds: ["hBP01/hBP01-002_R", "hBP01/hBP01-002_R", "hBP01/hBP01-003_C"],
      yellCardIds: ["hBP01/hBP01-004_C"],
      cardRefFormat: "image-key",
    });
    const restored = deckCode.decode(deckCode.encode(original));
    expect(restored).toEqual(original);
  });

  it("survives a non-Latin-1 deck name", () => {
    // `btoa` throws on anything outside Latin-1, which is why the encoder wraps the JSON
    // in `encodeURIComponent` first. Deck names are routinely Japanese.
    const original = deck({ name: "白上フブキ最強デッキ🦊", oshiCardIds: ["1"] });
    expect(deckCode.decode(deckCode.encode(original))?.name).toBe(original.name);
  });

  it("emits v1's payload shape, plus the format marker (ADR 0014)", () => {
    // Field names and the count-map form are still v1's — those never move. `cardRefFormat`
    // is the one addition, and it is additive on purpose: v1 ignores an unknown key, so a
    // code written here still decodes there. What v1 cannot do is *interpret* image_keys,
    // which is moot now that v1 is archived.
    const encoded = deckCode.encode(
      deck({
        oshiCardIds: ["hSD01/hSD01-007_OSR"],
        mainCardIds: ["hBP01/hBP01-008_R", "hBP01/hBP01-008_R"],
        yellCardIds: [],
        cardRefFormat: "image-key",
      }),
    );
    const payload = JSON.parse(decodeURIComponent(atob(encoded)));

    expect(Object.keys(payload).sort()).toEqual(
      [
        "author",
        "cardRefFormat",
        "id",
        "mainCards",
        "name",
        "oshiCards",
        "version",
        "yellCards",
      ].sort(),
    );
    expect(payload.cardRefFormat).toBe("image-key");
    expect(payload.oshiCards).toEqual({ "hSD01/hSD01-007_OSR": 1 });
    expect(payload.mainCards).toEqual({ "hBP01/hBP01-008_R": 2 });
    expect(payload.yellCards).toEqual({});
  });

  it("decodes a code produced by v1", () => {
    // Built by hand in v1's format, not by our encoder — so this fails if the reader
    // drifts, which is the whole point.
    const v1Payload = {
      id: "my-deck-1750000000000",
      name: "shared deck",
      oshiCards: { "199": 1 },
      mainCards: { "564": 3, "809": 1 },
      yellCards: { "810": 2 },
    };
    const code = btoa(encodeURIComponent(JSON.stringify(v1Payload)));

    const decoded = deckCode.decode(code);
    expect(decoded?.id).toBe("my-deck-1750000000000");
    // The ids are translated to `image_key`s on the way in (ADR 0014): a v1 code names
    // cards by ids the official site has since handed to *different* cards, so reading it
    // verbatim is what would corrupt the deck. Counts and order survive.
    expect(decoded?.oshiCardIds).toEqual([refForId("199")]);
    expect(decoded?.mainCardIds).toEqual([
      refForId("564"),
      refForId("564"),
      refForId("564"),
      refForId("809"),
    ]);
    expect(decoded?.yellCardIds).toEqual([refForId("810"), refForId("810")]);
    // v1 codes carry no `version`; the reader must not choke on that.
    expect(decoded?.version).toBe("");
    expect(decoded?.cardRefFormat).toBe("image-key");
  });

  it("returns null for junk rather than throwing", () => {
    // The input is a URL segment someone pasted — malformed is ordinary, not exceptional.
    expect(deckCode.decode("not-base64!!")).toBeNull();
    expect(deckCode.decode(btoa("plain text"))).toBeNull();
    expect(deckCode.decode(btoa(encodeURIComponent('{"no":"id"}')))).toBeNull();
    expect(deckCode.decode("")).toBeNull();
  });
});

describe("the stored shape", () => {
  it("still uses v1's field names", () => {
    // The refactor is in-memory only. These three names are what is in every user's
    // localStorage and inside every shared code.
    expect(SECTIONS.map((section) => section.field)).toEqual([
      "oshiCardIds",
      "mainCardIds",
      "yellCardIds",
    ]);
  });
});
