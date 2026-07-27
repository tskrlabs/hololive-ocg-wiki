/**
 * Card querying — one interface over one data source (Candidate 01).
 *
 * v1 had **two** stores for this: a legacy client-side one (`useCardStore`, Fuse.js over
 * an 8 MB `cards_i18n.json` imported at every boot) and an HTTP one (`useCardStoreAPI`).
 * Nearly every consuming view therefore existed twice — `Filter.vue` ↔ `FilterAPI.vue`,
 * `SearchInput.vue` ↔ `SearchInputAPI.vue`, three `CardListView*` ↔ three
 * `CardListViewAPI*`. The legacy half had gone dead but still ran at startup.
 *
 * That fork is not ported. This is the single interface; `cardSource.ts` is the seam
 * beneath it, so tests substitute an in-memory transport for HTTP.
 *
 * The interface also absorbs three things that had leaked into components:
 *
 * - **`useCardDetail` and `FilterAPI` each called `$fetch` directly**, bypassing every
 *   cache the store maintained — two more paths to endpoints the store already knew how
 *   to reach, neither of them cached.
 * - **Four filter-option methods on the store had no callers at all** (`getNameOptions`,
 *   `getTagOptions`, `getSetOptions`, `precomputeFilterOptions`), because the component
 *   fetching them by hand never used them.
 * - **In-flight requests were not deduped**, so two components mounting together made
 *   the same request twice.
 */

import type { Card, CardCollection, Locales } from "~/types/card";
import type { FilterOptions, FilterOptionsResponse } from "~/types/filter";
import { createCardSource, type CardPage, type CardSource } from "~/composables/cardSource";

/** Overridable for tests; production gets the HTTP adapter. */
let source: CardSource = createCardSource();

/** Swap the data source. Used by tests, never in application code. */
export function setCardSource(next: CardSource) {
  source = next;
}

export const useCardQuery = () => {
  const cards = useState<CardCollection>("cards", () => []);
  const total = useState<number>("cardsTotal", () => 0);
  const page = useState<number>("cardsPage", () => 1);
  const isLoading = useState<boolean>("cardsLoading", () => false);

  const byIdCache = useState<Map<string, Card>>("cardById", () => new Map());
  const pageCache = useState<Map<string, CardPage>>("cardPages", () => new Map());
  const optionsCache = useState<Map<string, FilterOptionsResponse>>(
    "filterOptions",
    () => new Map(),
  );

  /**
   * Requests in flight, keyed the same way as the caches.
   *
   * Not persisted in `useState`: a promise cannot be serialised, and an in-flight request
   * has no meaning after a page transition. Two components asking for the same thing in
   * the same tick now share one request instead of racing.
   */
  const inFlight = new Map<string, Promise<unknown>>();

  function once<T>(key: string, run: () => Promise<T>): Promise<T> {
    const existing = inFlight.get(key) as Promise<T> | undefined;
    if (existing) return existing;
    const promise = run().finally(() => inFlight.delete(key));
    inFlight.set(key, promise);
    return promise;
  }

  const pageKey = (
    filters: FilterOptions,
    locale: Locales,
    pageNumber: number,
    limit: number,
  ) => JSON.stringify({ filters, locale, page: pageNumber, limit });

  /**
   * Fetch a page and make it the visible list.
   *
   * `total` is read as `?? total.value` throughout: the API omits the key when the count
   * was skipped, where v1's Worker returned `-1`. A sentinel that is a valid number for
   * the field is exactly the kind that gets rendered to a user by accident.
   */
  async function getFilteredCards(
    filters: FilterOptions,
    locale: Locales,
    pageNumber = 1,
    limit = 50,
  ): Promise<CardCollection> {
    const key = pageKey(filters, locale, pageNumber, limit);

    const cached = pageCache.value.get(key);
    if (cached) {
      cards.value = cached.cards;
      total.value = cached.total ?? total.value;
      page.value = pageNumber;
      return cached.cards;
    }

    isLoading.value = true;
    try {
      const result = await once(key, () =>
        source.filter(filters, locale, pageNumber, limit),
      );
      const resolved = result.total ?? total.value;

      cards.value = result.cards;
      total.value = resolved;
      page.value = pageNumber;
      pageCache.value.set(key, { cards: result.cards, total: resolved });
      return result.cards;
    } catch (error) {
      console.error("Failed to fetch cards:", error);
      cards.value = [];
      total.value = 0;
      return [];
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Fetch the next page and append it.
   *
   * Skips the COUNT query: infinite scroll already has the total from page 1, and that
   * saves a full D1 round trip per scroll — the read budget is the binding constraint
   * (F-014).
   */
  async function loadMore(
    filters: FilterOptions,
    locale: Locales,
    nextPage: number,
    limit = 50,
  ): Promise<CardCollection> {
    const key = pageKey(filters, locale, nextPage, limit);
    const existing = [...cards.value];

    const cached = pageCache.value.get(key);
    if (cached) {
      cards.value = [...existing, ...cached.cards];
      page.value = nextPage;
      return cached.cards;
    }

    isLoading.value = true;
    try {
      const result = await once(key, () =>
        source.filter(filters, locale, nextPage, limit, true),
      );
      cards.value = [...existing, ...result.cards];
      page.value = nextPage;
      // Cached with the total page 1 established, since this response carries none.
      pageCache.value.set(key, { cards: result.cards, total: total.value });
      return result.cards;
    } catch (error) {
      console.error("Failed to load more cards:", error);
      cards.value = existing;
      return [];
    } finally {
      isLoading.value = false;
    }
  }

  const cardKey = (id: string, locale: Locales) => `${id}:${locale}`;

  async function getCardById(id: string, locale: Locales): Promise<Card | undefined> {
    const key = cardKey(id, locale);
    const cached = byIdCache.value.get(key);
    if (cached) return cached;

    const card = await once(key, () => source.byId(id, locale));
    if (card) byIdCache.value.set(key, card);
    return card;
  }

  /**
   * Several cards by id, in the order asked for.
   *
   * Only the ids not already cached are fetched; the result is assembled from the cache
   * so a deck that shares cards with the visible list costs nothing extra. The order is
   * the caller's, because a deck's order is the user's, not the database's.
   */
  async function getCardsByIds(
    ids: string[],
    locale: Locales,
  ): Promise<CardCollection> {
    const missing = ids.filter((id) => !byIdCache.value.has(cardKey(id, locale)));

    if (missing.length > 0) {
      const fetched = await once(`ids:${missing.join(",")}:${locale}`, () =>
        source.byIds(missing, locale),
      );
      for (const card of fetched) byIdCache.value.set(cardKey(card.id, locale), card);
    }

    return ids
      .map((id) => byIdCache.value.get(cardKey(id, locale)))
      .filter((card): card is Card => card !== undefined);
  }

  function getCardsByCardNumber(cardNumber: string, locale: Locales) {
    return once(`number:${cardNumber}:${locale}`, () =>
      source.byCardNumber(cardNumber, locale),
    );
  }

  function getCardsByCardNumbers(cardNumbers: string[], locale: Locales) {
    return once(`numbers:${cardNumbers.join(",")}:${locale}`, () =>
      source.byCardNumbers(cardNumbers, locale),
    );
  }

  function search(query: string, locale: Locales, limit = 100) {
    return once(`search:${query}:${locale}:${limit}`, () =>
      source.search(query, locale, limit),
    );
  }

  /** The dropdown values for a locale, fetched once per locale per session. */
  async function filterOptions(locale: Locales): Promise<FilterOptionsResponse> {
    const cached = optionsCache.value.get(locale);
    if (cached) return cached;

    try {
      const options = await once(`options:${locale}`, () =>
        source.filterOptions(locale),
      );
      optionsCache.value.set(locale, options);
      return options;
    } catch (error) {
      console.error("Failed to load filter options:", error);
      return { names: [], tags: [], sets: [] };
    }
  }

  /** Drop every cache. Called when the locale changes — every entry is locale-scoped. */
  function clearCache() {
    pageCache.value.clear();
    byIdCache.value.clear();
    optionsCache.value.clear();
    inFlight.clear();
  }

  return {
    cards,
    total,
    page,
    isLoading,

    getFilteredCards,
    loadMore,
    getCardById,
    getCardsByIds,
    getCardsByCardNumber,
    getCardsByCardNumbers,
    search,
    filterOptions,
    clearCache,
  };
};
