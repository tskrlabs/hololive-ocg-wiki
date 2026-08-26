/**
 * The id → `image_key` migration (ADR 0014, issue #83).
 *
 * **What these protect is someone's saved deck.** On 2026-08-26 the official list inserted
 * 36 cards mid-sequence and renumbered 82 existing ones. Card ids come from the site's own
 * `?id=` hrefs, so a deck saved before that date names cards by ids that now belong to
 * different cards.
 *
 * The failure being prevented is **silent**: a renumbered id still resolves, just to the
 * wrong card. There is no error for a user to notice and no empty slot to see. A
 * regression here would not throw — it would quietly hand someone a deck they did not
 * build, which is why the fixtures below are real ids from the real renumbering rather
 * than invented ones.
 */

import { describe, expect, it } from "vitest";

import {
  formatOf,
  isUnresolved,
  migrateDeck,
  migrateDecks,
  refForId,
  unresolvedId,
} from "../app/composables/cardRefs";
import * as deckCode from "../app/composables/deckCode";
import type { Deck } from "../app/types/deck";

/** id 2582 was `hBP01-051_UR_02`; after the renumbering that id is `hEB01-007_SR`. */
const POISONED_ID = "2582";
const POISONED_KEY = "hEB01/hBP01-051_UR_02";

/** id 1 never moved — the common case, and it must migrate just the same. */
const STABLE_ID = "1";
const STABLE_KEY = "hSD01/hSD01-001_OSR";

const deck = (over: Partial<Deck> = {}): Deck => ({
  id: "test-deck",
  name: "テストデッキ",
  oshiCardIds: [],
  mainCardIds: [],
  yellCardIds: [],
  version: "0.9.0",
  ...over,
});

describe("format detection", () => {
  it("treats absent and empty as the legacy id form", () => {
    // `decode()` has always defaulted a missing version to "", so codes in that state are
    // already in the wild; both must read as legacy or they would never migrate.
    expect(formatOf(undefined)).toBe("id");
    expect(formatOf("")).toBe("id");
  });

  it("recognises the new form", () => {
    expect(formatOf("image-key")).toBe("image-key");
  });
});

describe("reference translation", () => {
  it("maps a renumbered id to the card it meant, not the card that id is now", () => {
    expect(refForId(POISONED_ID)).toBe(POISONED_KEY);
  });

  it("maps an id that never moved", () => {
    expect(refForId(STABLE_ID)).toBe(STABLE_KEY);
  });

  it("marks an unknown id rather than guessing", () => {
    const ref = refForId("999999");
    expect(isUnresolved(ref)).toBe(true);
    expect(unresolvedId(ref)).toBe("999999");
  });
});

describe("deck migration", () => {
  it("converts every section", () => {
    const { deck: migrated, converted } = migrateDeck(
      deck({
        oshiCardIds: [STABLE_ID],
        mainCardIds: [POISONED_ID, POISONED_ID],
        yellCardIds: [STABLE_ID],
      }),
    );

    expect(converted).toBe(true);
    expect(migrated.cardRefFormat).toBe("image-key");
    expect(migrated.oshiCardIds).toEqual([STABLE_KEY]);
    expect(migrated.mainCardIds).toEqual([POISONED_KEY, POISONED_KEY]);
    expect(migrated.yellCardIds).toEqual([STABLE_KEY]);
  });

  it("preserves duplicate counts, which are how a deck holds copies", () => {
    const { deck: migrated } = migrateDeck(
      deck({ mainCardIds: [POISONED_ID, POISONED_ID, STABLE_ID] }),
    );
    expect(migrated.mainCardIds).toHaveLength(3);
  });

  it("is idempotent", () => {
    // The load path runs at every mount. A second pass must not re-translate, which would
    // treat each image_key as an id, find nothing, and turn a healthy deck into a deck of
    // unresolved markers.
    const once = migrateDeck(deck({ mainCardIds: [POISONED_ID] })).deck;
    const twice = migrateDeck(once);

    expect(twice.converted).toBe(false);
    expect(twice.deck.mainCardIds).toEqual([POISONED_KEY]);
  });

  it("reports how many decks changed, so the toast can be honest", () => {
    const legacy = deck({ id: "a", mainCardIds: [STABLE_ID] });
    const already = migrateDeck(deck({ id: "b", mainCardIds: [STABLE_ID] })).deck;

    const { convertedCount } = migrateDecks([legacy, already]);
    expect(convertedCount).toBe(1);
  });

  it("keeps an unresolvable card's slot instead of dropping it", () => {
    // A dropped card in a 50-card deck is invisible, and only the user knows what was
    // meant. The slot survives so they can see it and replace it.
    const { deck: migrated } = migrateDeck(
      deck({ mainCardIds: [STABLE_ID, "999999"] }),
    );
    expect(migrated.mainCardIds).toHaveLength(2);
    expect(isUnresolved(migrated.mainCardIds[1]!)).toBe(true);
  });
});

describe("deck codes", () => {
  it("translates a legacy code on decode", () => {
    // The code a v1 user shared: no cardRefFormat, ids inside.
    const legacy = btoa(
      encodeURIComponent(
        JSON.stringify({
          id: "shared",
          oshiCards: {},
          mainCards: { [POISONED_ID]: 2 },
          yellCards: {},
        }),
      ),
    );

    const decoded = deckCode.decode(legacy);
    expect(decoded?.mainCardIds).toEqual([POISONED_KEY, POISONED_KEY]);
    expect(decoded?.cardRefFormat).toBe("image-key");
  });

  it("leaves a new-form code alone", () => {
    const current = deckCode.encode(
      deck({ mainCardIds: [POISONED_KEY], cardRefFormat: "image-key" }),
    );
    expect(deckCode.decode(current)?.mainCardIds).toEqual([POISONED_KEY]);
  });

  it("round-trips", () => {
    const original = deck({
      mainCardIds: [POISONED_KEY, STABLE_KEY],
      cardRefFormat: "image-key",
    });
    const decoded = deckCode.decode(deckCode.encode(original));
    expect(decoded?.mainCardIds).toEqual(original.mainCardIds);
  });

  it("still rejects a malformed code", () => {
    expect(deckCode.decode("not base64 at all")).toBeNull();
  });
});
