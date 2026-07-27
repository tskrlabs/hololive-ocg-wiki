<script setup lang="ts">
import { useDebounceFn } from "@vueuse/core";

const { locale } = useI18n();
const filter = useFilter();
const cardStore = useCardStoreAPI(); // Use the new API-based store

// Pagination state
const pageSize = ref(500); // Reduced for better API performance
const currentPage = ref(1);
const hasMore = computed(() => {
  return cardStore.filteredCards.value.length < cardStore.totalCards.value;
});

// Debounced filter application
const applyFilters = useDebounceFn(async () => {
  currentPage.value = 1;
  await cardStore.getFilteredCards(
    filter.filter.value,
    locale.value,
    1,
    pageSize.value
  );
}, 300); // Slightly increased debounce for API calls

// Load more cards for infinite scroll
const loadMore = async () => {
  if (cardStore.isLoading.value || !hasMore.value) return;

  currentPage.value++;
  await cardStore.loadMoreCards(
    filter.filter.value,
    locale.value,
    currentPage.value
  );
};

// Apply filters when filter changes
watch(() => filter.filter.value, applyFilters, { deep: true });

// Also update when locale changes
watch(
  () => locale.value,
  () => {
    cardStore.clearCache();
    applyFilters();
  }
);

// Initial filter application
onMounted(() => {
  applyFilters();
});

// Use the filtered cards from the store
const displayedCards = computed(() => cardStore.filteredCards.value);

// Infinite scroll
onMounted(() => {
  const { reset } = useInfiniteScroll(window, loadMore, {
    distance: 10,
    canLoadMore: () => hasMore.value && !cardStore.isLoading.value,
  });

  // Reset pagination when filters change
  watch(
    () => filter.filter.value,
    () => {
      reset();
      currentPage.value = 1;
    },
    { deep: true }
  );
});

// Loading state for better UX
const showLoadingIndicator = computed(() => {
  return cardStore.isLoading.value && displayedCards.value.length === 0;
});

const showLoadMoreIndicator = computed(() => {
  return cardStore.isLoading.value && displayedCards.value.length > 0;
});
</script>

<template>
  <div>
    <!-- Loading indicator for initial load -->
    <div
      v-if="showLoadingIndicator"
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
