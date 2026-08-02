<script lang="ts" setup>
/**
 * The persistent filter rail, from `lg` (D10, #36).
 *
 * 280px, fixed — not resizable and not collapsible. It holds a fixed set of controls, and
 * because #43's columns derive from a target tile width rather than a breakpoint ladder,
 * a narrower rail buys the grid roughly 1.5 extra cards. That is not worth a drag handle.
 *
 * At 1024px this still leaves 728px of grid, which the target-width rule turns into four
 * legible columns — so there is no third layout between the sheet and the rail (#36 §1).
 *
 * **Its own scroll region**, `min-h-0 overflow-y-auto`. `min-h-0` is load-bearing for the
 * same reason it is everywhere else under the flex-column shell: a flex child's default
 * `min-height: auto` refuses to shrink below its content, so without it the groups would
 * push the Apply footer off the bottom (#44, P3).
 */
const filter = useFilter();
const cardQuery = useCardQuery();

/**
 * Whether there is a count worth stating.
 *
 * Read from `state` rather than from `total > 0`, which conflated "no cards match" with
 * "no query has run" and suppressed the line for both. The union already separates them
 * (D17): `idle` is the boot state and has nothing to report, and `loading` is the first
 * query still in flight. `empty` is the case this exists for — its number is zero, and
 * zero is the answer.
 *
 * **`error` is excluded, and that is #45's rule, not an omission.** A failed fetch also
 * writes `total = 0`, so rendering the count there would say "0 cards" — indistinguishable
 * from "your filters match nothing" and pointing the user at filters that cannot fix an
 * unreachable API. The grid reports the failure; the rail stays quiet rather than
 * contradicting it.
 *
 * `refiltering` keeps the previous count on screen deliberately, matching the grid beside
 * it: those results are still the ones being displayed until the new ones land.
 */
const showCount = computed(() => {
  const status = cardQuery.state.value.status;
  return status === "ready" || status === "refiltering" || status === "empty";
});

onMounted(() => {
  filter.initializeDraftFilters();
});
</script>

<template>
  <!--
    A `<nav>` with a name, so a screen-reader user can jump to the filters as a landmark
    rather than tabbing through them (#48 §7).
  -->
  <nav
    class="hidden w-[280px] shrink-0 flex-col border-r bg-background lg:flex"
    :aria-label="$t('Filter')"
  >
    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <!--
        Search lives in the rail on desktop (#36 §4).

        It belongs with the other query controls, and the header was already eight icon
        buttons wide. On mobile it stays in the header, because the sheet is closed most
        of the time and a search you must open a panel to reach is a worse search.
      -->
      <SearchInputAPI />

      <!--
        The result count, directly under the search field (#36 §4).

        It is query feedback and the rail is where the query lives. `role="status"` so a
        change is announced rather than only drawn — the count is the one thing that says
        an Apply did something when the grid is scrolled away from the top.

        **Zero is a count, and it was the one being withheld.** The guard was
        `total > 0`, so a search matching nothing rendered no line at all — the single
        surface that reports what a query did went silent in exactly the case where the
        user most needs telling, and the grid's empty state is off to the right where a
        reader watching what they typed is not looking. `hasQuery` distinguishes it from
        the boot state, which genuinely has nothing to report yet.

        It also stops the rail's height changing under the pointer as results come and go.
      -->
      <p v-if="showCount" class="text-xs text-muted-foreground" role="status">
        {{ $t("{total} cards", { total: cardQuery.total.value }) }}
      </p>

      <FilterPanel />
    </div>

    <!--
      The Apply footer is pinned, not scrolled with the groups (#36 §5). With seven groups
      visible at once the commit control must not be somewhere below the fold.
    -->
    <div class="shrink-0 border-t p-4">
      <FilterActions />
    </div>
  </nav>
</template>
