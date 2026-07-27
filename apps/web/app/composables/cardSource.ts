/**
 * The card source — the seam between "what the app asks for" and "where it comes from"
 * (architecture review Candidate 01, ports & adapters).
 *
 * Everything below is a **pure function of a transport**. The HTTP adapter is the one
 * production uses; an in-memory adapter backs the tests. Two adapters is what justifies a
 * seam existing at all — with one, this would be indirection for its own sake.
 *
 * v1 had the opposite problem: *two whole stores*. A legacy client-side one (Fuse.js over
 * an 8 MB JSON, loaded at every boot) and an HTTP one, each with its own interface, which
 * is why nearly every consuming view existed twice. The legacy store was already dead but
 * still cost a page load. It is not ported; this is the single interface that replaces
 * both.
 *
 * Nothing here touches Vue. The caching, request-dedupe and reactive state live in
 * `useCardQuery`, which composes this.
 */

import type { Card, CardCollection, Locales } from "~/types/card";
import type { FilterOptions, FilterOptionsResponse } from "~/types/filter";
import { toApiParams } from "~/composables/filter-states";
import { MAX_BATCH } from "@holo/schema/enums";

/** A page of filtered cards. `total` is absent when the count was skipped. */
export type CardPage = { cards: CardCollection; total?: number };

/**
 * The transport: given a path and query, produce parsed JSON.
 *
 * Deliberately this small. Anything richer would push knowledge of *our* endpoints into
 * the adapter, and the point of the seam is that the adapter knows only how to fetch.
 */
export type Transport = <T>(
  path: string,
  query?: Record<string, unknown>,
) => Promise<T>;

/** The production adapter: same-origin `/api/*` through Nuxt's `$fetch`. */
export const httpTransport: Transport = <T>(
  path: string,
  query?: Record<string, unknown>,
): Promise<T> => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, Array.isArray(value) ? value.join(",") : String(value));
  }
  const qs = params.toString();
  const url = qs ? `${path}?${qs}` : path;

  // `$fetch` is reached through an untyped alias on purpose.
  //
  // Its declared return type is `TypedInternalResponse`, resolved by matching the URL
  // against Nuxt's generated route table. These paths are the *Worker's* routes, not
  // Nitro's, so there is nothing to match — and the attempt recurses deeply enough that
  // TypeScript gives up with "excessive stack depth" (TS2321) rather than an error about
  // our code. Going through the alias skips that inference entirely.
  //
  // The cast here is this module's whole job: one boundary where an untyped external
  // response becomes a contract type, instead of a cast at each of nine call sites.
  const request = $fetch as (url: string) => Promise<unknown>;
  return request(url) as Promise<T>;
};

/** Split ids into batches the API will accept (it 400s above the cap, D7). */
export function chunk(ids: string[], size: number = MAX_BATCH): string[][] {
  const batches: string[][] = [];
  for (let i = 0; i < ids.length; i += size) batches.push(ids.slice(i, i + size));
  return batches;
}

/**
 * The queries the app makes, expressed once.
 *
 * Each is a thin, testable mapping from domain arguments to a request. The endpoints and
 * their quirks — the batch cap, the comma-joined path segments, `skip_count` — are
 * confined here rather than spread across components.
 */
export function createCardSource(transport: Transport = httpTransport) {
  return {
    async filter(
      filters: FilterOptions,
      locale: Locales,
      page = 1,
      limit = 50,
      skipCount = false,
    ): Promise<CardPage> {
      return transport<CardPage>("/api/cards/filter", {
        ...toApiParams(filters),
        locale,
        page,
        limit,
        // Only sent when true: the API reads the literal string "true", and sending
        // "false" would be indistinguishable from not asking.
        ...(skipCount ? { skip_count: "true" } : {}),
      });
    },

    async byId(id: string, locale: Locales): Promise<Card | undefined> {
      const response = await transport<{ card: Card }>(`/api/cards/${id}`, { locale });
      return response?.card;
    },

    /**
     * Several cards by id, chunked.
     *
     * v1 joined every id into one URL. Phase 4 made an over-cap request a 400 instead of
     * silently truncating, and a legal deck is 71 cards (1 oshi + 50 main + 20 yell), so
     * chunking is what keeps a full deck loading.
     */
    async byIds(ids: string[], locale: Locales): Promise<CardCollection> {
      if (ids.length === 0) return [];
      const pages = await Promise.all(
        chunk(ids).map((batch) =>
          transport<{ cards: CardCollection }>(
            `/api/cards-list/${batch.join(",")}`,
            { locale },
          ),
        ),
      );
      return pages.flatMap((page) => page.cards);
    },

    /** Every printing of one card number. */
    async byCardNumber(cardNumber: string, locale: Locales): Promise<CardCollection> {
      const response = await transport<{ cards: CardCollection }>(
        `/api/cards/filter-by-card-number/${encodeURIComponent(cardNumber)}`,
        { locale },
      );
      return response.cards;
    },

    /** One representative card per number — used by the Q&A cross-references. */
    async byCardNumbers(
      cardNumbers: string[],
      locale: Locales,
    ): Promise<CardCollection> {
      if (cardNumbers.length === 0) return [];
      const pages = await Promise.all(
        chunk(cardNumbers).map((batch) =>
          transport<{ cards: CardCollection }>(
            `/api/cards/by-card-numbers/${encodeURIComponent(batch.join(","))}`,
            { locale },
          ),
        ),
      );
      return pages.flatMap((page) => page.cards);
    },

    async search(
      query: string,
      locale: Locales,
      limit = 100,
    ): Promise<CardCollection> {
      if (!query.trim()) return [];
      const response = await transport<{ cards: CardCollection }>(
        "/api/cards/search",
        { q: query.trim(), locale, limit },
      );
      return response.cards;
    },

    /** The dropdown values, served from R2 rather than computed per request. */
    filterOptions(locale: Locales): Promise<FilterOptionsResponse> {
      return transport<FilterOptionsResponse>("/api/filter-options", { locale });
    },
  };
}

export type CardSource = ReturnType<typeof createCardSource>;
