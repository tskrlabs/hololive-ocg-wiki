<script setup lang="ts">
const cardImage = useCardImage();
import { CircleMinus, CirclePlus } from "lucide-vue-next";
import type { Card } from "@/types/card";

const props = defineProps<{
  item: Card;
}>();

const decks = useDecks();
const isEditing = computed(() => decks.isEditing.value);

const add = (amount: number = 1) => {
  if (!isEditing.value) return;
  decks.addCardToDeck({
    cardId: props.item.id,
    amount,
    cardTypeCode: props.item.card_type_code,
  });
};

const remove = (amount: number = 1) => {
  if (!isEditing.value) return;
  decks.removeCardFromDeck({
    cardId: props.item.id,
    amount,
    cardTypeCode: props.item.card_type_code,
  });
};

const count = computed(() => {
  return decks.getCardCount(props.item.id, props.item.card_type_code);
});
</script>

<template>
  <div class="relative flex aspect-400/559">
    <Dialog>
      <DialogTrigger class="w-full">
        <SimpleImage
          class="rounded-lg overflow-hidden"
          :src="cardImage(item.image_key)"
          :img-attributes="{ class: 'w-full' }"
        />
      </DialogTrigger>

      <CardItemDialogContent :item="item" />
    </Dialog>

    <div
      v-if="isEditing"
      class="absolute bottom-0 left-0 flex gap-1 p-1 w-full"
    >
      <button
        class="bg-secondary/90 rounded-sm md:py-0.5 grow"
        @click="add(10)"
      >
        <div class="flex items-center gap-1 justify-center text-xs md:text-sm">
          <CirclePlus class="w-3 md:w-4" />
          10
        </div>
      </button>
      <button class="bg-secondary/90 rounded-sm md:py-0.5 grow" @click="add(4)">
        <div class="flex items-center gap-1 justify-center text-xs md:text-sm">
          <CirclePlus class="w-3 md:w-4" />
          4
        </div>
      </button>
      <button class="bg-secondary/90 rounded-sm md:py-0.5 grow" @click="add(1)">
        <div class="flex items-center gap-1 justify-center text-xs md:text-sm">
          <CirclePlus class="w-3 md:w-4" />
          1
        </div>
      </button>
    </div>

    <div
      v-if="isEditing"
      class="absolute top-0 right-0 flex flex-col gap-1 p-1"
    >
      <button
        v-if="isEditing && count > 0"
        class="bg-red-500/90 rounded-sm size-7 md:size-8"
        @click="remove(1)"
      >
        <div class="flex items-center justify-center text-xs">
          <CircleMinus class="w-3 md:w-4 text-white" />
        </div>
      </button>
    </div>

    <CardCountBadge
      v-if="isEditing && count > 0"
      :count="count || 0"
      :size="'normal'"
    />
  </div>
</template>
