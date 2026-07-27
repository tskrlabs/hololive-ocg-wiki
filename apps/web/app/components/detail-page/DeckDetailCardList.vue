<script setup lang="ts">
import type { Card } from "~/types/card";

const props = defineProps<{
  cardIds: string[];
  isCompactMode: Boolean;
}>();

const cardQuery = useCardQuery();
const isLoading = ref(true);
const cards = ref<Card[]>([]);
const { locale } = useI18n();

const uniqueCardIds = computed(() => {
  const cardCounts = props.cardIds.reduce((acc, cardId) => {
    acc[cardId] = (acc[cardId] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // `cardCounts[id]` is `number | undefined` to the compiler; the key came from
  // `Object.keys` of the same object. Candidate 04's `useDeckCards` replaces this
  // whole derivation — see composables/useDeckCards.ts.
  return Object.keys(cardCounts).map((id) => ({ id, count: cardCounts[id]! }));
});

// Group cards by ID and count occurrences
const uniqueCards = computed(() => {
  if (!cards.value.length) return [];

  // Create a result array with card data and counts
  return uniqueCardIds.value
    .map((item) => {
      const card = cards.value.find((c) => c.id === item.id);
      if (!card) return null;
      return {
        cardId: card.id,
        count: item.count,
        card,
      };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);
});

watch(
  () => props.cardIds,
  async (newCardIds) => {
    isLoading.value = true;
    if (newCardIds.length === 0) {
      cards.value = [];
      isLoading.value = false;
      return;
    }

    // Fetch cards by IDs using the new batch method with locale
    const fetchedCards =
      (await cardQuery.getCardsByIds(
        uniqueCardIds.value.map((item) => item.id),
        locale.value
      )) || [];
    cards.value = fetchedCards;
    isLoading.value = false;
  },
  { immediate: true, deep: true }
);

// Resolve a card's art URL by id (D9: the key is stored, the URL is composed).
// v1 repeated this helper verbatim in three components and read a baked-in
// `image_path`; Candidate 04 merges the surrounding derivation.
const cardImage = useCardImage();
const getImagePath = (cardId: string) =>
  cardImage(cards.value.find((c) => c.id === cardId)?.image_key);
</script>

<template>
  <div v-if="isLoading" class="p-4 flex justify-center items-center">
    <div
      class="animate-spin h-6 w-6 border-2 border-primary rounded-full border-t-transparent"
    ></div>
  </div>

  <div
    v-else-if="uniqueCards.length === 0"
    class="p-4 text-center text-sm text-gray-500"
  >
    {{ $t("No cards to display") }}
  </div>

  <div
    v-else
    class="grid"
    :class="
      isCompactMode
        ? 'grid-cols-6 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 xl:grid-cols-12 2xl:grid-cols-14 gap-1 md:gap-2'
        : 'grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-1 md:gap-3'
    "
  >
    <template v-for="(item, index) in uniqueCards" :key="index">
      <div class="relative flex">
        <Dialog>
          <DialogTrigger class="w-full">
            <Image
              class="flex-[0_0_400px] aspect-400/559"
              :src="getImagePath(item.card.id)"
              :img-attributes="{ class: '' }"
            />
          </DialogTrigger>

          <CardItemDialogContent :item="item.card" />
        </Dialog>

        <CardCountBadge :count="item.count" :size="'large'" />
      </div>
    </template>
  </div>
</template>
