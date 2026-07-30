<script lang="ts" setup>
import { Funnel, PanelTopClose, RotateCcw } from "lucide-vue-next";
import { FILTERABLE_COLORS } from "~/composables/filter-states";
import type { Locales } from "~/types/card";
import type { FilterOption } from "~/types/filter";

const { locale, t } = useI18n();

// filter
const filter = useFilter();

// Use translation composable
const { getTranslatedText } = useTranslation();

const icon = useGameIcon();

// Use draft filters for UI editing
const name = computed(() => filter.draftFilter.value.name);
const tag = computed(() => filter.draftFilter.value.tag);
const set = computed(() => filter.draftFilter.value.set);
const colors = computed(() => filter.draftFilter.value.colors);
const cardTypes = computed(() => filter.draftFilter.value.cardTypes);
const rarities = computed(() => filter.draftFilter.value.rarity);
const bloomLevel = computed(() => filter.draftFilter.value.bloomLevel);

// Check if applied filters are active (for the red dot indicator)
const isFiltered = computed(() => filter.isFiltered());
// Check if there are pending changes
const hasPendingChanges = computed(() => filter.hasPendingChanges.value);

// For the API version, we'll use the existing filter logic
// but fetch options from the API when needed
const isLoading = ref(false);

// Filter application loading state
const isApplyingFilters = ref(false);

// Toggle states for dropdowns
const isNameOpen = ref(false);
const isTagOpen = ref(false);
const isSetOpen = ref(false);

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
const isLoadingFilterOptions = ref(false);

const loadAllFilterOptions = async () => {
  if (isLoadingFilterOptions.value) return;
  isLoadingFilterOptions.value = true;
  try {
    const options = await cardQuery.filterOptions(locale.value as Locales);
    nameFilterOptions.value = options.names;
    tagFilterOptions.value = options.tags;
    setFilterOptions.value = options.sets;
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

// Initialize draft filters when component mounts
onMounted(() => {
  filter.initializeDraftFilters();
});

// Handle filter application
const handleApplyFilters = async () => {
  // Check if there are any pending changes before applying
  if (!hasPendingChanges.value) {
    console.log(t("No filter changes detected, skipping filter application"));
    return;
  }

  isApplyingFilters.value = true;
  try {
    await filter.applyFilters();
    // Close the sheet after applying filters
    // The parent SheetClose will handle this
  } finally {
    isApplyingFilters.value = false;
  }
};

// Cancel: throw the draft away and start again from what is applied.
const handleCancel = () => {
  filter.initializeDraftFilters();
};

// Reset all: blank the draft. The applied filters stay until Apply is pressed.
const handleResetAll = () => {
  filter.clear();
};
</script>

<template>
  <Sheet>
    <SheetTrigger as-child>
      <Button size="icon" class="relative">
        <!-- filtered dot -->
        <div
          v-if="isFiltered"
          class="absolute left-0 top-0 -translate-2/4 size-2.5 bg-red-500 rounded-full"
        ></div>

        <Funnel />
      </Button>
    </SheetTrigger>
    <SheetContent side="top" hide-top-right-close>
      <DialogHeader class="h-0 overflow-hidden">
        <DialogTitle>{{ $t("Filter") }}</DialogTitle>
        <DialogDescription>{{ $t("Filter") }}</DialogDescription>
      </DialogHeader>

      <!-- Add loading overlay for filter application -->
      <div
        v-if="isLoading || isApplyingFilters"
        class="absolute inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center"
      >
        <div class="flex flex-col items-center gap-2">
          <div
            class="animate-spin h-8 w-8 border-4 border-primary rounded-full border-t-transparent"
          ></div>
          <span class="text-sm text-muted-foreground">{{
            isApplyingFilters
              ? `${$t("Applying filters")}...`
              : `${$t("Filtering")}...`
          }}</span>
        </div>
      </div>

      <div class="flex grow">
        <ScrollArea>
          <div class="w-full max-h-[calc(100dvh-96px-16px-16px)]">
            <!-- quick filters -->
            <div class="flex flex-col gap-4 pt-4 px-4">
              <!-- name -->
              <div class="">
                <div class="flex items-center gap-2 font-semibold mb-2">
                  {{ $t("fields.name") }}

                  <button @click="filter.clear('name')">
                    <RotateCcw class="size-4" />
                  </button>
                </div>

                <Popover v-model:open="isNameOpen">
                  <PopoverTrigger as-child>
                    <Button
                      variant="outline"
                      size="sm"
                      class="w-max justify-start"
                    >
                      <template v-if="name">
                        {{ getTranslatedText("names", name, name) }}
                      </template>
                      <template v-else> + {{ $t("fields.name") }} </template>
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent
                    class="p-0"
                    side="bottom"
                    align="start"
                    avoid-collisions
                  >
                    <div
                      v-if="isLoadingFilterOptions && !optionsLoaded"
                      class="p-2 text-center text-sm text-muted-foreground"
                    >
                      <div
                        class="animate-spin h-4 w-4 border border-primary rounded-full inline-block mr-2 border-t-transparent"
                      />
                      {{ $t("Loading") }}...
                    </div>
                    <Command
                      v-else-if="optionsLoaded"
                      v-model="filter.draftFilter.value.name"
                    >
                      <CommandInput :placeholder="$t('Change name') + '...'" />
                      <CommandList>
                        <CommandEmpty>
                          {{ $t("No results found.") }}
                        </CommandEmpty>
                        <CommandGroup>
                          <CommandItem
                            v-for="nameOption in nameFilterOptions"
                            :key="nameOption.value"
                            :value="nameOption.value"
                            @select="
                              () => {
                                isNameOpen = false;
                              }
                            "
                          >
                            {{
                              getTranslatedText(
                                "names",
                                nameOption.value,
                                nameOption.label
                              )
                            }}
                          </CommandItem>
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>

              <!-- tag -->
              <div class="">
                <div class="flex items-center gap-2 font-semibold mb-2">
                  {{ $t("fields.tags") }}

                  <button @click="filter.clear('tag')">
                    <RotateCcw class="size-4" />
                  </button>
                </div>

                <Popover v-model:open="isTagOpen">
                  <PopoverTrigger as-child>
                    <Button
                      variant="outline"
                      size="sm"
                      class="w-max justify-start"
                    >
                      <template v-if="tag">
                        {{ getTranslatedText("tags", tag, tag) }}
                      </template>
                      <template v-else> + {{ $t("fields.tags") }} </template>
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent
                    class="p-0"
                    side="bottom"
                    align="start"
                    avoid-collisions
                  >
                    <div
                      v-if="isLoadingFilterOptions && !optionsLoaded"
                      class="p-2 text-center text-sm text-muted-foreground"
                    >
                      <div
                        class="animate-spin h-4 w-4 border border-primary rounded-full inline-block mr-2 border-t-transparent"
                      />
                      {{ $t("Loading") }}...
                    </div>
                    <Command
                      v-else-if="optionsLoaded"
                      v-model="filter.draftFilter.value.tag"
                    >
                      <CommandInput :placeholder="$t('Change tag') + '...'" />
                      <CommandList>
                        <CommandEmpty>
                          {{ $t("No results found.") }}
                        </CommandEmpty>
                        <CommandGroup>
                          <CommandItem
                            v-for="tagOption in tagFilterOptions"
                            :key="tagOption.value"
                            :value="tagOption.value"
                            @select="
                              () => {
                                isTagOpen = false;
                              }
                            "
                          >
                            {{
                              getTranslatedText(
                                "tags",
                                tagOption.value,
                                tagOption.label
                              )
                            }}
                          </CommandItem>
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>

              <!-- set -->
              <div class="">
                <div class="flex items-center gap-2 font-semibold mb-2">
                  {{ $t("fields.set") }}

                  <button @click="filter.clear('set')">
                    <RotateCcw class="size-4" />
                  </button>
                </div>

                <Popover v-model:open="isSetOpen">
                  <PopoverTrigger as-child>
                    <Button
                      variant="outline"
                      size="sm"
                      class="w-max justify-start"
                    >
                      <template v-if="set">
                        {{ getTranslatedText("sets", set, set) }}
                      </template>
                      <template v-else> + {{ $t("fields.set") }} </template>
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent
                    class="p-0"
                    side="bottom"
                    align="start"
                    avoid-collisions
                  >
                    <div
                      v-if="isLoadingFilterOptions && !optionsLoaded"
                      class="p-2 text-center text-sm text-muted-foreground"
                    >
                      <div
                        class="animate-spin h-4 w-4 border border-primary rounded-full inline-block mr-2 border-t-transparent"
                      />
                      {{ $t("Loading") }}...
                    </div>
                    <Command
                      v-else-if="optionsLoaded"
                      v-model="filter.draftFilter.value.set"
                    >
                      <CommandInput :placeholder="$t('Change set') + '...'" />
                      <CommandList>
                        <CommandEmpty>
                          {{ $t("No results found.") }}
                        </CommandEmpty>
                        <CommandGroup>
                          <CommandItem
                            v-for="setOption in setFilterOptions"
                            :key="setOption.value"
                            :value="setOption.value"
                            @select="
                              () => {
                                isSetOpen = false;
                              }
                            "
                          >
                            {{
                              getTranslatedText(
                                "sets",
                                setOption.value,
                                setOption.label
                              )
                            }}
                          </CommandItem>
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>

              <!-- color -->
              <div class="">
                <div class="flex items-center gap-2 font-semibold mb-2">
                  {{ $t("fields.color") }}

                  <button @click="filter.clear('colors')">
                    <RotateCcw class="size-4" />
                  </button>
                </div>
                <div class="flex flex-wrap gap-2">
                  <!--
                    Iterates FILTERABLE_COLORS, not the filter state: the fused symbols
                    (blue_red, white_green) get no checkbox of their own. The Worker
                    expands a colour filter through FUSED_COLORS, so those cards already
                    appear under both constituent colours (F-016).
                  -->
                  <template v-for="key in FILTERABLE_COLORS" :key="key">
                    <Toggle
                      :model-value="!!colors[key]"
                      @update:model-value="(val: boolean) => (colors[key] = val)"
                      size="sm"
                      variant="outline"
                      aria-label="Toggle Colors"
                    >
                      <Image
                        :src="icon.color(key)"
                        :img-attributes="{ class: 'w-4' }"
                      />

                      {{ $t(`colors.${key}`) }}
                    </Toggle>
                  </template>
                </div>
              </div>

              <!-- CardTypeCodeType -->
              <div class="">
                <div class="flex items-center gap-2 font-semibold mb-2">
                  {{ $t("fields.cardType") }}

                  <button @click="filter.clear('cardTypes')">
                    <RotateCcw class="size-4" />
                  </button>
                </div>
                <div class="flex flex-wrap gap-2">
                  <template v-for="(type, key) in cardTypes" :key="key">
                    <Toggle
                      :model-value="!!cardTypes[key]"
                      @update:model-value="(val: boolean) => (cardTypes[key] = val)"
                      size="sm"
                      variant="outline"
                      aria-label="Toggle Types"
                    >
                      {{ $t(`cardTypes.${key}`) }}
                    </Toggle>
                  </template>
                </div>
              </div>

              <!-- Rarity -->
              <div class="">
                <div class="flex items-center gap-2 font-semibold mb-2">
                  {{ $t("fields.rarity") }}

                  <button @click="filter.clear('rarity')">
                    <RotateCcw class="size-4" />
                  </button>
                </div>
                <div class="flex flex-wrap gap-2">
                  <template v-for="(rarity, key) in rarities" :key="key">
                    <Toggle
                      :model-value="!!rarities[key]"
                      @update:model-value="(val: boolean) => (rarities[key] = val)"
                      size="sm"
                      variant="outline"
                      aria-label="Toggle Rarity"
                    >
                      {{ $t(`rarity.${key}`) }}
                    </Toggle>
                  </template>
                </div>
              </div>

              <!-- bloomLevel -->
              <div class="">
                <div class="flex items-center gap-2 font-semibold mb-2">
                  {{ $t("fields.bloomLevel") }}

                  <button @click="filter.clear('bloomLevel')">
                    <RotateCcw class="size-4" />
                  </button>
                </div>
                <div class="flex flex-wrap gap-2">
                  <template v-for="(level, key) in bloomLevel" :key="key">
                    <Toggle
                      :model-value="!!bloomLevel[key]"
                      @update:model-value="(val: boolean) => (bloomLevel[key] = val)"
                      size="sm"
                      variant="outline"
                      aria-label="Toggle Bloom Level"
                    >
                      {{ $t(`bloomLevel.${key}`) }}
                    </Toggle>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </ScrollArea>
      </div>

      <SheetFooter class="pt-0 md:pt-4">
        <div class="flex flex-wrap items-center w-full gap-2">
          <!-- Show filter button only when there are pending changes -->
          <SheetClose as-child>
            <Button
              class="grow w-full"
              @click="handleApplyFilters"
              :disabled="isApplyingFilters || !hasPendingChanges"
            >
              <Funnel />
              <template v-if="hasPendingChanges">
                {{ $t("Apply Filters") }}
              </template>
              <template v-else> {{ $t("No Changes") }} </template>
            </Button>
          </SheetClose>

          <Button class="grow" variant="outline" @click="handleResetAll">
            <RotateCcw /> {{ $t("Reset") }}
          </Button>

          <SheetClose as-child>
            <Button class="grow" variant="outline" @click="handleCancel">
              <PanelTopClose /> {{ $t("Close") }}
            </Button>
          </SheetClose>
        </div>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
