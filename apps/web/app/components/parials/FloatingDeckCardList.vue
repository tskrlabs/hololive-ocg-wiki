<script setup lang="ts">
import { CircleMinus, CirclePlus, Trash2 } from "lucide-vue-next";
import type { Card, CardTypeCode } from "~/types/card";

const props = defineProps<{
  cardIds: string[];
}>();

// The count → dedupe → fetch → join pipeline, once (Candidate 04). v1 had it written
// out verbatim here and in DeckDetailCardList, plus a hand-rolled Map variant in the
// compact list — six copies of one derivation across three files.
const { deckCards, isLoading } = useDeckCards(() => props.cardIds);

const decks = useDecks();
const cardImage = useCardImage();

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

</script>

<template>
  <div v-if="isLoading" class="p-4 flex justify-center items-center">
    <div
      class="animate-spin h-6 w-6 border-2 border-primary rounded-full border-t-transparent"
    ></div>
  </div>

  <div
    v-else-if="deckCards.length === 0"
    class="p-4 text-center text-sm text-gray-500"
  >
    {{ $t("No cards to display") }}
  </div>

  <div v-else class="grid grid-cols-4 md:grid-cols-10 gap-1 md:gap-2">
    <template v-for="{ card, count } in deckCards" :key="card.id">
      <div class="relative flex">
        <Dialog>
          <DialogTrigger class="w-full">
            <Image
              class="aspect-400/559"
              :src="cardImage(card.image_key)"
              :img-attributes="{ class: '' }"
            />
          </DialogTrigger>

          <CardItemDialogContent :item="card" />
        </Dialog>

        <!-- actions -->
        <div class="absolute bottom-0 left-0 w-full flex gap-1 p-1">
          <button
            class="w-2/4 h-6 md:h-6 bg-secondary/95 rounded-sm"
            @click.prevent="add(card.id, card.card_type_code)"
            aria-label="Add card"
          >
            <div class="flex items-center justify-center text-xs">
              <CirclePlus class="size-3 md:size-4" />
            </div>
          </button>
          <button
            class="w-2/4 h-6 md:h-6 bg-red-500/95 rounded-sm"
            @click.prevent="remove(card.id, card.card_type_code)"
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
            @click.prevent="removeAll(card.id, card.card_type_code)"
            aria-label="Remove all cards"
          >
            <div class="flex items-center justify-center text-xs">
              <Trash2 class="size-3 text-white md:size-4" />
            </div>
          </button>
        </div>

        <!-- The count comes with the card now; v1 looked it back up by id. -->
        <CardCountBadge :count="count" :size="'small'" />
      </div>
    </template>
    <!-- </TransitionGroup> -->
  </div>
</template>
