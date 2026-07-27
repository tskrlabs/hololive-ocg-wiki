/**
 * The deck's sections and their rules (architecture review Candidate 03).
 *
 * A deck is three parallel arrays — `oshiCardIds`, `mainCardIds`, `yellCardIds` — so in
 * v1 every operation forked three ways: `addCardToDeck`, `removeCardFromDeck`,
 * `removeAllCardFromDeck` and `getCardCount` each had the same branch written out three
 * times, twelve near-identical blocks in one file.
 *
 * Worse, **the size rules had no home at all**. 1 oshi / 50 main / 20 yell were magic
 * numbers typed directly into templates, with the status-colour ternary copied six times
 * across `pages/deck/[code]/index.vue` and `FloatingDeck.vue` — and the store enforced
 * nothing, so a deck could hold 60 main cards with only the badge turning red.
 *
 * Here the section is a value, the rules are data, and a caller passes a card type rather
 * than choosing a bucket. Adding a section becomes one entry.
 *
 * **The stored shape does not change** (Q11): this is how the deck is *reasoned about*,
 * not how it is written down. `deckCode.ts` is the boundary, and the three array names
 * stay exactly as v1 wrote them into `localStorage` and into every shared URL.
 */

import {
  MAIN_CARD_TYPES,
  OSHI_CARD_TYPES,
  YELL_CARD_TYPES,
  type CardTypeCode,
} from "@holo/schema/enums";
import type { Deck } from "~/types/deck";

export type SectionKey = "oshi" | "main" | "yell";

/** Which `Deck` field a section is stored in — the frozen names (Q11). */
export type SectionField = "oshiCardIds" | "mainCardIds" | "yellCardIds";

export type SectionSpec = {
  key: SectionKey;
  field: SectionField;
  /** The official deck-construction limit. */
  limit: number;
  /** Card types this section accepts, from the contract. */
  cardTypes: readonly CardTypeCode[];
};

/**
 * The deck rules, in one place.
 *
 * The limits are the game's: exactly 1 oshi, exactly 50 main, exactly 20 yell. The card
 * types come from `@holo/schema/enums`, which is generated from the same models as the
 * database — v1's hand-written copy omitted `supportStaff`, so a card of that type
 * matched no section and silently vanished when added.
 */
export const SECTIONS: readonly SectionSpec[] = [
  { key: "oshi", field: "oshiCardIds", limit: 1, cardTypes: OSHI_CARD_TYPES },
  { key: "main", field: "mainCardIds", limit: 50, cardTypes: MAIN_CARD_TYPES },
  { key: "yell", field: "yellCardIds", limit: 20, cardTypes: YELL_CARD_TYPES },
] as const;

/**
 * Which section a card type belongs to, or `null` if none does.
 *
 * `null` is a real answer, not a failure: `unknown` is a legitimate card type — the
 * scraper writes it when it cannot classify a card — and it is deliberately absent from
 * all three lists, because routing an unclassified card to `main` would be a guess.
 */
export function sectionForCardType(cardType: CardTypeCode): SectionSpec | null {
  return SECTIONS.find((section) => section.cardTypes.includes(cardType)) ?? null;
}

export function sectionByKey(key: SectionKey): SectionSpec {
  // Every key is a member of SECTIONS by construction of the type.
  return SECTIONS.find((section) => section.key === key)!;
}

/** How many cards a section currently holds. */
export function sectionCount(deck: Deck, section: SectionSpec): number {
  return deck[section.field].length;
}

/** How many copies of one card a section holds. */
export function copiesOf(deck: Deck, section: SectionSpec, cardId: string): number {
  return deck[section.field].filter((id) => id === cardId).length;
}

/** Room left before the section is full. Never negative. */
export function remaining(deck: Deck, section: SectionSpec): number {
  return Math.max(0, section.limit - sectionCount(deck, section));
}

/**
 * A section's completeness, for the badge in the deck views.
 *
 * v1 spelled this as a nested ternary over raw lengths, copied six times across two
 * files. The names are the states, not the colours — a view still chooses how to render
 * `over` versus `complete`, but no longer decides what those mean.
 */
export type SectionStatus = "empty" | "partial" | "complete" | "over";

export function sectionStatus(deck: Deck, section: SectionSpec): SectionStatus {
  const count = sectionCount(deck, section);
  if (count === 0) return "empty";
  if (count > section.limit) return "over";
  if (count === section.limit) return "complete";
  return "partial";
}

/** Is the whole deck legal — every section exactly at its limit? */
export function isDeckLegal(deck: Deck): boolean {
  return SECTIONS.every((section) => sectionStatus(deck, section) === "complete");
}

/**
 * Add copies of a card, up to the section's limit.
 *
 * Returns a **new** array rather than mutating, so the caller decides when state changes,
 * and the count actually added — which may be fewer than asked for, or zero. v1 had no
 * cap here at all: `addCardToDeck` pushed unconditionally and the limit existed only as a
 * number in a template.
 */
export function addToSection(
  deck: Deck,
  section: SectionSpec,
  cardId: string,
  amount = 1,
): { ids: string[]; added: number } {
  const current = deck[section.field];
  const added = Math.min(amount, Math.max(0, section.limit - current.length));
  if (added === 0) return { ids: current, added: 0 };
  return { ids: [...current, ...Array<string>(added).fill(cardId)], added };
}

/**
 * Remove copies of a card.
 *
 * Removes from the end, so repeatedly adding and removing one card leaves the rest of the
 * order untouched. `amount` omitted removes every copy.
 */
export function removeFromSection(
  deck: Deck,
  section: SectionSpec,
  cardId: string,
  amount?: number,
): { ids: string[]; removed: number } {
  const current = deck[section.field];
  let toRemove = amount ?? Number.POSITIVE_INFINITY;
  const ids: string[] = [];

  for (let i = current.length - 1; i >= 0; i--) {
    const id = current[i]!;
    if (id === cardId && toRemove > 0) {
      toRemove--;
      continue;
    }
    ids.unshift(id);
  }

  const removed = current.length - ids.length;
  return { ids: removed > 0 ? ids : current, removed };
}
