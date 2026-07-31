<script setup lang="ts">
import { vResizeObserver } from "@vueuse/components";
import { useDebounceFn } from "@vueuse/core";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";

const { locale } = useI18n();
const filter = useFilter();
const cardQuery = useCardQuery(); 

// Ref to the virtual scroller
const virtualScroller = ref();

// Scroll position tracking
const scrollPosition = ref(0);
const shouldPreserveScroll = ref(false);

// Pagination state
const pageSize = ref(200); // Increased for virtual scrolling
const currentPage = ref(1);
const hasMore = computed(() => {
  return cardQuery.cards.value.length < cardQuery.total.value;
});

/**
 * Virtual scroller geometry.
 *
 * The rule lives in `gridColumns.ts` — columns follow from a target tile width rather
 * than from a breakpoint ladder, which is what stops the cards shrinking as the window
 * grows (#43). `RecycleScroller` cannot measure its own children, so both axes are
 * computed here and passed as props.
 *
 * ⚠️ **The geometry now depends on two pieces of *state*, not only on width** (#37 §5).
 * Compact mode drops the text block and gains a column on a phone; show-original adds a
 * line to every tile. Both change `itemSize`, which is how the scroller positions rows —
 * so a stale value does not degrade gracefully, it overlaps the whole grid.
 */
const { density } = useCardDensity();
const { enabled: showOriginal } = useShowOriginal();

const geometryOptions = computed(() => ({
  showsText: showsText(density.value),
  showsOriginal: showOriginal.value,
  compactMobileBonus: true,
}));

/** The last width the observer reported, kept so state changes can re-measure. */
const observedWidth = shallowRef(1280);

const gridColCount = shallowRef(gridGeometry(1280, { compactMobileBonus: true }).columns);
const itemSize = shallowRef(gridGeometry(1280, { compactMobileBonus: true }).itemSize);
const itemSecondarySize = shallowRef(
  gridGeometry(1280, { compactMobileBonus: true }).itemSecondarySize,
);

function measure(width: number) {
  const geometry = gridGeometry(width, geometryOptions.value);

  gridColCount.value = geometry.columns;
  itemSecondarySize.value = geometry.itemSecondarySize;
  itemSize.value = geometry.itemSize;
}

function onResizeObserver(entries: ResizeObserverEntry[]) {
  const [entry] = entries;
  if (!entry) return;

  const { width } = entry.contentRect;
  if (!width || width <= 0) return;

  observedWidth.value = width;
  measure(width);
}

/**
 * Re-measure when the mode changes, not only when the width does.
 *
 * Without this the observer is the only path to `itemSize`, and flipping a toggle resizes
 * nothing — so the grid would keep the previous mode's row height until the next window
 * resize. `tests/grid.test.ts` pins the heights themselves; this is the wiring that
 * delivers them, which is the half a pure test cannot see (F-019).
 */
watch(geometryOptions, () => measure(observedWidth.value));

// Debounced filter application - simplified
const applyFilters = useDebounceFn(async () => {
  // Reset pagination first
  currentPage.value = 1;

  // Make the API call directly - the cardStore will handle loading states
  await cardQuery.getFilteredCards(
    filter.filter.value,
    locale.value,
    1,
    pageSize.value
  );
}, 300); // Slightly increased debounce for API calls// Load more cards for infinite scroll with virtual scroller
const loadMore = async () => {
  if (cardQuery.isLoading.value || !hasMore.value) return;

  // Save current scroll position before loading
  if (virtualScroller.value && virtualScroller.value.$el) {
    scrollPosition.value = virtualScroller.value.$el.scrollTop;
    shouldPreserveScroll.value = true;
  }

  currentPage.value++;
  await cardQuery.loadMore(
    filter.filter.value,
    locale.value,
    currentPage.value,
    pageSize.value
  );
};

// Virtual scroller infinite loading with improved scroll handling
const handleScrollEnd = useDebounceFn(() => {
  // Load more when reaching the end of virtual scroller
  if (hasMore.value && !cardQuery.isLoading.value) {
    loadMore();
  }
}, 100); // Debounce to prevent multiple rapid calls

/**
 * Return to the top of the list.
 *
 * A new filter replaces the items but not the scroll offset, so without this the first
 * page of a fresh result set renders under a viewport still scrolled to where the last
 * one was — the user applies a filter and appears to land in the middle of it. Invisible
 * until infinite scroll started working, because there was never a second page to be
 * scrolled into.
 *
 * `shouldPreserveScroll` is cleared alongside: it belongs to the append path, and a
 * pending restore would otherwise scroll us straight back down.
 */
const scrollToTop = () => {
  shouldPreserveScroll.value = false;
  scrollPosition.value = 0;
  virtualScroller.value?.scrollToItem?.(0);
};

// Apply filters when filter changes - simplified
watch(
  () => filter.filter.value,
  () => {
    // Reset pagination when filters change
    currentPage.value = 1;
    // Use setTimeout to move execution out of current tick and prevent UI blocking
    setTimeout(() => {
      applyFiltersWithPreciseLoading();
    }, 0);
  },
  {
    deep: true,
    immediate: false, // Prevent immediate execution on mount
  }
);

// Also update when locale changes
watch(
  () => locale.value,
  () => {
    // Reset pagination when locale changes
    currentPage.value = 1;
    // Use setTimeout to prevent blocking
    setTimeout(() => {
      cardQuery.clearCache();
      applyFiltersWithPreciseLoading();
    }, 0);
  }
);

// Initial filter application
onMounted(() => {
  // Initialize window height tracking
  updateWindowHeight();
  window.addEventListener("resize", updateWindowHeight);

  // Use setTimeout to prevent blocking initial render
  setTimeout(() => {
    applyFiltersWithPreciseLoading();
  }, 0);
});

onUnmounted(() => {
  window.removeEventListener("resize", updateWindowHeight);
});

// Use the filtered cards from the store
const displayedCards = computed(() => cardQuery.cards.value);

/**
 * The failure to report, if there is one (#45).
 *
 * Only shown when there is nothing to show: a `loadMore` that fails leaves the pages
 * already on screen intact, and replacing a working list with an error panel would be a
 * worse answer than leaving the list alone.
 */
const queryError = computed(() =>
  displayedCards.value.length === 0 ? cardQuery.error.value : null,
);

/** Ask again. The failed page was never cached, so this is a real retry. */
const retry = () => {
  applyFiltersWithPreciseLoading();
};

// Window size tracking for responsive design (simplified for virtual scroller)
const windowHeight = ref(0);

const updateWindowHeight = () => {
  windowHeight.value = window.innerHeight;
};

// Loading state for better UX
const showLoadingIndicator = computed(() => {
  return cardQuery.isLoading.value && displayedCards.value.length === 0;
});

const showLoadMoreIndicator = computed(() => {
  return cardQuery.isLoading.value && displayedCards.value.length > 0;
});

// Track if we're filtering (not just loading more)
const isFiltering = ref(false);

// Enhanced apply filters with precise loading control
const applyFiltersWithPreciseLoading = () => {
  isFiltering.value = true;

  // Call the debounced function
  applyFilters();

  // Watch for the loading state to change to track when API call completes
  const stopWatching = watch(
    () => cardQuery.isLoading.value,
    (isLoading, wasLoading) => {
      // When loading goes from true to false, the API call is done
      if (wasLoading && !isLoading) {
        // Add a small delay to ensure DOM has updated
        nextTick(() => {
          // After the new results are in the DOM, not before — scrolling a list that
          // still holds the previous filter's items would be undone by the re-render.
          scrollToTop();
          isFiltering.value = false;
          stopWatching(); // Stop watching
        });
      }
    }
  );

  // Safety timeout in case something goes wrong
  setTimeout(() => {
    isFiltering.value = false;
    stopWatching();
  }, 5000);
};

// Computed property to check if virtual scroller should be rendered
const shouldRenderScroller = computed(() => {
  return (
    displayedCards.value.length > 0 &&
    itemSize.value > 0 &&
    itemSecondarySize.value > 0 &&
    gridColCount.value > 0
  );
});

// Watch for changes in displayed cards to preserve scroll position
watch(
  () => displayedCards.value.length,
  async (newLength, oldLength) => {
    // Only preserve scroll when cards are added (not when filtering)
    if (newLength > oldLength && shouldPreserveScroll.value) {
      await nextTick();
      if (virtualScroller.value && virtualScroller.value.$el) {
        virtualScroller.value.$el.scrollTop = scrollPosition.value;
        shouldPreserveScroll.value = false;
      }
    }
  }
);
</script>

<template>
  <!--
    A flex column filling the region the shell gives it (#44). The scroller needs a real
    height to inherit; before the shell change there was none to inherit, which is how it
    came to be `height: 100dvh` — a whole viewport, sitting between a sticky header and a
    sticky footer, with ~138px of the list hidden underneath them.
  -->
  <div class="flex h-full flex-col">
    <!-- Filtering overlay - only when filtering, not when loading more -->
    <div
      v-if="isFiltering"
      class="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 flex items-center justify-center"
    >
      <div class="flex flex-col items-center gap-2">
        <div
          class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"
        ></div>
        <p class="text-sm text-muted-foreground">
          {{ $t("Applying filters") }}...
        </p>
      </div>
    </div>

    <!-- Loading indicator for initial load -->
    <div
      v-if="showLoadingIndicator && !isFiltering"
      class="flex justify-center items-center min-h-[400px]"
    >
      <div class="flex flex-col items-center gap-2">
        <div
          class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"
        ></div>
        <p class="text-sm text-muted-foreground">
          {{ $t("Loading cards") }}...
        </p>
      </div>
    </div>

    <!-- Virtual Scroller for cards grid -->
    <div
      v-else-if="displayedCards.length > 0"
      class="flex min-h-0 grow flex-col"
    >
      <div class="min-h-0 grow">
        <!--
          The scroller's key carries **every input to the geometry**, not just the column
          count. `RecycleScroller` caches each item's position from the `itemSize` it was
          constructed with, so a changed row height has to remount it — otherwise rows
          keep the old spacing and overlap. Density and the show-original toggle both
          change that height (#37 §5), and both were missing from this key.
        -->
        <RecycleScroller
          v-if="shouldRenderScroller"
          ref="virtualScroller"
          :key="`scroller-${gridColCount}-${locale}-${density}-${showOriginal}`"
          class="scroller p-2"
          :items="displayedCards"
          :item-size="itemSize"
          :item-secondary-size="itemSecondarySize"
          :grid-items="gridColCount"
          :buffer="600"
          key-field="id"
          :emit-update="true"
          @scroll-end="handleScrollEnd"
          v-resize-observer="onResizeObserver"
        >
          <!--
            No `aspect-400/559` on the tile any more: the tile is art *plus* text now, and
            forcing the card's ratio onto the whole thing would crop the name it exists to
            show. The ratio lives on the art element inside `CardItem`, where it belongs.
          -->
          <template #default="{ item }">
            <div class="p-1">
              <CardItem :item="item" />
            </div>
          </template>
        </RecycleScroller>

        <!--
          Fallback grid, rendered until the resize observer reports a width.

          This carried its own copy of the breakpoint ladder
          (`xl:grid-cols-8 2xl:grid-cols-10`), so it had the same bug: a *smaller* card at
          1536px than at 1440px. Fixing only the scroller would have left it live here.

          `auto-fill` keys on the minimum track rather than on a target, so it is not
          identical to `columnsForWidth` — it fills to whatever fits above `MIN_TILE`
          instead of aiming at `TARGET_TILE`. What it does share is the property the bug
          was about: columns are derived from width, so the tile can never fall below
          150px and adding a column can never shrink the grid's floor. #43.
        -->
        <div
          v-else
          class="grid h-full grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2 overflow-y-auto p-2"
        >
          <div v-for="item in displayedCards" :key="item.id">
            <CardItem :item="item" />
          </div>
        </div>
      </div>

      <!-- Load more indicator for virtual scroller -->
      <div
        v-if="showLoadMoreIndicator"
        class="flex justify-center items-center py-8"
      >
        <div class="flex items-center gap-2">
          <div
            class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"
          ></div>
          <p class="text-sm text-muted-foreground">
            {{ $t("Loading more cards") }}...
          </p>
        </div>
      </div>
    </div>

    <!--
      The fetch failed (#45).

      This has to come *before* the empty state, because both are reached with an empty
      card list and only one of them is about the user's filters. Telling someone whose
      API is unreachable to "try adjusting your filters" sends them to a control that
      cannot possibly help, and reads as "this wiki has no cards".
    -->
    <div
      v-else-if="!showLoadingIndicator && queryError"
      class="flex grow justify-center items-center min-h-[200px]"
    >
      <div class="text-center">
        <p class="text-lg font-medium">
          {{ $t(`errors.cards.${queryError}.title`) }}
        </p>
        <p class="text-sm text-muted-foreground mt-1">
          {{ $t(`errors.cards.${queryError}.detail`) }}
        </p>
        <Button variant="outline" size="sm" class="mt-4" @click="retry">
          {{ $t("errors.retry") }}
        </Button>
      </div>
    </div>

    <!-- No results message — a genuine zero-result, with filters worth adjusting. -->
    <div
      v-else-if="!showLoadingIndicator && displayedCards.length === 0"
      class="flex grow justify-center items-center min-h-[200px]"
    >
      <div class="text-center">
        <p class="text-lg font-medium text-muted-foreground">
          {{ $t("No cards found") }}
        </p>
        <p class="text-sm text-muted-foreground mt-1">
          {{ $t("Try adjusting your filters") }}
        </p>
      </div>
    </div>

    <!--
      Results summary — back in normal flow (#44), and below `lg` only (#36 §4).

      It was `fixed`, and its comment recorded why: *"In flow it sits below a scroller
      that is `height: 100dvh`, so it is never on screen — which is how it came to be
      commented out, and why 'Showing 200 of 2448' went unseen while infinite scroll was
      broken."* That was this bug, diagnosed and worked around rather than fixed. With
      the scroller sized to the space it actually has, below the scroller *is* on screen,
      so the workaround and its `bottom-13 md:bottom-16` guess both go.

      Above `lg` the rail carries the count instead: it is query feedback, and the rail is
      where the query lives. Two live counts on one screen would be one too many, and the
      rail's is the one beside the controls that change it.
    -->
    <div
      v-if="displayedCards.length > 0"
      class="shrink-0 border-t px-2 py-1 text-right text-xs text-muted-foreground lg:hidden"
    >
      {{
        $t("Showing {count} of {total} cards", {
          count: displayedCards.length,
          total: cardQuery.total.value,
        })
      }}
    </div>
  </div>
</template>

<style lang="css" scoped>
/*
 * The scroller fills its parent rather than the viewport (#44).
 *
 * It used to be `height: 100dvh` between a sticky header and a sticky footer, each 69px,
 * so ~138px of the list was permanently hidden underneath the chrome — 17% of the list
 * at an 800px viewport. The commented-out `50vh`/`60vh`/`70vh` ladder below it was an
 * earlier attempt at the same problem by guessing; both are gone now that the shell is a
 * flex column and there is a real height to inherit.
 */
.scroller {
  height: 100%;
}
</style>
