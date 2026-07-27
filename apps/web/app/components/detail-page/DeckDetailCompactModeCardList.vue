<script setup lang="ts">
import type { Card } from "~/types/card";

const props = defineProps<{
  oshiCardIds: string[];
  mainCardIds: string[];
  yellCardIds: string[];
}>();

const cardQuery = useCardQuery();
const isLoading = ref(true);
const oshiCards = ref<Card[]>([]);
const mainCards = ref<Card[]>([]);
const yellCards = ref<Card[]>([]);
const { locale } = useI18n();

// Group cards by ID and count occurrences
const uniqueCards = computed(() => {
  return (cardIds: string[], cards: Card[]) => {
    const cardMap = new Map();

    // Skip processing if there are no card IDs
    if (!cardIds.length || !cards.length) return [];

    // Collect card IDs and count occurrences
    cardIds.forEach((cardId) => {
      if (!cardMap.has(cardId)) {
        cardMap.set(cardId, { cardId, count: 0 });
      }
      cardMap.get(cardId).count++;
    });

    // Get unique card IDs for efficient lookup
    const uniqueCardIds = Array.from(cardMap.keys());

    // Create a result array with card data and counts
    return uniqueCardIds
      .map((cardId) => {
        const card = cards.find((c) => c.id === cardId);
        if (!card) return null;
        const count = cardMap.get(cardId).count;
        return {
          cardId: card.id,
          count,
          card,
        };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null);
  };
});

// Computed properties for each deck type
const uniqueOshiCards = computed(() =>
  uniqueCards.value(props.oshiCardIds, oshiCards.value)
);
const uniqueMainCards = computed(() =>
  uniqueCards.value(props.mainCardIds, mainCards.value)
);
const uniqueYellCards = computed(() =>
  uniqueCards.value(props.yellCardIds, yellCards.value)
);

// Watch for changes in card IDs and fetch cards
watch(
  [() => props.oshiCardIds, () => props.mainCardIds, () => props.yellCardIds],
  async ([newOshiIds, newMainIds, newYellIds]) => {
    isLoading.value = true;

    try {
      // Get unique card IDs for each deck type
      const uniqueOshiIds = [...new Set(newOshiIds)];
      const uniqueMainIds = [...new Set(newMainIds)];
      const uniqueYellIds = [...new Set(newYellIds)];

      // Fetch cards for each deck type
      const [fetchedOshiCards, fetchedMainCards, fetchedYellCards] =
        await Promise.all([
          uniqueOshiIds.length > 0
            ? cardQuery.getCardsByIds(uniqueOshiIds, locale.value)
            : [],
          uniqueMainIds.length > 0
            ? cardQuery.getCardsByIds(uniqueMainIds, locale.value)
            : [],
          uniqueYellIds.length > 0
            ? cardQuery.getCardsByIds(uniqueYellIds, locale.value)
            : [],
        ]);

      oshiCards.value = fetchedOshiCards || [];
      mainCards.value = fetchedMainCards || [];
      yellCards.value = fetchedYellCards || [];
    } catch (error) {
      console.error("Failed to fetch cards:", error);
      oshiCards.value = [];
      mainCards.value = [];
      yellCards.value = [];
    } finally {
      isLoading.value = false;
    }
  },
  { immediate: true, deep: true }
);

// As in the other deck lists, but over a list passed per section (D9).
const cardImage = useCardImage();
const getImagePath = (cardId: string, cards: Card[]) =>
  cardImage(cards.find((c) => c.id === cardId)?.image_key);
</script>

<template>
  <div v-if="isLoading" class="p-4 flex justify-center items-center">
    <div
      class="animate-spin h-6 w-6 border-2 border-primary rounded-full border-t-transparent"
    ></div>
  </div>

  <div
    v-else-if="
      uniqueOshiCards.length === 0 &&
      uniqueYellCards.length === 0 &&
      uniqueMainCards.length === 0
    "
    class="p-4 text-center text-sm text-gray-500"
  >
    {{ $t("No cards to display") }}
  </div>

  <div v-else>
    <div
      class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-12 gap-2"
    >
      <template v-for="(item, index) in uniqueOshiCards" :key="`oshi-${index}`">
        <div class="flex flex-col gap-2">
          <Badge class="px-1 text-md w-full">
            {{ $t("Oshi") }}
          </Badge>

          <div class="relative flex">
            <Dialog>
              <DialogTrigger class="w-full">
                <Image
                  class="flex-[0_0_400px] aspect-400/559"
                  :src="getImagePath(item.card.id, oshiCards)"
                  :img-attributes="{ class: '' }"
                />
              </DialogTrigger>

              <CardItemDialogContent :item="item.card" />
            </Dialog>

            <CardCountBadge :count="item.count" :size="'large'" />
          </div>
        </div>
      </template>

      <template v-for="(item, index) in uniqueYellCards" :key="`yell-${index}`">
        <div class="flex flex-col gap-2">
          <Badge class="px-1 text-md w-full">
            {{ $t("Yell Deck") }}
          </Badge>

          <div class="relative flex">
            <Dialog>
              <DialogTrigger class="w-full">
                <Image
                  class="flex-[0_0_400px] aspect-400/559"
                  :src="getImagePath(item.card.id, yellCards)"
                  :img-attributes="{ class: '' }"
                />
              </DialogTrigger>

              <CardItemDialogContent :item="item.card" />
            </Dialog>

            <CardCountBadge :count="item.count" :size="'large'" />
          </div>
        </div>
      </template>
    </div>
    <div
      class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-12 gap-2"
    >
      <template v-for="(item, index) in uniqueMainCards" :key="`main-${index}`">
        <div class="flex flex-col gap-2">
          <Badge class="px-1 text-md w-full">
            {{ $t("Main Deck") }}
          </Badge>

          <div class="relative flex">
            <Dialog>
              <DialogTrigger class="w-full">
                <Image
                  class="flex-[0_0_400px] aspect-400/559"
                  :src="getImagePath(item.card.id, mainCards)"
                  :img-attributes="{ class: '' }"
                />
              </DialogTrigger>

              <CardItemDialogContent :item="item.card" />
            </Dialog>

            <CardCountBadge :count="item.count" :size="'large'" />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
