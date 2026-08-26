<script setup lang="ts">
const props = defineProps<{
  cardIds: string[];
  isCompactMode: Boolean;
}>();

// The count → dedupe → fetch → join pipeline, once (Candidate 04). This component and
// FloatingDeckCardList had it verbatim; the compact list had a Map variant of the same
// thing applied three times.
const { deckCards, unresolvedCards, isLoading } = useDeckCards(() => props.cardIds);
const cardImage = useCardImage();
</script>

<template>
  <div v-if="isLoading" class="p-4 flex justify-center items-center">
    <div
      class="animate-spin h-6 w-6 border-2 border-primary rounded-full border-t-transparent"
    ></div>
  </div>

  <!--
    `unresolvedCards` counts toward emptiness: a deck whose every card failed to resolve
    is not empty, and "no cards" would hide exactly what the user needs to see (ADR 0014).
  -->
  <div
    v-else-if="deckCards.length === 0 && unresolvedCards.length === 0"
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
    <template v-for="{ card, count } in deckCards" :key="card.id">
      <div class="relative flex">
        <Dialog>
          <DialogTrigger class="w-full">
            <Image
              class="flex-[0_0_400px] aspect-400/559"
              :src="cardImage(card.image_key)"
              :img-attributes="{ class: '' }"
            />
          </DialogTrigger>

          <CardItemDialogContent :item="card" />
        </Dialog>

        <CardCountBadge :count="count" :size="'large'" />
      </div>
    </template>

    <!--
      Slots we cannot name, after the real cards. The full deck view is where a missing
      card is most noticeable, so it must not be the one view that hides them.
    -->
    <DeckUnresolvedCard
      v-for="item in unresolvedCards"
      :key="item.ref"
      :item="item"
    />
  </div>
</template>
