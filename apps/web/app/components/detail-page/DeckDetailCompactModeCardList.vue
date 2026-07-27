<script setup lang="ts">
const props = defineProps<{
  oshiCardIds: string[];
  mainCardIds: string[];
  yellCardIds: string[];
}>();

// One composable per section (Candidate 04). v1 built a `uniqueCards` factory returning a
// closure over a Map, called it three times, and ran three parallel fetch branches inside
// a single watcher — all to do what `useDeckCards` does once.
const oshi = useDeckCards(() => props.oshiCardIds);
const main = useDeckCards(() => props.mainCardIds);
const yell = useDeckCards(() => props.yellCardIds);

const isLoading = computed(
  () => oshi.isLoading.value || main.isLoading.value || yell.isLoading.value,
);

const cardImage = useCardImage();
</script>

<template>
  <div v-if="isLoading" class="p-4 flex justify-center items-center">
    <div
      class="animate-spin h-6 w-6 border-2 border-primary rounded-full border-t-transparent"
    ></div>
  </div>

  <div
    v-else-if="
      oshi.deckCards.value.length === 0 &&
      yell.deckCards.value.length === 0 &&
      main.deckCards.value.length === 0
    "
    class="p-4 text-center text-sm text-gray-500"
  >
    {{ $t("No cards to display") }}
  </div>

  <div v-else>
    <div
      class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-12 gap-2"
    >
      <template v-for="{ card, count } in oshi.deckCards.value" :key="`oshi-${card.id}`">
        <div class="flex flex-col gap-2">
          <Badge class="px-1 text-md w-full">
            {{ $t("Oshi") }}
          </Badge>

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
        </div>
      </template>

      <template v-for="{ card, count } in yell.deckCards.value" :key="`yell-${card.id}`">
        <div class="flex flex-col gap-2">
          <Badge class="px-1 text-md w-full">
            {{ $t("Yell Deck") }}
          </Badge>

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
        </div>
      </template>
    </div>
    <div
      class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-12 gap-2"
    >
      <template v-for="{ card, count } in main.deckCards.value" :key="`main-${card.id}`">
        <div class="flex flex-col gap-2">
          <Badge class="px-1 text-md w-full">
            {{ $t("Main Deck") }}
          </Badge>

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
        </div>
      </template>
    </div>
  </div>
</template>
