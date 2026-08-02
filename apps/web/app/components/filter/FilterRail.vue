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
      -->
      <p
        v-if="cardQuery.total.value > 0"
        class="text-xs text-muted-foreground"
        role="status"
      >
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
