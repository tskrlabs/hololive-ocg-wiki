/**
 * Deck serialisation — the **frozen** compatibility boundary (ADR 0006, Q11).
 *
 * Two formats live outside our control and must never change:
 *
 * 1. `localStorage["hololive-ocg-wiki-decks"]` — a `Deck[]` in every existing user's
 *    browser, written by v1.
 * 2. The shared deck-code URL — base64 of a count-map form, pasted into Discord messages
 *    that never expire.
 *
 * Candidate 03 restructures the deck **in memory** into sections. This module is the seam
 * where that internal shape meets the stored one, so the refactor cannot strand data
 * already in the wild.
 *
 * **The premise that made the v1 → v2 cutover safe has since failed** (ADR 0014, #83).
 * This file used to argue that a card `id` is the official site's own detail-page id
 * rather than a database rowid, so ids in an old deck code still resolve. They do still
 * resolve — that turned out to be the danger, not the safety. On 2026-08-26 the site
 * renumbered 82 cards, so those ids now resolve to the *wrong* cards, silently.
 *
 * References are therefore `image_key` from that date on, and an id-form code is
 * translated on decode. The format field is `cardRefFormat`, not `version`; both formats
 * stay readable forever, because the codes are in messages we do not control.
 *
 * Extracted as pure functions, per the review's "other notes": v1 welded this transform
 * into the state composable alongside `window`, `localStorage` and `useI18n`, so the
 * round trip could not be tested without a browser. Here it is `encode`/`decode` over
 * plain values.
 */

import type { Deck } from "~/types/deck";
import { formatOf, refForId } from "~/composables/cardRefs";

/**
 * A deck as it appears inside a shared code.
 *
 * Note the field names differ from `Deck`'s — `oshiCards`, not `oshiCardIds` — and the
 * values are `{id: count}` maps rather than arrays with repeats. Both are v1's choices,
 * and both are load-bearing: a code built by v1 must decode here, and a code built here
 * must decode in v1 for as long as both are live.
 */
export type EncodedDeck = {
  id: string;
  name?: string;
  author?: string;
  oshiCards: Record<string, number>;
  mainCards: Record<string, number>;
  yellCards: Record<string, number>;
  version?: string;
  /**
   * Which identifier the three card maps are written in (ADR 0014). Absent means `"id"`,
   * which is every code written before 2026-08-26 and every code v1 ever produced.
   */
  cardRefFormat?: "id" | "image-key";
};

/** `["1","1","2"]` → `{"1": 2, "2": 1}`. */
export function compressCardIds(cardIds: string[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const id of cardIds) counts[id] = (counts[id] ?? 0) + 1;
  return counts;
}

/** `{"1": 2, "2": 1}` → `["1","1","2"]`. */
export function expandCardIds(compressed: Record<string, number>): string[] {
  const expanded: string[] = [];
  for (const [id, count] of Object.entries(compressed ?? {})) {
    for (let i = 0; i < count; i++) expanded.push(id);
  }
  return expanded;
}

/**
 * A deck → its shareable code.
 *
 * `btoa(encodeURIComponent(json))` exactly as v1 did. The `encodeURIComponent` step is
 * not decoration: `btoa` throws on any character outside Latin-1, and deck names are
 * routinely Japanese.
 */
export function encode(deck: Deck): string {
  const payload: EncodedDeck = {
    id: deck.id,
    name: deck.name,
    author: deck.author,
    oshiCards: compressCardIds(deck.oshiCardIds),
    mainCards: compressCardIds(deck.mainCardIds),
    yellCards: compressCardIds(deck.yellCardIds),
    version: deck.version,
    cardRefFormat: formatOf(deck.cardRefFormat),
  };
  return btoa(encodeURIComponent(JSON.stringify(payload)));
}

/**
 * A shareable code → a deck, or `null` if it is not one.
 *
 * Returns `null` rather than throwing: the input is a URL segment a user pasted, so
 * malformed is an ordinary case, not an exceptional one. v1 returned `false` and logged
 * to the console.
 */
export function decode(code: string): Deck | null {
  try {
    const parsed = JSON.parse(decodeURIComponent(atob(code))) as Partial<EncodedDeck>;
    if (!parsed || typeof parsed.id !== "string") return null;

    // A code is not ours to rewrite — it lives in a Discord message that never expires —
    // so an id-form code is translated on the way in, every time, forever (ADR 0014).
    // This is why the mapping is permanent rather than a migration artifact with an end
    // date: the last id-form code will be pasted long after every saved deck has moved.
    const legacy = formatOf(parsed.cardRefFormat) === "id";
    const refs = (compressed: Record<string, number>) => {
      const ids = expandCardIds(compressed);
      return legacy ? ids.map(refForId) : ids;
    };

    return {
      id: parsed.id,
      name: parsed.name,
      author: parsed.author,
      oshiCardIds: refs(parsed.oshiCards ?? {}),
      mainCardIds: refs(parsed.mainCards ?? {}),
      yellCardIds: refs(parsed.yellCards ?? {}),
      version: parsed.version ?? "",
      cardRefFormat: "image-key",
    };
  } catch {
    return null;
  }
}
