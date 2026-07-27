<script setup lang="ts">
import { vResizeObserver } from "@vueuse/components";
import { useDebounceFn } from "@vueuse/core";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";

const { locale } = useI18n();
const filter = useFilter();
const cardStore = useCardStoreAPI(); // Use the new API-based store

// Ref to the virtual scroller
const virtualScroller = ref();

// Scroll position tracking
const scrollPosition = ref(0);
const shouldPreserveScroll = ref(false);

// Pagination state
const pageSize = ref(200); // Increased for virtual scrolling
const currentPage = ref(1);
const hasMore = computed(() => {
  return cardStore.filteredCards.value.length < cardStore.totalCards.value;
});

/**
 * Virtual scroller card size and padding configuration
 */
let cardPadding = 8;
const cardImageRatio =
  (558 + cardPadding + cardPadding) / (400 + cardPadding + cardPadding); // Ratio of card height to width
const gridColCount = shallowRef(6);
const itemSize = shallowRef(574); // Default calculated size (400 + padding)
const itemSecondarySize = shallowRef(416); // Default calculated secondary size (558 + padding)

function onResizeObserver(entries: ResizeObserverEntry[]) {
  const [entry] = entries;
  if (!entry) return;

  const { width } = entry.contentRect;
  if (!width || width <= 0) return;

  if (width < 640) {
    cardPadding = 4; // Adjust ratio for smaller screens
  } else {
    cardPadding = 8; // Default padding for larger screens
  }

  if (width < 640) {
    gridColCount.value = 3;
  } else if (width < 768) {
    gridColCount.value = 4;
  } else if (width < 1024) {
    gridColCount.value = 5;
  } else if (width < 1280) {
    gridColCount.value = 6;
  } else if (width < 1536) {
    gridColCount.value = 8;
  } else if (width < 2000) {
    gridColCount.value = 10;
  } else {
    gridColCount.value = 12;
  }

  // Ensure we have valid dimensions
  const newSecondarySize = Math.max(100, width / gridColCount.value); // Min 100px width
  const newSize = Math.max(140, newSecondarySize * cardImageRatio); // Min 140px height

  itemSecondarySize.value = newSecondarySize;
  itemSize.value = newSize;
}

// Debounced filter application - simplified
const applyFilters = useDebounceFn(async () => {
  // Reset pagination first
  currentPage.value = 1;

  // Make the API call directly - the cardStore will handle loading states
  await cardStore.getFilteredCards(
    filter.filter.value,
    locale.value,
    1,
    pageSize.value
  );
}, 300); // Slightly increased debounce for API calls// Load more cards for infinite scroll with virtual scroller
const loadMore = async () => {
  if (cardStore.isLoading.value || !hasMore.value) return;

  // Save current scroll position before loading
  if (virtualScroller.value && virtualScroller.value.$el) {
    scrollPosition.value = virtualScroller.value.$el.scrollTop;
    shouldPreserveScroll.value = true;
  }

  currentPage.value++;
  await cardStore.loadMoreCards(
    filter.filter.value,
    locale.value,
    currentPage.value,
    pageSize.value
  );
};

// Virtual scroller infinite loading with improved scroll handling
const handleScrollEnd = useDebounceFn(() => {
  // Load more when reaching the end of virtual scroller
  if (hasMore.value && !cardStore.isLoading.value) {
    loadMore();
  }
}, 100); // Debounce to prevent multiple rapid calls

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
      cardStore.clearCache();
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
const displayedCards = computed(() => cardStore.filteredCards.value);

// Window size tracking for responsive design (simplified for virtual scroller)
const windowHeight = ref(0);

const updateWindowHeight = () => {
  windowHeight.value = window.innerHeight;
};

// Loading state for better UX
const showLoadingIndicator = computed(() => {
  return cardStore.isLoading.value && displayedCards.value.length === 0;
});

const showLoadMoreIndicator = computed(() => {
  return cardStore.isLoading.value && displayedCards.value.length > 0;
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
    () => cardStore.isLoading.value,
    (isLoading, wasLoading) => {
      // When loading goes from true to false, the API call is done
      if (wasLoading && !isLoading) {
        // Add a small delay to ensure DOM has updated
        nextTick(() => {
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
          @scroll-end="handleScrollEnd"
          v-resize-observer="onResizeObserver"
        >
          <template #default="{ item }">
            <div class="p-1">
              <CardItem :item="item" class="aspect-400/559" />
            </div>
          </template>
        </RecycleScroller>

        <!-- Fallback grid when virtual scroller can't render -->
        <div
          v-else
          class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 2xl:grid-cols-10 gap-2 p-2"
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

    <!-- Results summary -->
    <!-- <div v-if="displayedCards.length > 0" class="flex justify-center py-4">
      <p class="text-sm text-muted-foreground">
        Showing {{ displayedCards.length }} of
        {{ cardStore.totalCards.value }} cards
        <span v-if="hasMore">(scroll for more)</span>
      </p>
    </div> -->

    <!-- Spacer for bottom padding -->
    <!-- <div class="h-[65vh]"></div> -->
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
