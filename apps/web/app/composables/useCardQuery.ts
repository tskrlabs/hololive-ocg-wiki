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

/**
 * Why the last request failed, or `null` if it did not (#45).
 *
 * A failed fetch used to be written down as `cards: []`, which is the same value a
 * genuine zero-result produces — so offline, HTTP 500, a timeout and a malformed response
 * all rendered as *"No cards found — try adjusting your filters"*. That advice cannot
 * help: no filter change reaches an unreachable API, and a user on a flaky connection
 * concludes the wiki has no cards.
 *
 * `isLoading: boolean` alongside `cards: []` cannot express this — the pair has four
 * combinations and only three are legal. The kinds are distinguished because the useful
 * message differs: offline is the user's network, server is ours.
 */
export type QueryErrorKind = "offline" | "server" | "timeout";

/**
 * What the card list should render right now (D17, #38).
 *
 * The four legal situations, named — rather than inferred at each call site from
 * `isLoading` and `cards.length`. Those two booleans-in-effect have more combinations
 * than there are real states, and the illegal ones are reachable: `isLoading === false`
 * with `cards === []` is *both* "matched nothing" and "the fetch failed", which is
 * precisely the bug #45 fixed by adding `error` beside them.
 *
 * `error` stopped the two being the same *value*; this stops them being the same
 * *question*. A template asks `state.status` once instead of assembling the answer from
 * three refs in an order it has to get right.
 *
 * `refiltering` is deliberately distinct from `loading`: one has results to keep on
 * screen and dim, the other has nothing to show but skeletons. Conflating them is what
 * produced the full-screen blur over the very results being refined.
 */
export type QueryState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "refiltering"; cards: CardCollection; total: number }
  | { status: "ready"; cards: CardCollection; total: number }
  | { status: "empty" }
  | { status: "error"; kind: QueryErrorKind };

/**
 * Classify a thrown fetch failure.
 *
 * `$fetch` rejects with an `FetchError` carrying `statusCode` for an HTTP response and
 * none at all when the request never completed, which is the distinction that matters:
 * no status means the network did not carry it.
 */
export function classifyError(error: unknown): QueryErrorKind {
  const status = (error as { statusCode?: number; status?: number } | null)?.statusCode
    ?? (error as { status?: number } | null)?.status;

  if (typeof status === "number" && status > 0) {
    return status === 408 || status === 504 ? "timeout" : "server";
  }

  const name = (error as { name?: string } | null)?.name;
  if (name === "TimeoutError" || name === "AbortError") return "timeout";

  // No status and not an abort: the request never reached anyone.
  return "offline";
}

export const useCardQuery = () => {
  const cards = useState<CardCollection>("cards", () => []);
  const total = useState<number>("cardsTotal", () => 0);
  const page = useState<number>("cardsPage", () => 1);
  const isLoading = useState<boolean>("cardsLoading", () => false);

  /**
   * Why the last card fetch failed, or `null`. See `QueryErrorKind` (#45).
   *
   * Still here beside `cards` rather than replaced by the union: `state` below is
   * *derived* from these refs, so the many existing readers of `cards.value` keep
   * working. The union is what a template should ask; these are what the fetch functions
   * write.
   */
  const error = useState<QueryErrorKind | null>("cardsError", () => null);

  /**
   * Whether the request in flight is appending a page rather than replacing the list.
   *
   * The distinction the union needs and a lone `isLoading` cannot carry: appending must
   * leave the visible results completely untouched, while replacing may dim them. Both
   * set `isLoading`.
   */
  const isAppending = useState<boolean>("cardsAppending", () => false);

  /** Has any query completed yet? Distinguishes "nothing asked" from "asked, none". */
  const hasResolved = useState<boolean>("cardsResolved", () => false);
  const optionsError = useState<QueryErrorKind | null>("filterOptionsError", () => null);

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
      error.value = null;
      hasResolved.value = true;
      return cached.cards;
    }

    isLoading.value = true;
    isAppending.value = false;
    try {
      const result = await once(key, () =>
        source.filter(filters, locale, pageNumber, limit),
      );
      const resolved = result.total ?? total.value;

      cards.value = result.cards;
      total.value = resolved;
      page.value = pageNumber;
      error.value = null;
      pageCache.value.set(key, { cards: result.cards, total: resolved });
      return result.cards;
    } catch (cause) {
      // The empty list still happens — the view needs *something* to render — but it is
      // no longer the only thing said about the failure (#45).
      console.error("Failed to fetch cards:", cause);
      error.value = classifyError(cause);
      cards.value = [];
      total.value = 0;
      return [];
    } finally {
      isLoading.value = false;
      // Set *after* the request settles, so an in-flight first query reads as `loading`
      // rather than briefly as `empty`.
      hasResolved.value = true;
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
    // Marks this load as an *append*, which is what keeps the visible results from being
    // dimmed or replaced by skeletons while the next page is in flight (#38).
    isAppending.value = true;
    try {
      const result = await once(key, () =>
        source.filter(filters, locale, nextPage, limit, true),
      );
      cards.value = [...existing, ...result.cards];
      page.value = nextPage;
      error.value = null;
      // Cached with the total page 1 established, since this response carries none.
      pageCache.value.set(key, { cards: result.cards, total: total.value });
      return result.cards;
    } catch (cause) {
      // The cards already on screen are kept — a failed *next* page does not invalidate
      // the pages that arrived — but the failure is now reportable rather than silent.
      console.error("Failed to load more cards:", cause);
      error.value = classifyError(cause);
      cards.value = existing;
      return [];
    } finally {
      isLoading.value = false;
      isAppending.value = false;
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
      optionsError.value = null;
      return options;
    } catch (cause) {
      // Empty arrays render as "no filter options exist", which is a lie of the same
      // shape as the card list's (#45). The caller can now tell the two apart.
      console.error("Failed to load filter options:", cause);
      optionsError.value = classifyError(cause);
      return { names: [], tags: [], sets: [] };
    }
  }

  /**
   * The one question a view should ask (D17, #38).
   *
   * Derived rather than stored, so it cannot disagree with the refs the fetch functions
   * write — a second source of truth updated by hand is how `cards: []` came to mean two
   * different things in the first place.
   *
   * Order matters and encodes the rules:
   *
   * 1. **An append never changes the state.** A failed or pending *next* page must leave
   *    the pages already on screen exactly as they are, so `isAppending` short-circuits
   *    to whatever the list already is.
   * 2. **A failure outranks an empty list**, because the empty list *is* the failure's
   *    residue. Reversed, every error would render "no cards match these filters" — the
   *    lie #45 removed.
   * 3. **Loading with results is `refiltering`**, which keeps them; loading without is
   *    `loading`, which shows skeletons. Same boolean, two situations, and only the
   *    presence of prior results tells them apart.
   */
  const state = computed<QueryState>(() => {
    const visible = cards.value;

    if (isLoading.value && !isAppending.value) {
      return visible.length > 0
        ? { status: "refiltering", cards: visible, total: total.value }
        : { status: "loading" };
    }

    if (error.value && visible.length === 0) {
      return { status: "error", kind: error.value };
    }

    if (visible.length > 0) {
      return { status: "ready", cards: visible, total: total.value };
    }

    // Nothing on screen, nothing failed: either no query has run yet, or one ran and
    // genuinely matched nothing. Only the second is the user's filters' fault.
    return hasResolved.value ? { status: "empty" } : { status: "idle" };
  });

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
    error,
    optionsError,
    /** What to render (D17). Prefer this over assembling the answer from the refs above. */
    state,
    isAppending,

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
