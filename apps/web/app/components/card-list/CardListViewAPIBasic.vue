<script setup lang="ts">
import { useDebounceFn } from "@vueuse/core";

const { locale } = useI18n();
const filter = useFilter();
const cardStore = useCardStoreAPI(); // Use the new API-based store

// Pagination state
const pageSize = ref(10); // Reduced for better API performance
const currentPage = ref(1);
const hasMore = computed(() => {
  return cardStore.filteredCards.value.length < cardStore.totalCards.value;
});

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
}, 300); // Slightly increased debounce for API calls// Load more cards for infinite scroll
const loadMore = async () => {
  if (cardStore.isLoading.value || !hasMore.value) return;

  currentPage.value++;
  await cardStore.loadMoreCards(
    filter.filter.value,
    locale.value,
    currentPage.value,
    pageSize.value
  );
};

// Apply filters when filter changes - simplified
watch(
  () => filter.filter.value,
  () => {
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
    // Use setTimeout to prevent blocking
    setTimeout(() => {
      cardStore.clearCache();
      applyFiltersWithPreciseLoading();
    }, 0);
  }
);

// Initial filter application
onMounted(() => {
  // Use setTimeout to prevent blocking initial render
  setTimeout(() => {
    applyFiltersWithPreciseLoading();
  }, 0);
});

// Use the filtered cards from the store
const displayedCards = computed(() => cardStore.filteredCards.value);

// Window size tracking for responsive trigger distance
const windowHeight = ref(0);

// Update window height on resize
const updateWindowHeight = () => {
  windowHeight.value = window.innerHeight;
};

// Reactive trigger distance based on window height
const triggerDistance = computed(() => {
  const spacingHeight = windowHeight.value * 0.65; // 65vh in pixels
  return spacingHeight + 50; // 65vh + 50px
});

// Infinite scroll
onMounted(() => {
  // Initialize window height
  updateWindowHeight();

  const { reset } = useInfiniteScroll(window, loadMore, {
    distance: triggerDistance.value,
    canLoadMore: () => hasMore.value && !cardStore.isLoading.value,
  });

  // Handle window resize and recreate infinite scroll with new distance
  const handleResize = () => {
    updateWindowHeight();
    // Reset and recreate with new distance
    reset();
    nextTick(() => {
      useInfiniteScroll(window, loadMore, {
        distance: triggerDistance.value,
        canLoadMore: () => hasMore.value && !cardStore.isLoading.value,
      });
    });
  };

  window.addEventListener("resize", handleResize);

  // Reset pagination when filters change
  watch(
    () => filter.filter.value,
    () => {
      reset();
      currentPage.value = 1;
    },
    { deep: true }
  );

  // Cleanup resize listener
  onUnmounted(() => {
    window.removeEventListener("resize", handleResize);
  });
});

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
        <p class="text-sm text-muted-foreground">Applying filters...</p>
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
        <p class="text-sm text-muted-foreground">Loading cards...</p>
      </div>
    </div>

    <!-- Cards grid -->
    <div
      v-else
      class="p-1 sm:p-2 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-1 sm:gap-2"
    >
      <template v-for="(item, index) in displayedCards" :key="item.id || index">
        <CardItem :item="item" class="aspect-400/559" />
      </template>
    </div>

    <!-- Load more indicator -->
    <div
      v-if="showLoadMoreIndicator"
      class="flex justify-center items-center py-8"
    >
      <div class="flex items-center gap-2">
        <div
          class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"
        ></div>
        <p class="text-sm text-muted-foreground">Loading more cards...</p>
      </div>
    </div>

    <!-- Results summary -->
    <div v-if="!showLoadingIndicator" class="flex justify-center py-4">
      <p class="text-sm text-muted-foreground">
        Showing {{ displayedCards.length }} of
        {{ cardStore.totalCards.value }} cards
        <span v-if="hasMore">(scroll for more)</span>
      </p>
    </div>

    <!-- No results message -->
    <div
      v-if="!showLoadingIndicator && displayedCards.length === 0"
      class="flex justify-center items-center min-h-[200px]"
    >
      <div class="text-center">
        <p class="text-lg font-medium text-muted-foreground">No cards found</p>
        <p class="text-sm text-muted-foreground mt-1">
          Try adjusting your filters
        </p>
      </div>
    </div>

    <div class="h-[65vh]"></div>
  </div>
</template>

<style scoped></style>
