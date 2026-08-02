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
 *
 * **The root carries no `grow`, and that is load-bearing** — it is a sizing decision that
 * belongs to whoever places this. The header lays out in a *row*, where `grow` means "take
 * the width the icon buttons leave"; the rail lays out in a *column*, where the same
 * declaration means "take the height the filter groups leave". It did, and the `h-9` input
 * inside did not follow, leaving a band of dead space between the field and the result
 * count. `index.vue` states the header's stretch on the wrapper it already owns.
 *
 * The tell was that it came and went: `flex-grow` only acts on *free* space, so a short
 * viewport whose groups overflowed showed nothing wrong at all.
 */
import { matchSetCode } from "~/composables/filter-states";
import type { Locales } from "~/types/card";

const filter = useFilter();

// Use API-based store instead of local processing
const cardQuery = useCardQuery();

const { locale } = useI18n();

/** Unique per instance, so the two copies never collide. */
const inputId = useId();

// Local search value that user types into (not immediately applied to filter)
const localSearchValue = ref(filter.filter.value.search || "");

/**
 * The known set codes, for the routing rule below.
 *
 * From the same cached `filterOptions` call the panel makes, so this costs no extra
 * request — and it means the rule is driven by the shipped data rather than a list
 * compiled into the bundle, which would go stale the day a set releases.
 */
const setCodes = ref<string[]>([]);
watchEffect(async () => {
  const options = await cardQuery.filterOptions(locale.value as Locales);
  setCodes.value = (options.set_codes ?? []).map((entry) => entry.value);
});

// Debounced function to update the actual filter value
const debouncedUpdateFilter = useDebounceFn(async (searchValue: string) => {
  // A typed set code becomes the set-code *filter*, not a search (ADR 0010).
  //
  // The box is cleared rather than left showing the code: the constraint is now visible
  // as a filter group with its own clear button, and leaving the text behind would put
  // one constraint in two places where clearing either leaves the other — the exact
  // split-state bug the draft/applied separation exists to prevent.
  const code = matchSetCode(searchValue, setCodes.value);
  if (code) {
    filter.filter.value.search = "";
    filter.filter.value.setCode = code;
    // The draft has to move too, or opening the panel would show the old value and
    // "Apply" would silently undo the routing.
    filter.draftFilter.value.setCode = code;

    // `await nextTick()` before clearing, and it is load-bearing rather than tidy.
    //
    // The field is a child component holding `modelValue`. Writing "" in the same tick
    // that the input event was processed means the child's prop goes `"hBP03"` → `""`
    // within one render pass, so Vue reconciles against a value the DOM node never
    // received and skips the patch — state reads empty while the box still shows
    // `hBP03`. Letting the tick complete gives the child a prop change it can act on.
    //
    // In production the 500 ms debounce already puts this in a later tick, which is
    // exactly why the bug is invisible there and would surface on any change to the
    // debounce. Found by the mounted test, which runs the callback synchronously.
    await nextTick();
    localSearchValue.value = "";
    return;
  }

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
  <div class="relative">
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
