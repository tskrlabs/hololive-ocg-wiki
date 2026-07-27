<script setup lang="ts">
// const { locale } = useI18n();
const filter = useFilter();

// Use API-based store instead of local processing
const cardStore = useCardStoreAPI();

// Local search value that user types into (not immediately applied to filter)
const localSearchValue = ref(filter.filter.value.search || "");

// Debounced function to update the actual filter value
const debouncedUpdateFilter = useDebounceFn(async (searchValue: string) => {
  // Update the actual filter value after debounce
  filter.filter.value.search = searchValue;

  // The card store should automatically react to filter changes
  // If not, we can trigger it manually here
}, 500);

// Watch local search input changes and debounce updates to filter
watch(localSearchValue, (newValue) => {
  debouncedUpdateFilter(newValue);
});

// Watch for external filter changes (e.g., when filter is reset)
// to sync the local input value
watch(
  () => filter.filter.value.search,
  (newValue) => {
    if (newValue !== localSearchValue.value) {
      localSearchValue.value = newValue || "";
    }
  }
);
</script>

<template>
  <div class="relative grow">
    <Input
      v-model="localSearchValue"
      id="search"
      type="text"
      :placeholder="$t('Search cards') + '...'"
      class="pr-8 w-full"
    />
    <div
      v-if="cardStore.isLoading.value"
      class="absolute right-2 top-1/2 transform -translate-y-1/2"
    >
      <div
        class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"
      ></div>
    </div>
  </div>
</template>
