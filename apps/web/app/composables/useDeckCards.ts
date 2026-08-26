/**
 * The deck-list view model (architecture review Candidate 04).
 *
 * A deck is stored as a flat list of card references with duplicates — three copies of a
 * card appear three times. Every view that renders one has to do the same four steps:
 * count the duplicates, dedupe, fetch the distinct cards, and join the counts back on.
 *
 * **The reference is an `image_key`, not an id** (ADR 0014, #83). The official site reuses
 * its own ids, so an id-keyed deck silently resolved to the wrong cards after a
 * renumbering. Some refs resolve to nothing at all; those are surfaced as
 * `unresolvedCards` rather than dropped.
 *
 * v1 wrote that pipeline out three times. `FloatingDeckCardList` and `DeckDetailCardList`
 * had it verbatim — the same `uniqueCardIds` reduce, the same `uniqueCards` join, the
 * same `watch`/fetch boilerplate — and `DeckDetailCompactModeCardList` had a hand-rolled
 * `Map` variant applied three times over, once per section. Six copies of one derivation
 * across three files.
 *
 * Taking `cardIds` as a getter rather than a plain array keeps it reactive: the deck is
 * edited while these lists are on screen, so the fetch has to follow.
 */

import type { Card, Locales } from "~/types/card";
import { isUnresolved, unresolvedId } from "~/composables/cardRefs";

export type DeckCard = {
  /** Convenience alias of `card.id`, which several templates key on. */
  cardId: string;
  /** How many copies of this card the deck holds. */
  count: number;
  card: Card;
};

/**
 * A slot the deck holds but we cannot name (ADR 0014).
 *
 * Kept rather than dropped: a card missing from a 50-card deck is invisible, and the user
 * is the only one who knows what was meant. `ref` is the original reference, shown so they
 * can replace it.
 */
export type UnresolvedDeckCard = {
  ref: string;
  /** The legacy card id behind it, when there was one. */
  originalId: string;
  count: number;
};

/**
 * @param cardRefs `image_key`s (ADR 0014), or `unresolved:` markers for references the
 * migration could not translate.
 *
 * **Never name a local binding `ref` in this file.** Nuxt's auto-import scanner skips any
 * identifier it sees bound in scope, so a `for (const ref of …)` loop suppressed the
 * `ref` import for the whole module: `computed` and `watch` were injected, `ref` was not,
 * and the deck panel died with `ReferenceError: ref is not defined` on first open. Nothing
 * caught it — `vue-tsc` resolves auto-imports from generated types, and the unit tests
 * shim `ref` onto `globalThis`, so both were blind to it.
 */
export function useDeckCards(cardRefs: () => string[]) {
  const cardQuery = useCardQuery();
  const { locale } = useI18n();

  const isLoading = ref(true);
  const cards = ref<Card[]>([]);

  /** Distinct refs with their multiplicity, in first-seen order. */
  const counted = computed(() => {
    const counts = new Map<string, number>();
    for (const cardRef of cardRefs()) {
      counts.set(cardRef, (counts.get(cardRef) ?? 0) + 1);
    }
    return [...counts].map(([cardRef, count]) => ({ cardRef, count }));
  });

  /** The counts joined onto the fetched cards. */
  const deckCards = computed<DeckCard[]>(() => {
    if (!cards.value.length) return [];
    const byKey = new Map(cards.value.map((card) => [card.image_key, card]));

    return counted.value.flatMap(({ cardRef, count }) => {
      const card = byKey.get(cardRef);
      return card ? [{ cardId: card.id, count, card }] : [];
    });
  });

  /**
   * Slots that name no card — either marked `unresolved:` by the migration, or an
   * `image_key` the API returned nothing for (a card withdrawn since the deck was saved).
   */
  const unresolvedCards = computed<UnresolvedDeckCard[]>(() => {
    const byKey = new Set(cards.value.map((card) => card.image_key));
    return counted.value.flatMap(({ cardRef, count }) => {
      if (!isUnresolved(cardRef) && byKey.has(cardRef)) return [];
      // Still loading is not the same as unresolvable; say nothing until the fetch lands.
      if (!isUnresolved(cardRef) && isLoading.value) return [];
      return [
        {
          ref: cardRef,
          originalId: isUnresolved(cardRef) ? unresolvedId(cardRef) : cardRef,
          count,
        },
      ];
    });
  });

  watch(
    [counted, locale],
    async () => {
      isLoading.value = true;
      // `unresolved:` markers name no card, so they are never sent to the API.
      const keys = counted.value
        .map((item) => item.cardRef)
        .filter((cardRef) => !isUnresolved(cardRef));
      if (keys.length === 0) {
        cards.value = [];
        isLoading.value = false;
        return;
      }
      // Chunked to the API's batch cap inside the store — a legal deck is 71 cards.
      cards.value = (await cardQuery.getCardsByKeys(keys, locale.value as Locales)) ?? [];
      isLoading.value = false;
    },
    { immediate: true },
  );

  return { deckCards, cards, unresolvedCards, isLoading };
}
