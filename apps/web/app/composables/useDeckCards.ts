/**
 * The deck-list view model (architecture review Candidate 04).
 *
 * A deck is stored as a flat list of card ids with duplicates — three copies of a card
 * appear three times. Every view that renders one has to do the same four steps: count
 * the duplicates, dedupe, fetch the distinct cards, and join the counts back on.
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

import type { Card } from "~/types/card";

export type DeckCard = {
  /** Convenience alias of `card.id`, which several templates key on. */
  cardId: string;
  /** How many copies of this card the deck holds. */
  count: number;
  card: Card;
};

export function useDeckCards(cardIds: () => string[]) {
  const cardStore = useCardStoreAPI();
  const { locale } = useI18n();

  const isLoading = ref(true);
  const cards = ref<Card[]>([]);

  /** Distinct ids with their multiplicity, in first-seen order. */
  const counted = computed(() => {
    const counts = new Map<string, number>();
    for (const id of cardIds()) counts.set(id, (counts.get(id) ?? 0) + 1);
    return [...counts].map(([id, count]) => ({ id, count }));
  });

  /** The counts joined onto the fetched cards. Ids that failed to fetch drop out. */
  const deckCards = computed<DeckCard[]>(() => {
    if (!cards.value.length) return [];
    const byId = new Map(cards.value.map((card) => [card.id, card]));

    return counted.value.flatMap(({ id, count }) => {
      const card = byId.get(id);
      return card ? [{ cardId: card.id, count, card }] : [];
    });
  });

  watch(
    [counted, locale],
    async () => {
      isLoading.value = true;
      const ids = counted.value.map((item) => item.id);
      if (ids.length === 0) {
        cards.value = [];
        isLoading.value = false;
        return;
      }
      // Chunked to the API's batch cap inside the store — a legal deck is 71 cards.
      cards.value = (await cardStore.getCardsByIds(ids, locale.value)) ?? [];
      isLoading.value = false;
    },
    { immediate: true },
  );

  return { deckCards, cards, isLoading };
}
