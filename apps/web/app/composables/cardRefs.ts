/**
 * Translating a deck's card references from the official site's ids to `image_key`.
 *
 * **Why this exists** (ADR 0014, issue #83). On 2026-08-26 the official list inserted 36
 * cards mid-sequence and renumbered 82 existing ones: same `card_number`, same artwork,
 * new `?id=`. Card ids come from the site's own `?id=` hrefs, so an id in a saved deck
 * stopped meaning the card it was saved as.
 *
 * The failure mode this prevents is **not** a missing card. After a seed, a renumbered id
 * still resolves — to the wrong card. Nothing throws, nothing is empty, and a player just
 * opens a deck with different cards in it. That is why the migration is not optional and
 * not user-confirmed: there is no error state for a user to notice.
 *
 * Pure functions over plain values, like `deckCode.ts` and for the same reason: the round
 * trip must be testable without a browser, `localStorage` or `useI18n`.
 */

import history from "@holo/schema/card-id-history" with { type: "json" };
import type { Deck } from "~/types/deck";

/**
 * Which identifier a deck's card references are written in.
 *
 * Deliberately **not** `APP_VERSION` (ADR 0014). That field is stamped into every deck as
 * an app release marker, and reusing it here would make a routine version bump read as a
 * format change. Absent or empty means `"id"` — `decode()` has always defaulted a missing
 * version to `""`, so codes in that state exist in the wild.
 */
export type CardRefFormat = "id" | "image-key";

/** `id -> image_key`, as production D1 held it before the renumbering. Frozen. */
const ID_TO_IMAGE_KEY: Record<string, string> = history.mapping;

/**
 * An unresolved reference, kept in place rather than dropped.
 *
 * A card id absent from the map is genuinely foreign: a hand-edited `localStorage`, a
 * corrupted paste, or a card withdrawn by an update after the snapshot. It keeps its slot
 * so the user can see what was lost and replace it — dropping it silently would make a
 * missing card in a 50-card deck invisible, and the user is the only one who knows what
 * was meant.
 */
export const UNRESOLVED_PREFIX = "unresolved:";

export function unresolvedRef(cardId: string): string {
  return `${UNRESOLVED_PREFIX}${cardId}`;
}

export function isUnresolved(ref: string): boolean {
  return ref.startsWith(UNRESOLVED_PREFIX);
}

/** The original id behind an unresolved reference, for display in the placeholder. */
export function unresolvedId(ref: string): string {
  return ref.slice(UNRESOLVED_PREFIX.length);
}

/** Absent, empty and unrecognised all mean the legacy id form. */
export function formatOf(value: string | undefined): CardRefFormat {
  return value === "image-key" ? "image-key" : "id";
}

/**
 * One card id to its `image_key`, or an unresolved marker.
 *
 * The lookup is exact, never a guess. The snapshot was verified total at capture — 2,650
 * ids, 2,650 distinct keys, every key still present in the 2,686-card build — so a hit is
 * the card the deck meant, and a miss is genuinely unknown rather than merely unmoved.
 * That distinction is the whole reason the full map ships instead of the 82-entry delta.
 */
export function refForId(cardId: string): string {
  return ID_TO_IMAGE_KEY[cardId] ?? unresolvedRef(cardId);
}

/** Every id in a list, translated. */
function convertList(cardIds: string[]): string[] {
  return cardIds.map(refForId);
}

/**
 * Migrate one deck's references to `image_key`.
 *
 * Idempotent by way of `cardRefFormat`: a deck already in the new form is returned
 * untouched, so a second pass at the next mount is a no-op rather than a double
 * translation that would turn every `image_key` into an unresolved marker.
 */
export function migrateDeck(deck: Deck): { deck: Deck; converted: boolean } {
  if (formatOf(deck.cardRefFormat) === "image-key") {
    return { deck, converted: false };
  }

  return {
    deck: {
      ...deck,
      oshiCardIds: convertList(deck.oshiCardIds ?? []),
      mainCardIds: convertList(deck.mainCardIds ?? []),
      yellCardIds: convertList(deck.yellCardIds ?? []),
      cardRefFormat: "image-key",
    },
    converted: true,
  };
}

/** Migrate a collection, reporting how many decks changed so the toast can say. */
export function migrateDecks(decks: Deck[]): { decks: Deck[]; convertedCount: number } {
  let convertedCount = 0;
  const migrated = decks.map((deck) => {
    const result = migrateDeck(deck);
    if (result.converted) convertedCount += 1;
    return result.deck;
  });
  return { decks: migrated, convertedCount };
}
