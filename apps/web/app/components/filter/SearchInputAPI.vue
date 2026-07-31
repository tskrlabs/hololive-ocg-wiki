<script setup lang="ts">
/**
 * The card search box.
 *
 * Rendered **twice** from `lg` up — once in the header for mobile and once in the rail
 * for desktop — with CSS choosing which is visible (#36 §4). That is why the input's id
 * is generated rather than the hardcoded `id="search"` it was: two elements sharing an id
 * is invalid HTML, and `<label for>` and `aria-describedby` both resolve to whichever the
 * browser finds first, which is not necessarily the visible one.
 *
 * Search stays outside the draft → apply flow deliberately (#36 §5). It is already
 * debounced and applies as you type; routing it through Apply would be a regression.
 */
const filter = useFilter();

// Use API-based store instead of local processing
const cardQuery = useCardQuery();

/** Unique per instance, so the two copies never collide. */
const inputId = useId();

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
    <label :for="inputId" class="sr-only">{{ $t("Search cards") }}</label>
    <Input
      :id="inputId"
      v-model="localSearchValue"
      type="search"
      :placeholder="$t('Search cards') + '...'"
      class="pr-8 w-full"
    />
    <div
      v-if="cardQuery.isLoading.value"
      class="absolute right-2 top-1/2 transform -translate-y-1/2"
    >
      <div
        class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"
      ></div>
    </div>
  </div>
</template>
