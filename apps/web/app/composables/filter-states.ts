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
  CARD_TYPES,
  COLORS,
  FUSED_COLORS,
  RARITIES,
} from "@holo/schema/enums";
import type { FilterOptions } from "~/types/filter";

/** The checkbox sections, as opposed to the free-text ones. */
const FLAG_SECTIONS = ["colors", "cardTypes", "rarity", "bloomLevel"] as const;
const TEXT_SECTIONS = ["search", "name", "tag", "set"] as const;

export type FilterSection =
  | (typeof FLAG_SECTIONS)[number]
  | (typeof TEXT_SECTIONS)[number];

/**
 * Colours the filter UI offers as checkboxes.
 *
 * The fused symbols (`blue_red`, `white_green`) are **excluded**, which is a real
 * behaviour change: v1 gave them their own checkboxes, and its colour filter then
 * silently omitted them from the constituent colours — filtering `blue` missed the 5
 * `blue_red` cards, because `LIKE '%"blue"%'` does not match `"blue_red"` (F-016). The
 * Worker now expands a colour filter through `FUSED_COLORS`, so those cards appear under
 * *both* their constituent colours; a separate checkbox would be a second, worse way to
 * find them.
 */
export const FILTERABLE_COLORS = COLORS.filter(
  (color) => !(color in FUSED_COLORS),
);

const flags = <T extends string>(values: readonly T[]): Record<T, boolean> =>
  Object.fromEntries(values.map((value) => [value, false])) as Record<T, boolean>;

/** The one empty filter. Everything that needs a blank slate calls this. */
export function createEmpty(): FilterOptions {
  return {
    search: "",
    name: "",
    tag: "",
    set: "",
    colors: flags(COLORS),
    cardTypes: flags(CARD_TYPES),
    rarity: flags(RARITIES),
    bloomLevel: flags(BLOOM_LEVELS),
  };
}

/** The keys of a flag section that are switched on. */
const active = (section: Record<string, boolean>): string[] =>
  Object.keys(section).filter((key) => section[key]);

/** Is anything set? Drives the "filters are active" dot in the UI. */
export function isActive(filter: FilterOptions): boolean {
  return (
    TEXT_SECTIONS.some((key) => filter[key].trim() !== "") ||
    FLAG_SECTIONS.some((key) => active(filter[key]).length > 0)
  );
}

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
    if (value) params[key] = value;
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
  };
};
