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
 */
const gridColCount = shallowRef(gridGeometry(1280).columns);
const itemSize = shallowRef(gridGeometry(1280).itemSize);
const itemSecondarySize = shallowRef(gridGeometry(1280).itemSecondarySize);

function onResizeObserver(entries: ResizeObserverEntry[]) {
  const [entry] = entries;
  if (!entry) return;

  const { width } = entry.contentRect;
  if (!width || width <= 0) return;

  const geometry = gridGeometry(width);

  gridColCount.value = geometry.columns;
  itemSecondarySize.value = geometry.itemSecondarySize;
  itemSize.value = geometry.itemSize;
}

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
  <div>
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
    <div v-else-if="displayedCards.length > 0" class="">
      <div class="">
        <RecycleScroller
          v-if="shouldRenderScroller"
          ref="virtualScroller"
          :key="`scroller-${gridColCount}-${locale}`"
          class="scroller p-2 pb-[65vh]"
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
          <template #default="{ item }">
            <div class="p-1">
              <CardItem :item="item" class="aspect-400/559" />
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
          class="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2 p-2"
        >
          <div
            v-for="item in displayedCards"
            :key="item.id"
            class="aspect-400/559"
          >
            <CardItem :item="item" class="aspect-400/559" />
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

    <!-- No results message -->
    <div
      v-else-if="!showLoadingIndicator && displayedCards.length === 0"
      class="flex justify-center items-center min-h-[200px]"
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
      Results summary.

      Floated rather than placed in flow. In flow it sits *below* a scroller that is
      `height: 100dvh`, so it is never on screen — which is how it came to be commented
      out, and why "Showing 200 of 2448" went unseen while infinite scroll was broken.
      Mirrors FloatingDeck (bottom-left) on the opposite side so the two do not overlap.
    -->
    <div
      v-if="displayedCards.length > 0"
      class="fixed bottom-13 md:bottom-16 right-0 m-2 md:m-4 z-40 pointer-events-none"
    >
      <p
        class="rounded-md border bg-background/90 px-2 py-1 text-xs text-muted-foreground backdrop-blur"
      >
        {{
          $t("Showing {count} of {total} cards", {
            count: displayedCards.length,
            total: cardQuery.total.value,
          })
        }}
      </p>
    </div>
  </div>
</template>

<style lang="css" scoped>
.scroller {
  height: 100dvh;
}

/* Responsive heights for virtual scroller */
/* @media (min-height: 500px) {
  .scroller {
    height: 50vh;
  }
}

@media (min-height: 800px) {
  .scroller {
    height: 60vh;
  }
}

@media (min-height: 1000px) {
  .scroller {
    height: 70vh;
  }
} */

/* Ensure virtual scroller items maintain proper aspect ratio */
/* .scroller :deep(.vue-recycle-scroller__item-wrapper) {
  overflow: visible;
} */
</style>
