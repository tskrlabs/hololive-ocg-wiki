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
 * already in the wild. What makes it safe across the v1 → v2 cutover is that a card `id`
 * is the official site's own detail-page id (`scrape/fetch.py:91`), not a database rowid
 * — the ids in an old deck code still resolve.
 *
 * Extracted as pure functions, per the review's "other notes": v1 welded this transform
 * into the state composable alongside `window`, `localStorage` and `useI18n`, so the
 * round trip could not be tested without a browser. Here it is `encode`/`decode` over
 * plain values.
 */

import type { Deck } from "~/types/deck";

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

    return {
      id: parsed.id,
      name: parsed.name,
      author: parsed.author,
      oshiCardIds: expandCardIds(parsed.oshiCards ?? {}),
      mainCardIds: expandCardIds(parsed.mainCards ?? {}),
      yellCardIds: expandCardIds(parsed.yellCards ?? {}),
      version: parsed.version ?? "",
    };
  } catch {
    return null;
  }
}
