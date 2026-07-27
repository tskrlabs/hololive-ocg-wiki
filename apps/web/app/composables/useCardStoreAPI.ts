import { MAX_BATCH } from "@holo/schema/enums";
import { createEmpty, toApiParams } from "~/composables/filter-states";
import type { Card, CardCollection, Locales } from "~/types/card";
import type { FilterOptions, FilterOptionsResponse } from "~/types/filter";

interface FilterResponse {
  cards: CardCollection;
  /**
   * Absent when the request set `skip_count=true`.
   *
   * v1's Worker returned `-1` as a sentinel; Phase 4's omits the key entirely, which is
   * why this is optional rather than `number`. Read it as `total ?? cachedTotal` — a
   * sentinel that is a valid number for the field's type is exactly the shape that gets
   * rendered to a user by accident.
   */
  total?: number;
}

// `FilterOptionsResponse` was declared here as well as in `types/filter.ts`; it now
// comes from the one place, imported above.

// The API-backed card store. v1's client-side `useCardStore` (Fuse.js over an 8 MB JSON
// imported at boot) is not ported at all — see ADR 0006, Candidate 01.
export const useCardStoreAPI = () => {
  // State management
  const allCards = useState<CardCollection>("cards", () => []);
  const filteredCards = useState<CardCollection>("filteredCards", () => []);
  const isLoading = useState<boolean>("cardsLoading", () => false);
  const totalCards = useState<number>("totalCards", () => 0);
  const currentPage = useState<number>("currentPage", () => 1);

  // Cache for API responses
  const filterCache = useState<Map<string, FilterResponse>>(
    "filterCache",
    () => new Map(),
  );

  // Cache for filter options
  const filterOptionsCache = useState<Map<string, FilterOptionsResponse>>(
    "filterOptionsCache",
    () => new Map(),
  );

  // Cache for individual cards by ID and locale
  const cardsCache = useState<Map<string, Card>>("cardsCache", () => new Map());

  // Cache for cards by card number
  const cardsByNumberCache = useState<Map<string, CardCollection>>(
    "cardsByNumberCache",
    () => new Map(),
  );

  // Cache for cards by multiple card numbers
  const cardsByNumbersCache = useState<Map<string, CardCollection>>(
    "cardsByNumbersCache",
    () => new Map(),
  );

  // API call helper with error handling
  const apiCall = async <T>(
    endpoint: string,
    params?: Record<string, any>,
  ): Promise<T> => {
    try {
      // Build query string for parameters
      const searchParams = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            if (Array.isArray(value)) {
              searchParams.set(key, value.join(","));
            } else {
              searchParams.set(key, String(value));
            }
          }
        });
      }

      // Construct the URL with query parameters
      const url =
        endpoint +
        (searchParams.toString() ? "?" + searchParams.toString() : "");

      return (await $fetch<T>(url)) as T;
    } catch (error) {
      console.error(`API call failed for ${endpoint}:`, error);
      throw error;
    }
  };

  // Load cards with filtering - now uses API
  const loadCards = async (
    filterOptions?: FilterOptions,
    locale: Locales = "en",
  ) => {
    // The fifth copy of the empty-filter literal lived here — 50 lines listing every
    // colour, card type, rarity and bloom level by hand. `createEmpty()` derives it from
    // the contract's enums instead (Candidate 02).
    return await getFilteredCards(filterOptions ?? createEmpty(), locale);
  };

  // Get filtered cards from API
  const getFilteredCards = async (
    filterOptions: FilterOptions,
    locale: Locales,
    page: number = 1,
    limit: number = 50,
  ): Promise<CardCollection> => {
    // Create cache key
    const cacheKey = JSON.stringify({ ...filterOptions, locale, page, limit });

    // Return cached result if available
    if (filterCache.value.has(cacheKey)) {
      const cached = filterCache.value.get(cacheKey)!;
      filteredCards.value = cached.cards;
      // A page-2+ entry was cached with the total page 1 established, but the type
      // allows it to be absent — keep what we have rather than zeroing the count.
      totalCards.value = cached.total ?? totalCards.value;
      currentPage.value = page;
      return cached.cards;
    }

    isLoading.value = true;

    try {
      // One mapping, shared with every other caller (Candidate 02): v1 rebuilt
      // this block here and again in the other pagination path.
      const apiParams: Record<string, any> = {
        ...toApiParams(filterOptions),
        locale,
        page,
        limit,
      };

      // Make API call
      const response = await apiCall<FilterResponse>(
        "/api/cards/filter",
        apiParams,
      );

      // Update state. This path never sets skip_count, so `total` is present — but it
      // is read defensively rather than asserted, because the fallback (keep the count
      // we had) is strictly better than rendering "undefined results".
      const total = response.total ?? totalCards.value;
      filteredCards.value = response.cards;
      totalCards.value = total;
      currentPage.value = page;

      filterCache.value.set(cacheKey, { cards: filteredCards.value, total });

      return response.cards;
    } catch (error) {
      console.error("Failed to fetch filtered cards:", error);
      // Fallback to empty array on error
      filteredCards.value = [];
      totalCards.value = 0;
      return [];
    } finally {
      isLoading.value = false;
    }
  };

  // Get card by ID from API
  const getCardById = async (
    id: string,
    locale: Locales = "en",
  ): Promise<Card | undefined> => {
    // Create cache key with locale
    const cacheKey = `${id}_${locale}`;

    // Return cached card if available
    if (cardsCache.value.has(cacheKey)) {
      return cardsCache.value.get(cacheKey);
    }

    try {
      const response = await apiCall<{ card: Card }>(`/api/cards/${id}`, {
        locale,
      });
      if (response.card) {
        const normalizedCard = response.card;
        // Cache the card
        cardsCache.value.set(cacheKey, normalizedCard);
        return normalizedCard;
      }
      return undefined;
    } catch (error) {
      console.error(`Failed to fetch card ${id}:`, error);
      return undefined;
    }
  };

  // Get cards by card number from API
  const getCardsByCardNumber = async (
    cardNumber: string,
    locale: Locales = "en",
  ): Promise<CardCollection> => {
    if (!cardNumber.trim()) return [];

    // Create cache key with locale
    const cacheKey = `${cardNumber.trim()}_${locale}`;

    // Return cached cards if available
    if (cardsByNumberCache.value.has(cacheKey)) {
      return cardsByNumberCache.value.get(cacheKey)!;
    }

    try {
      const response = await apiCall<{ cards: CardCollection }>(
        `/api/cards/filter-by-card-number/${encodeURIComponent(
          cardNumber.trim(),
        )}`,
        { locale },
      );

      const normalizedCards = response.cards;

      // Cache the cards
      cardsByNumberCache.value.set(cacheKey, normalizedCards);

      // Also cache individual cards for other operations
      normalizedCards.forEach((card) => {
        const cardCacheKey = `${card.id}_${locale}`;
        cardsCache.value.set(cardCacheKey, card);
      });

      return normalizedCards;
    } catch (error) {
      console.error(
        `Failed to fetch cards with card number ${cardNumber}:`,
        error,
      );
      return [];
    }
  };

  // Get cards by multiple card numbers from API (first match for each number)
  const getCardsByCardNumbers = async (
    cardNumbers: string[],
    locale: Locales = "en",
  ): Promise<CardCollection> => {
    if (cardNumbers.length === 0) return [];

    // Filter and sanitize card numbers
    const validCardNumbers = cardNumbers
      .map((num) => num.trim())
      .filter((num) => num.length > 0);

    if (validCardNumbers.length === 0) return [];

    // Create cache key with locale and sorted card numbers for consistent caching
    const sortedNumbers = [...validCardNumbers].sort();
    const cacheKey = `${sortedNumbers.join(",")}_${locale}`;

    // Return cached cards if available
    if (cardsByNumbersCache.value.has(cacheKey)) {
      return cardsByNumbersCache.value.get(cacheKey)!;
    }

    try {
      const response = await apiCall<{ cards: CardCollection }>(
        `/api/cards/by-card-numbers/${encodeURIComponent(
          validCardNumbers.join(","),
        )}`,
        { locale },
      );

      const normalizedCards = response.cards;

      // Cache the cards
      cardsByNumbersCache.value.set(cacheKey, normalizedCards);

      // Also cache individual cards for other operations
      normalizedCards.forEach((card) => {
        const cardCacheKey = `${card.id}_${locale}`;
        cardsCache.value.set(cardCacheKey, card);
      });

      return normalizedCards;
    } catch (error) {
      console.error(
        `Failed to fetch cards with card numbers ${validCardNumbers.join(
          ",",
        )}:`,
        error,
      );
      return [];
    }
  };

  const getCardsByIds = async (
    ids: string[],
    locale: Locales = "en",
  ): Promise<CardCollection> => {
    if (ids.length === 0) return [];

    // Check cache for existing cards
    const cachedCards: Card[] = [];
    const missingIds: string[] = [];

    ids.forEach((id) => {
      const cacheKey = `${id}_${locale}`;
      const cachedCard = cardsCache.value.get(cacheKey);
      if (cachedCard) {
        cachedCards.push(cachedCard);
      } else {
        missingIds.push(id);
      }
    });

    // If all cards are cached, return them immediately
    if (missingIds.length === 0) {
      // console.log(`All ${ids.length} cards found in cache`);
      // Return cards in the same order as requested IDs
      return ids
        .map((id) => {
          const cacheKey = `${id}_${locale}`;
          return cardsCache.value.get(cacheKey)!;
        })
        .filter(Boolean);
    }

    // console.log(
    //   `Found ${cachedCards.length} cached cards, fetching ${missingIds.length} new cards`
    // );

    try {
      // Fetch the missing cards, in batches the API will accept.
      //
      // Phase 4 made an over-cap request a 400 instead of silently returning the first
      // 50. v1 sliced server-side and said nothing, so a deck longer than 50 cards
      // rendered short with no error — the worst failure mode available to a deck
      // builder, and reachable with a legal deck (1 oshi + 50 main + 20 yell = 71).
      // Chunking is what keeps that legal deck working.
      const batches: string[][] = [];
      for (let i = 0; i < missingIds.length; i += MAX_BATCH) {
        batches.push(missingIds.slice(i, i + MAX_BATCH));
      }

      const responses = await Promise.all(
        batches.map((batch) =>
          apiCall<{ cards: CardCollection }>(
            `/api/cards-list/${batch.join(",")}`,
            { locale },
          ),
        ),
      );

      const newCards = responses.flatMap((response) => response.cards);

      // Cache the newly fetched cards
      newCards.forEach((card) => {
        const cacheKey = `${card.id}_${locale}`;
        cardsCache.value.set(cacheKey, card);
      });

      // Combine cached and new cards, maintaining the order of requested IDs
      const allCards = ids
        .map((id) => {
          const cacheKey = `${id}_${locale}`;
          return cardsCache.value.get(cacheKey);
        })
        .filter(Boolean) as Card[];

      return allCards;
    } catch (error) {
      console.error("Failed to fetch cards by IDs:", error);
      // Return cached cards even if API call fails
      return cachedCards;
    }
  };

  // Search cards using API
  const searchCards = async (
    query: string,
    locale: Locales = "en",
    limit: number = 100,
  ): Promise<CardCollection> => {
    if (!query.trim()) {
      return [];
    }

    try {
      isLoading.value = true;
      const response = await apiCall<{ cards: CardCollection }>(
        "/api/cards/search",
        {
          q: query.trim(),
          locale,
          limit,
        },
      );

      return response.cards;
    } catch (error) {
      console.error("Search failed:", error);
      return [];
    } finally {
      isLoading.value = false;
    }
  };

  // Get filter options from API
  const getFilterOptions = async (
    locale: Locales,
  ): Promise<FilterOptionsResponse> => {
    // Check cache first
    if (filterOptionsCache.value.has(locale)) {
      return filterOptionsCache.value.get(locale)!;
    }

    try {
      const response = await apiCall<FilterOptionsResponse>(
        "/api/filter-options",
        { locale },
      );

      // Cache the result
      filterOptionsCache.value.set(locale, response);

      return response;
    } catch (error) {
      console.error("Failed to fetch filter options:", error);
      return { names: [], tags: [], sets: [] };
    }
  };

  // Get name options for a locale
  const getNameOptions = async (locale: Locales) => {
    const options = await getFilterOptions(locale);
    return options.names;
  };

  // Get tag options for a locale
  const getTagOptions = async (locale: Locales) => {
    const options = await getFilterOptions(locale);
    return options.tags;
  };

  // Get set options for a locale
  const getSetOptions = async (locale: Locales) => {
    const options = await getFilterOptions(locale);
    return options.sets;
  };

  // Clear caches
  const clearCache = () => {
    filterCache.value.clear();
    filterOptionsCache.value.clear();
    cardsCache.value.clear();
    cardsByNumberCache.value.clear();
    cardsByNumbersCache.value.clear();
  };

  // Load more cards for pagination
  const loadMoreCards = async (
    filterOptions: FilterOptions,
    locale: Locales,
    nextPage: number,
    limit: number = 50,
  ): Promise<CardCollection> => {
    // Store existing cards before making the API call
    const existingCards = [...filteredCards.value];

    // Create cache key for this specific page
    const cacheKey = JSON.stringify({
      ...filterOptions,
      locale,
      page: nextPage,
      limit,
    });

    // Check if this specific page is already cached
    if (filterCache.value.has(cacheKey)) {
      const cached = filterCache.value.get(cacheKey)!;
      // Append cached cards to existing ones
      filteredCards.value = [...existingCards, ...cached.cards];
      return cached.cards;
    }

    isLoading.value = true;

    try {
      // The same mapping page 1 used. v1's comment here said "same as
      // getFilteredCards" — it was a hand-maintained copy, and a copy that drifts makes
      // page 2 filter differently from page 1.
      const apiParams: Record<string, any> = {
        ...toApiParams(filterOptions),
        locale,
        page: nextPage,
        limit,
      };

      // Skip the COUNT query on page 2+ — client already has the total from page 1
      apiParams.skip_count = true;

      // Make API call directly (don't use getFilteredCards to avoid overwriting)
      const response = await apiCall<FilterResponse>(
        "/api/cards/filter",
        apiParams,
      );

      const newCards = response.cards;

      // Append new cards to existing ones
      filteredCards.value = [...existingCards, ...newCards];

      // Keep the total from page 1. The response omits `total` entirely when
      // skip_count=true (v1's Worker returned -1); either way this path never reads it.
      currentPage.value = nextPage;

      // Cache this specific page using the known total
      filterCache.value.set(cacheKey, {
        cards: newCards,
        total: totalCards.value,
      });

      return newCards;
    } catch (error) {
      console.error("Failed to load more cards:", error);
      // Restore existing cards on error
      filteredCards.value = existingCards;
      return [];
    } finally {
      isLoading.value = false;
    }
  };

  // Precompute filter options - now async
  const precomputeFilterOptions = async (locale: Locales) => {
    if (process.server) return;

    // Preload filter options for better UX
    setTimeout(() => {
      getFilterOptions(locale);
    }, 100);
  };

  // Get cache statistics for debugging
  const getCacheStats = () => {
    return {
      filterCacheSize: filterCache.value.size,
      filterOptionsCacheSize: filterOptionsCache.value.size,
      cardsCacheSize: cardsCache.value.size,
      cardsByNumberCacheSize: cardsByNumberCache.value.size,
      cardsByNumbersCacheSize: cardsByNumbersCache.value.size,
    };
  };

  return {
    // State
    allCards,
    filteredCards,
    isLoading,
    totalCards,
    currentPage,

    // Main methods
    loadCards,
    getFilteredCards,
    getCardById,
    getCardsByIds,
    getCardsByCardNumber,
    getCardsByCardNumbers,
    searchCards,

    // Filter options
    getNameOptions,
    getTagOptions,
    getSetOptions,
    getFilterOptions,

    // Pagination
    loadMoreCards,

    // Cache management
    clearCache,
    getCacheStats,
    precomputeFilterOptions,
  };
};
