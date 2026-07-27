<script setup lang="ts">
import { CircleMinus, CirclePlus, Trash2 } from "lucide-vue-next";
import type { Card, CardTypeCode } from "~/types/card";

const props = defineProps<{
  cardIds: string[];
}>();

// Use the decks store's optimized method to get cards
// const decksStore = useDecks();

const cardStore = useCardStoreAPI();
const isLoading = ref(true);
const cards = ref<Card[]>([]);
const decks = useDecks();
const { locale } = useI18n();

const uniqueCardIds = computed(() => {
  const cardCounts = props.cardIds.reduce((acc, cardId) => {
    acc[cardId] = (acc[cardId] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return Object.keys(cardCounts).map((id) => ({ id, count: cardCounts[id] }));
});

watch(
  () => props.cardIds,
  async (newCardIds) => {
    // console.log("Card IDs changed, fetching cards...");

    isLoading.value = true;
    if (newCardIds.length === 0) {
      cards.value = [];
      isLoading.value = false;
      return;
    }

    // Fetch cards by IDs using the new batch method with locale
    const fetchedCards =
      (await cardStore.getCardsByIds(
        uniqueCardIds.value.map((item) => item.id),
        locale.value
      )) || [];
    cards.value = fetchedCards;
    isLoading.value = false;
  },
  { immediate: true, deep: true }
);

// Optimized action methods with cached context
// Using arrow functions with parameter destructuring for better performance
const add = (cardId: string, cardTypeCode: CardTypeCode) => {
  if (decks.currentDeck.value) {
    decks.addCardToDeck({ cardId, amount: 1, cardTypeCode });
  }
};

const remove = (cardId: string, cardTypeCode: CardTypeCode) => {
  if (decks.currentDeck.value) {
    decks.removeCardFromDeck({ cardId, amount: 1, cardTypeCode });
  }
};

const removeAll = (cardId: string, cardTypeCode: CardTypeCode) => {
  if (decks.currentDeck.value) {
    decks.removeAllCardFromDeck(cardId, cardTypeCode);
  }
};

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
    v-else-if="uniqueCardIds.length === 0"
    class="p-4 text-center text-sm text-gray-500"
  >
    {{ $t("No cards to display") }}
  </div>

  <div v-else class="grid grid-cols-4 md:grid-cols-10 gap-1 md:gap-2">
    <template v-for="item in cards" :key="item.id">
      <div class="relative flex">
        <Dialog>
          <DialogTrigger class="w-full">
            <Image
              class="aspect-400/559"
              :src="getImagePath(item.id)"
              :img-attributes="{ class: '' }"
            />
          </DialogTrigger>

          <CardItemDialogContent v-if="item" :item="item" />
        </Dialog>

        <!-- actions -->
        <div class="absolute bottom-0 left-0 w-full flex gap-1 p-1">
          <button
            class="w-2/4 h-6 md:h-6 bg-secondary/95 rounded-sm"
            @click.prevent="add(item.id, item.card_type_code)"
            aria-label="Add card"
          >
            <div class="flex items-center justify-center text-xs">
              <CirclePlus class="size-3 md:size-4" />
            </div>
          </button>
          <button
            class="w-2/4 h-6 md:h-6 bg-red-500/95 rounded-sm"
            @click.prevent="remove(item.id, item.card_type_code)"
            aria-label="Remove card"
          >
            <div class="flex items-center justify-center text-xs">
              <CircleMinus class="size-3 text-white md:size-4" />
            </div>
          </button>
        </div>

        <div class="absolute top-0 right-0 flex flex-col gap-1 p-1">
          <button
            class="bg-red-500/90 rounded-sm size-7 md:size-8"
            @click.prevent="removeAll(item.id, item.card_type_code)"
            aria-label="Remove all cards"
          >
            <div class="flex items-center justify-center text-xs">
              <Trash2 class="size-3 text-white md:size-4" />
            </div>
          </button>
        </div>

        <CardCountBadge
          :count="
            uniqueCardIds.find((cardIdObj) => cardIdObj.id === item.id)
              ?.count || 0
          "
          :size="'small'"
        />
      </div>
    </template>
    <!-- </TransitionGroup> -->
  </div>
</template>
