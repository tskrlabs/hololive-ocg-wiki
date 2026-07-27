<script setup lang="ts">
import type { Deck } from "~/types/deck";

const route = useRoute();

const decks = useDecks();
const deck = ref<Deck | null>(null);

onMounted(() => {
  if (route.params.code) {
    const code = route.params.code as string;
    const checked = decks.checkForDeckCode(code);

    if (checked) {
      deck.value = checked;
    }
  }
});

const isImported = computed(() => {
  return decks.decks.value.some((_deck) => {
    if (deck.value) {
      return _deck.id === deck.value.id;
    } else {
      return false;
    }
  });
});
</script>

<template>
  <div class="flex items-center gap-2 md:gap-4">
    <Badge
      variant="outline"
      class="text-xs md:text-sm"
      :class="
        isImported
          ? 'bg-emerald-500/15 border-emerald-500'
          : 'bg-gray-500/15 border-gray-500'
      "
    >
      {{
        isImported
          ? $t("Saved In Local Storage")
          : $t("Can Import/Update This Deck")
      }}
    </Badge>
  </div>
</template>
