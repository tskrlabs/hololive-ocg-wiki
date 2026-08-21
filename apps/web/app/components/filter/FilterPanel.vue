<script lang="ts" setup>
import { RotateCcw } from "lucide-vue-next";
import { FILTERABLE_COLORS } from "~/composables/filter-states";
import type { FilterSection } from "~/composables/filter-states";
import type { Locales } from "~/types/card";
import type { FilterOption } from "~/types/filter";

/**
 * The filter groups themselves — the body shared by the rail and the sheet (#36).
 *
 * `FilterAPI` used to be one 563-line component that was *both* the Sheet shell and the
 * groups inside it, so a persistent rail could only have been a second copy of all seven
 * groups. Splitting the body out is what makes the two surfaces the same controls in two
 * containers rather than two implementations that can drift.
 *
 * This component owns no container decisions: no width, no scrolling, no Apply footer.
 * Its parent places it.
 */

const { locale } = useI18n();
const filter = useFilter();
const { getTranslatedText } = useTranslation();
const icon = useGameIcon();

// Use draft filters for UI editing
const name = computed(() => filter.draftFilter.value.name);
const tag = computed(() => filter.draftFilter.value.tag);
const set = computed(() => filter.draftFilter.value.set);
const setCode = computed(() => filter.draftFilter.value.setCode);
const colors = computed(() => filter.draftFilter.value.colors);
const cardTypes = computed(() => filter.draftFilter.value.cardTypes);
const rarities = computed(() => filter.draftFilter.value.rarity);
const bloomLevel = computed(() => filter.draftFilter.value.bloomLevel);

/**
 * Which groups hold uncommitted edits (D10, #36 §5).
 *
 * In a rail the user sees the filters *and* the stale results at once — a gap that was
 * invisible inside a sheet, which showed one thing at a time and closed on Apply. One
 * global dot cannot say *which* of seven visible groups is the uncommitted one.
 */
const pending = filter.pending;

// Toggle states for dropdowns
const isNameOpen = ref(false);
const isTagOpen = ref(false);
const isSetOpen = ref(false);
const isSetCodeOpen = ref(false);

// Dropdown values, fetched through the one interface (Candidate 01).
//
// v1 called `$fetch("/api/filter-options")` right here, bypassing the store — which
// meant the store's own `getNameOptions` / `getTagOptions` / `getSetOptions` /
// `precomputeFilterOptions` had **no callers at all**, four methods maintained for a
// consumer that had gone its own way. `useCardQuery.filterOptions` caches per locale and
// dedupes concurrent calls, neither of which the hand-rolled version did.
const cardQuery = useCardQuery();

const nameFilterOptions = ref<FilterOption[]>([]);
const tagFilterOptions = ref<FilterOption[]>([]);
const setFilterOptions = ref<FilterOption[]>([]);
const setCodeFilterOptions = ref<FilterOption[]>([]);
const isLoadingFilterOptions = ref(false);

const loadAllFilterOptions = async () => {
  if (isLoadingFilterOptions.value) return;
  isLoadingFilterOptions.value = true;
  try {
    const options = await cardQuery.filterOptions(locale.value as Locales);
    nameFilterOptions.value = options.names;
    tagFilterOptions.value = options.tags;
    setFilterOptions.value = options.sets;
    // `?? []` — an artifact published before set codes existed has no such key, and the
    // site is served against whatever R2 currently holds.
    setCodeFilterOptions.value = options.set_codes ?? [];
  } finally {
    isLoadingFilterOptions.value = false;
  }
};
loadAllFilterOptions();

// Derived, not tracked separately: v1 kept an `optionsLoaded` flag beside the data and
// had to reset both on a locale change.
const optionsLoaded = computed(
  () =>
    nameFilterOptions.value.length > 0 ||
    tagFilterOptions.value.length > 0 ||
    setFilterOptions.value.length > 0,
);

// Refetch when the locale changes: the labels are translated, and the cache is keyed by
// locale so this is a hit after the first visit.
watch(() => locale.value, loadAllFilterOptions);

/** A group heading's classes — `--border-strong` when it holds uncommitted edits. */
const headingClass = (section: FilterSection) =>
  pending.value.has(section)
    ? "border-b border-border-strong pb-1 font-semibold"
    : "font-semibold";
</script>

<template>
  <div class="flex flex-col gap-6">
    <!--
      The option lists failed to load (#45).

      Without this the empty arrays render as "no filter options exist" — the same lie the
      card list used to tell, and worse here because the lists sit beside working
      controls, so nothing looks broken at all.
    -->
    <div
      v-if="cardQuery.optionsError.value"
      class="rounded-md border border-destructive/50 px-3 py-2"
    >
      <p class="text-sm font-medium">{{ $t("errors.filterOptions.title") }}</p>
      <p class="text-xs text-muted-foreground mt-0.5">
        {{ $t("errors.filterOptions.detail") }}
      </p>
      <Button
        variant="outline"
        size="sm"
        class="mt-2"
        @click="loadAllFilterOptions"
      >
        {{ $t("errors.retry") }}
      </Button>
    </div>

    <!--
      Each group's heading carries its own pending marker (D10).

      The marker is a border and a glyph, never a colour: D4's palette has no accent hue,
      so "uncommitted" has to be carried by weight and border — and the `.sr-only`
      "modified" is what makes it perceivable at all to a screen reader, which is the
      channel a purely visual dot never had.
    -->

    <!-- name -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('name')">
        {{ $t("fields.name") }}
        <span v-if="pending.has('name')" aria-hidden="true">•</span>
        <span v-if="pending.has('name')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.name') })"
          @click="filter.clear('name')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.name") }) }}
          </span>
        </button>
      </div>

      <Popover v-model:open="isNameOpen">
        <PopoverTrigger as-child>
          <Button variant="outline" size="sm" class="w-full justify-start">
            <template v-if="name">
              {{ getTranslatedText("names", name, name) }}
            </template>
            <template v-else> + {{ $t("fields.name") }} </template>
          </Button>
        </PopoverTrigger>
        <PopoverContent class="p-0" side="bottom" align="start" avoid-collisions>
          <div
            v-if="isLoadingFilterOptions && !optionsLoaded"
            class="p-2 text-center text-sm text-muted-foreground"
          >
            <div
              class="animate-spin h-4 w-4 border border-primary rounded-full inline-block mr-2 border-t-transparent"
            />
            {{ $t("Loading") }}...
          </div>
          <Command v-else-if="optionsLoaded" v-model="filter.draftFilter.value.name">
            <CommandInput :placeholder="$t('Change name') + '...'" />
            <CommandList>
              <CommandEmpty>{{ $t("No results found.") }}</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  v-for="nameOption in nameFilterOptions"
                  :key="nameOption.value"
                  :value="nameOption.value"
                  @select="() => { isNameOpen = false; }"
                >
                  {{ getTranslatedText("names", nameOption.value, nameOption.label) }}
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>

    <!-- tag -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('tag')">
        {{ $t("fields.tags") }}
        <span v-if="pending.has('tag')" aria-hidden="true">•</span>
        <span v-if="pending.has('tag')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.tags') })"
          @click="filter.clear('tag')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.tags") }) }}
          </span>
        </button>
      </div>

      <Popover v-model:open="isTagOpen">
        <PopoverTrigger as-child>
          <Button variant="outline" size="sm" class="w-full justify-start">
            <template v-if="tag">
              {{ getTranslatedText("tags", tag, tag) }}
            </template>
            <template v-else> + {{ $t("fields.tags") }} </template>
          </Button>
        </PopoverTrigger>
        <PopoverContent class="p-0" side="bottom" align="start" avoid-collisions>
          <div
            v-if="isLoadingFilterOptions && !optionsLoaded"
            class="p-2 text-center text-sm text-muted-foreground"
          >
            <div
              class="animate-spin h-4 w-4 border border-primary rounded-full inline-block mr-2 border-t-transparent"
            />
            {{ $t("Loading") }}...
          </div>
          <Command v-else-if="optionsLoaded" v-model="filter.draftFilter.value.tag">
            <CommandInput :placeholder="$t('Change tag') + '...'" />
            <CommandList>
              <CommandEmpty>{{ $t("No results found.") }}</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  v-for="tagOption in tagFilterOptions"
                  :key="tagOption.value"
                  :value="tagOption.value"
                  @select="() => { isTagOpen = false; }"
                >
                  {{ getTranslatedText("tags", tagOption.value, tagOption.label) }}
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>

    <!--
      set code — the printed code (`hBP03`), above the product-set group.

      A separate group from `set` rather than an option inside it, because they are
      different taxonomies: hBP03 is 283 cards, the "Elite Spark" product is 244, and
      only 229 are both. One control returning two different answer shapes would be
      impossible to explain.

      No `getTranslatedText`: the code *is* the label in every locale.
    -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('setCode')">
        {{ $t("fields.setCode") }}
        <span v-if="pending.has('setCode')" aria-hidden="true">•</span>
        <span v-if="pending.has('setCode')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.setCode') })"
          @click="filter.clear('setCode')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.setCode") }) }}
          </span>
        </button>
      </div>

      <Popover v-model:open="isSetCodeOpen">
        <PopoverTrigger as-child>
          <Button variant="outline" size="sm" class="w-full justify-start">
            <template v-if="setCode">{{ setCode }}</template>
            <template v-else> + {{ $t("fields.setCode") }} </template>
          </Button>
        </PopoverTrigger>
        <PopoverContent class="p-0" side="bottom" align="start" avoid-collisions>
          <div
            v-if="isLoadingFilterOptions && !optionsLoaded"
            class="p-2 text-center text-sm text-muted-foreground"
          >
            <div
              class="animate-spin h-4 w-4 border border-primary rounded-full inline-block mr-2 border-t-transparent"
            />
            {{ $t("Loading") }}...
          </div>
          <!--
            Guarded on the list being non-empty, not just on `optionsLoaded`: R2 may still
            hold an artifact published before set codes existed, and an empty picker with
            a working search box beside it is the same silent lie #45 fixed.
          -->
          <Command
            v-else-if="setCodeFilterOptions.length"
            v-model="filter.draftFilter.value.setCode"
          >
            <CommandInput :placeholder="$t('Change set code') + '...'" />
            <CommandList>
              <CommandEmpty>{{ $t("No results found.") }}</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  v-for="option in setCodeFilterOptions"
                  :key="option.value"
                  :value="option.value"
                  @select="() => { isSetCodeOpen = false; }"
                >
                  {{ option.label }}
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>

    <!-- set -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('set')">
        {{ $t("fields.set") }}
        <span v-if="pending.has('set')" aria-hidden="true">•</span>
        <span v-if="pending.has('set')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.set') })"
          @click="filter.clear('set')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.set") }) }}
          </span>
        </button>
      </div>

      <Popover v-model:open="isSetOpen">
        <PopoverTrigger as-child>
          <Button variant="outline" size="sm" class="w-full justify-start">
            <template v-if="set">
              {{ getTranslatedText("sets", set, set) }}
            </template>
            <template v-else> + {{ $t("fields.set") }} </template>
          </Button>
        </PopoverTrigger>
        <PopoverContent class="p-0" side="bottom" align="start" avoid-collisions>
          <div
            v-if="isLoadingFilterOptions && !optionsLoaded"
            class="p-2 text-center text-sm text-muted-foreground"
          >
            <div
              class="animate-spin h-4 w-4 border border-primary rounded-full inline-block mr-2 border-t-transparent"
            />
            {{ $t("Loading") }}...
          </div>
          <Command v-else-if="optionsLoaded" v-model="filter.draftFilter.value.set">
            <CommandInput :placeholder="$t('Change set') + '...'" />
            <CommandList>
              <CommandEmpty>{{ $t("No results found.") }}</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  v-for="setOption in setFilterOptions"
                  :key="setOption.value"
                  :value="setOption.value"
                  @select="() => { isSetOpen = false; }"
                >
                  {{ getTranslatedText("sets", setOption.value, setOption.label) }}
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>

    <!-- color -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('colors')">
        {{ $t("fields.color") }}
        <span v-if="pending.has('colors')" aria-hidden="true">•</span>
        <span v-if="pending.has('colors')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.color') })"
          @click="filter.clear('colors')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.color") }) }}
          </span>
        </button>
      </div>
      <div class="flex flex-wrap gap-2">
        <!--
          Iterates FILTERABLE_COLORS, not the filter state, so the checkbox set is a
          property of the contract rather than of whatever the state happens to hold.
          A dual-colour card carries a row per badge (ADR 0013), so it turns up under
          each of its colours without a checkbox of its own.
        -->
        <template v-for="key in FILTERABLE_COLORS" :key="key">
          <Toggle
            :model-value="!!colors[key]"
            size="sm"
            variant="outline"
            :aria-label="$t(`colors.${key}`)"
            @update:model-value="(val: boolean) => (colors[key] = val)"
          >
            <Image :src="icon.color(key)" :img-attributes="{ class: 'w-4' }" />
            {{ $t(`colors.${key}`) }}
          </Toggle>
        </template>
      </div>
    </div>

    <!-- card type -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('cardTypes')">
        {{ $t("fields.cardType") }}
        <span v-if="pending.has('cardTypes')" aria-hidden="true">•</span>
        <span v-if="pending.has('cardTypes')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.cardType') })"
          @click="filter.clear('cardTypes')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.cardType") }) }}
          </span>
        </button>
      </div>
      <div class="flex flex-wrap gap-2">
        <template v-for="(type, key) in cardTypes" :key="key">
          <Toggle
            :model-value="!!cardTypes[key]"
            size="sm"
            variant="outline"
            :aria-label="$t(`cardTypes.${key}`)"
            @update:model-value="(val: boolean) => (cardTypes[key] = val)"
          >
            {{ $t(`cardTypes.${key}`) }}
          </Toggle>
        </template>
      </div>
    </div>

    <!-- rarity -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('rarity')">
        {{ $t("fields.rarity") }}
        <span v-if="pending.has('rarity')" aria-hidden="true">•</span>
        <span v-if="pending.has('rarity')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.rarity') })"
          @click="filter.clear('rarity')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.rarity") }) }}
          </span>
        </button>
      </div>
      <div class="flex flex-wrap gap-2">
        <template v-for="(rarity, key) in rarities" :key="key">
          <Toggle
            :model-value="!!rarities[key]"
            size="sm"
            variant="outline"
            :aria-label="$t(`rarity.${key}`)"
            @update:model-value="(val: boolean) => (rarities[key] = val)"
          >
            {{ $t(`rarity.${key}`) }}
          </Toggle>
        </template>
      </div>
    </div>

    <!-- bloom level -->
    <div>
      <div class="flex items-center gap-2 mb-2" :class="headingClass('bloomLevel')">
        {{ $t("fields.bloomLevel") }}
        <span v-if="pending.has('bloomLevel')" aria-hidden="true">•</span>
        <span v-if="pending.has('bloomLevel')" class="sr-only">
          {{ $t("filter.modified") }}
        </span>

        <button
          class="ml-auto"
          :title="$t('filter.clearGroup', { group: $t('fields.bloomLevel') })"
          @click="filter.clear('bloomLevel')"
        >
          <RotateCcw class="size-4" aria-hidden="true" />
          <span class="sr-only">
            {{ $t("filter.clearGroup", { group: $t("fields.bloomLevel") }) }}
          </span>
        </button>
      </div>
      <div class="flex flex-wrap gap-2">
        <template v-for="(level, key) in bloomLevel" :key="key">
          <Toggle
            :model-value="!!bloomLevel[key]"
            size="sm"
            variant="outline"
            :aria-label="$t(`bloomLevel.${key}`)"
            @update:model-value="(val: boolean) => (bloomLevel[key] = val)"
          >
            {{ $t(`bloomLevel.${key}`) }}
          </Toggle>
        </template>
      </div>
    </div>
  </div>
</template>
