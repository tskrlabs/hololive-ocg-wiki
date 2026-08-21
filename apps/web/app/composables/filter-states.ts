/**
 * The filter module (architecture review Candidate 02).
 *
 * v1's version was 413 lines exposing ~25 members over a thin body — a shallow module in
 * the review's terms. The empty-filter literal was written out **five times** (two state
 * initialisers, two resets, and once more in `useCardStoreAPI.loadCards`), and each copy
 * was a hand-maintained list of every colour, card type, rarity and bloom level. That is
 * what let the spellings drift apart: `constants/card-data.ts` said
 * `["debut","1st","2nd","spot"]` while the type said `debut|first|second|spot`, so two of
 * four bloom filters silently matched nothing, and the missing `HR` rarity left 24 cards
 * unfilterable in the live UI.
 *
 * Here the shape is **derived** from the contract's enums, so there is exactly one empty
 * filter and it cannot disagree with the data. Adding a rarity to the pydantic models
 * regenerates the enum and this module follows with no edit.
 *
 * The interface shrinks from ~25 members to 9. Fourteen reset methods (seven
 * `resetDraftX` plus seven legacy `resetX` aliases) collapse into one `clear(section?)`.
 * The genuinely useful part of v1's design — the draft ↔ applied split, so the panel can
 * be edited without refetching on every keystroke — is kept.
 */

import {
  BLOOM_LEVELS,
  COLORS,
  FILTERABLE_CARD_TYPES,
  RARITIES,
} from "@holo/schema/enums";
import type { FilterOptions } from "~/types/filter";

/** The checkbox sections, as opposed to the free-text ones. */
const FLAG_SECTIONS = ["colors", "cardTypes", "rarity", "bloomLevel"] as const;
const TEXT_SECTIONS = ["search", "name", "tag", "set", "setCode"] as const;

export type FilterSection =
  | (typeof FLAG_SECTIONS)[number]
  | (typeof TEXT_SECTIONS)[number];

/**
 * Colours the filter UI offers as checkboxes — now every colour there is.
 *
 * This used to exclude `blue_red` and `white_green`, because they were their own enum
 * values and a checkbox for each would have been a second, worse way to find cards that
 * the Worker already returned under both constituent colours (F-016). ADR 0013 removed
 * the codes entirely: a dual-colour card holds a row per badge, so it appears under each
 * of its colours with nothing excluded and nothing expanded.
 *
 * Kept as a named export rather than inlining `COLORS`, because "the colours the filter
 * offers" and "the colours that exist" are different questions that happen to have the
 * same answer today.
 */
export const FILTERABLE_COLORS = COLORS;

const flags = <T extends string>(values: readonly T[]): Record<T, boolean> =>
  Object.fromEntries(values.map((value) => [value, false])) as Record<T, boolean>;

/** The one empty filter. Everything that needs a blank slate calls this. */
export function createEmpty(): FilterOptions {
  return {
    search: "",
    name: "",
    tag: "",
    set: "",
    setCode: "",
    colors: flags(COLORS),
    // FILTERABLE_CARD_TYPES, not CARD_TYPES: the latter includes non-card entries
    // (rules notices, F-020), which are never in an /api/cards response. A checkbox for
    // one would always return zero results.
    cardTypes: flags(FILTERABLE_CARD_TYPES),
    rarity: flags(RARITIES),
    bloomLevel: flags(BLOOM_LEVELS),
  };
}

/** Every section, in the order the panel renders them. */
export const FILTER_SECTIONS: readonly FilterSection[] = [
  "name",
  "tag",
  // Above `set`, so the two set dimensions sit together with the code first — the code
  // is what a card prints and what users type, the product name is the elaboration.
  "setCode",
  "set",
  "colors",
  "cardTypes",
  "rarity",
  "bloomLevel",
];

/** The keys of a flag section that are switched on. */
const active = (section: Record<string, boolean>): string[] =>
  Object.keys(section).filter((key) => section[key]);

/**
 * Which sections the draft has changed but not applied (D10, #36 §5).
 *
 * A persistent rail shows all seven groups at once, so one global "you have pending
 * changes" dot is too coarse to act on — it says something is uncommitted without saying
 * *what*. Inside a sheet that was fine, because the sheet showed one thing at a time and
 * closed on Apply.
 *
 * `search` is deliberately excluded: it applies immediately rather than through the draft
 * (#36 §5), so it can never be pending.
 */
export function pendingSections(
  draft: FilterOptions,
  applied: FilterOptions,
): FilterSection[] {
  return FILTER_SECTIONS.filter((section) => {
    const a = draft[section];
    const b = applied[section];
    return typeof a === "string" ? a !== b : JSON.stringify(a) !== JSON.stringify(b);
  });
}

/**
 * The set code a query names, or `undefined` — the search box's routing rule.
 *
 * Users type `hBP03` into the search box, which is what prompted this whole feature, and
 * free text is the wrong way to answer it: the FTS index also matches every ruling that
 * *cites* an hBP03 card, so the result is a mix rather than a set. Recognising the query
 * as a set code and applying the facet instead answers exactly what was asked.
 *
 * **Exact match against the known codes, not a pattern.** `hBP` is a prefix of nine codes
 * and `hBP3` of none; both stay free-text searches, so a partial typing keeps behaving
 * the way it does today rather than becoming a confident empty result. Verified against
 * production that no code collides with any card name or tag, so nothing that was
 * findable by name becomes unreachable.
 *
 * Case-insensitive because the index already is — `hbp03` matches `hBP03` today — and
 * the canonical spelling is returned so the chip and the URL show the printed form.
 */
export function matchSetCode(
  query: string,
  codes: readonly string[],
): string | undefined {
  const needle = query.trim().toLowerCase();
  if (!needle) return undefined;
  return codes.find((code) => code.toLowerCase() === needle);
}

/** Is anything set? Drives the "filters are active" dot in the UI. */
export function isActive(filter: FilterOptions): boolean {
  return (
    TEXT_SECTIONS.some((key) => filter[key].trim() !== "") ||
    FLAG_SECTIONS.some((key) => active(filter[key]).length > 0)
  );
}

/**
 * Sections whose query-string name differs from their field name.
 *
 * Only one, and only because the two sides have different conventions: the query string
 * is snake_case throughout, the filter shape camelCase throughout. A lookup rather than
 * a branch inside the loop, so a second such section is a line of data.
 */
const API_PARAM: Partial<Record<FilterSection, string>> = { setCode: "set_code" };

/**
 * The filter as `/api/cards/filter` query parameters.
 *
 * v1 rebuilt this mapping twice inside `useCardStoreAPI` — once in `getFilteredCards` and
 * again in `loadMoreCards`, each re-extracting all four flag sections by hand. Two copies
 * of a mapping is two chances for a page-2 request to filter differently from page 1.
 *
 * Empty sections are omitted rather than sent empty: the API treats an absent parameter
 * as "no constraint", while an empty `colors=` would be a request for cards with no
 * colour at all.
 */
export function toApiParams(
  filter: FilterOptions,
): Record<string, string | string[]> {
  const params: Record<string, string | string[]> = {};

  for (const key of TEXT_SECTIONS) {
    const value = filter[key].trim();
    if (value) params[API_PARAM[key] ?? key] = value;
  }
  for (const key of FLAG_SECTIONS) {
    const values = active(filter[key]);
    if (values.length > 0) params[key] = values;
  }
  return params;
}

export const useFilter = () => {
  const filterState = useState<FilterOptions>("filter", createEmpty);
  const draftFilterState = useState<FilterOptions>("draftFilter", createEmpty);

  /** Copy applied → draft, so opening the panel starts from what is in effect. */
  const initializeDraftFilters = () => {
    draftFilterState.value = structuredClone(toRaw(filterState.value));
  };

  /** Copy draft → applied. The only point at which a refetch is triggered. */
  const applyFilters = () => {
    filterState.value = structuredClone(toRaw(draftFilterState.value));
  };

  /**
   * Clear one section, or everything.
   *
   * Replaces fourteen methods: seven `resetDraftX`, and seven `resetX` legacy aliases
   * that differed only in also writing the applied state (`applied` here).
   */
  const clear = (section?: FilterSection, applied = false) => {
    const empty = createEmpty();
    const targets = applied ? [draftFilterState, filterState] : [draftFilterState];

    for (const target of targets) {
      if (!section) {
        target.value = createEmpty();
      } else {
        // Assign by key rather than replacing the object, so the panel's `v-model`
        // bindings keep pointing at live state.
        (target.value[section] as unknown) = empty[section];
      }
    }
  };

  /** Does the draft differ from what is applied? Drives the Apply button's state. */
  const hasPendingChanges = computed(
    () =>
      JSON.stringify(draftFilterState.value) !== JSON.stringify(filterState.value),
  );

  /**
   * The same question, per group — which the rail needs and the sheet did not (#36 §5).
   *
   * A `Set` rather than an array so a group heading asks `pending.has('colors')` instead
   * of scanning, and so the seven headings share one computation.
   */
  const pending = computed(
    () => new Set(pendingSections(draftFilterState.value, filterState.value)),
  );

  return {
    /** Applied filters — what the card list is showing. */
    filter: filterState,
    /** Draft filters — what the panel is editing. */
    draftFilter: draftFilterState,

    applyFilters,
    initializeDraftFilters,
    clear,

    isFiltered: () => isActive(filterState.value),
    hasPendingChanges,
    pending,
  };
};
