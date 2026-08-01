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
    <!--
      Fill and weight, not hue (D4). This was emerald against gray — two hardcoded
      colours for a state the palette has no accent hue for, and a distinction invisible
      to a red-green colour-blind reader since the two badges also read as similar
      lightness.
    -->
    <Badge
      :variant="isImported ? 'default' : 'outline'"
      class="text-xs md:text-sm"
      :class="isImported ? 'font-semibold' : 'text-muted-foreground'"
    >
      {{
        isImported
          ? $t("Saved In Local Storage")
          : $t("Can Import/Update This Deck")
      }}
    </Badge>
  </div>
</template>
