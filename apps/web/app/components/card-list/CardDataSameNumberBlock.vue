<script lang="ts" setup>
const cardImage = useCardImage();
import { SwatchBook } from "lucide-vue-next";
import type { Card, CardCollection } from "@/types/card";

const { locale } = useI18n();
const { getCardsByCardNumber } = useCardStoreAPI();

const props = defineProps<{
  item: Card;
}>();

// State for same number cards
const sameNumberCards = ref<CardCollection>([]);
const isLoading = ref(false);
const error = ref<string | null>(null);
const accordionValue = ref<string>("");
const hasDataLoaded = ref(false);

// Fetch cards with same card number
const fetchSameNumberCards = async () => {
  if (!props.item?.card_number || hasDataLoaded.value) return;

  isLoading.value = true;
  error.value = null;

  try {
    const cards = await getCardsByCardNumber(
      props.item.card_number,
      locale.value as any
    );
    // Filter out the current card to avoid showing duplicates
    sameNumberCards.value = cards.filter((card) => card.id !== props.item.id);
    hasDataLoaded.value = true;
  } catch (err) {
    console.error("Failed to fetch same number cards:", err);
    error.value = "Failed to load cards";
  } finally {
    isLoading.value = false;
  }
};

// Watch for accordion open state and fetch data when opened
watch(accordionValue, (newValue) => {
  if (newValue === "item-1" && !hasDataLoaded.value) {
    fetchSameNumberCards();
  }
});

// Watch for changes in card number or locale and reset data
watch([() => props.item?.card_number, locale], () => {
  hasDataLoaded.value = false;
  sameNumberCards.value = [];
  error.value = null;
  if (accordionValue.value === "item-1") {
    fetchSameNumberCards();
  }
});

// Computed property to check if we should show the component
const shouldShowComponent = computed(() => {
  return props.item?.card_number; // Show if there's a card number
});
</script>

<template>
  <div v-if="shouldShowComponent" class="">
    <Accordion type="single" collapsible v-model="accordionValue">
      <AccordionItem value="item-1">
        <AccordionTrigger
          class="flex gap-2 p-2 rounded-lg border bg-accent/50 hover:no-underline"
        >
          <div class="flex text-sm gap-2">
            <SwatchBook class="size-5" /> {{ $t("Same Number Cards") }}
            <span
              v-if="!isLoading && sameNumberCards.length > 0"
              class="text-muted-foreground"
            >
              ({{ sameNumberCards.length }})
            </span>
          </div>
        </AccordionTrigger>
        <AccordionContent
          class="pb-0 pt-2 md:pt-4 flex flex-col gap-2 md:gap-4"
        >
          <!-- Loading state -->
          <div v-if="isLoading" class="flex justify-center p-4">
            <div class="text-sm text-muted-foreground">
              {{ $t("Loading") }}...
            </div>
          </div>

          <!-- Error state -->
          <div v-else-if="error" class="flex justify-center p-4">
            <div class="text-sm text-destructive">{{ error }}</div>
          </div>

          <!-- Cards grid -->
          <div
            v-else-if="sameNumberCards.length > 0"
            class="grid grid-cols-2 sm:grid-cols-3 gap-2 md:gap-4"
          >
            <template v-for="card in sameNumberCards" :key="card.id">
              <div class="relative flex aspect-400/559">
                <Dialog>
                  <DialogTrigger class="w-full">
                    <SimpleImage
                      class="rounded-lg overflow-hidden"
                      :src="cardImage(card.image_key)"
                      :img-attributes="{ class: 'w-full h-full object-cover' }"
                    />
                  </DialogTrigger>
                  <CardItemDialogContent :item="card" />
                </Dialog>

                <!-- Card info overlay -->
                <!-- <div
                  class="absolute bottom-0 left-0 right-0 bg-black/70 text-white p-1 rounded-b-lg"
                >
                  <div class="text-xs truncate font-medium">
                    {{ card.name }}
                  </div>
                  <div class="text-xs text-gray-300">
                    {{ card.card_number }}
                  </div>
                </div> -->
              </div>
            </template>
          </div>

          <!-- No cards found (shouldn't happen due to shouldShowComponent) -->
          <div v-else class="flex justify-center p-4">
            <div class="text-sm text-muted-foreground">
              {{ $t("No other cards found with the same number") }}
            </div>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  </div>
</template>
