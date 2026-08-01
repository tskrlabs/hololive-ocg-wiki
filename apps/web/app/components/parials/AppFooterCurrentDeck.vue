<script setup lang="ts">
/**
 * Which deck is being edited, and the toggle for whether it is (ADR 0009 D4, D18).
 *
 * **The Edit toggle is breakpoint-dependent, by decision.** Above `xl` the deck panel is
 * pushed beside the grid and implies editing — opening it is the statement — so this
 * reports state rather than being the way to change it. Below `xl` the panel is a modal
 * sheet that occludes the grid, so the two decouple and this stays the control.
 * `useDeckPanel` owns that rule; this renders it.
 */
const route = useRoute();
const getRouteBaseName = useRouteBaseName();

const decks = useDecks();
const { requireDeck } = useDeckGuard();

const isEditing = computed(() => decks.isEditing.value);
const currentDeck = computed(() => decks.currentDeck.value);

const toggleEditing = () => {
  if (!requireDeck()) return;
  decks.toggleEditing();
};
</script>

<template>
  <div
    v-if="getRouteBaseName(route) === 'index'"
    class="flex items-center gap-2 md:gap-4"
  >
    <!--
      State by weight and fill, never by hue (D4).

      This was `bg-emerald-500` against `bg-gray-500` with an `animate-ping` dot — three
      hardcoded colours signalling a state the palette deliberately has no accent hue for,
      plus a pulsing dot that `prefers-reduced-motion` had no say over. Editing now reads
      as a filled badge against an outlined one, which survives both constraints.
    -->
    <button type="button" @click="toggleEditing">
      <Badge
        :variant="isEditing ? 'default' : 'outline'"
        class="text-xs md:text-sm"
        :class="isEditing ? 'font-semibold' : 'text-muted-foreground'"
      >
        {{ isEditing ? $t("deck.editing.on") : $t("deck.editing.off") }}
      </Badge>
      <span class="sr-only">{{ $t("deck.editing.toggle") }}</span>
    </button>

    <span class="text-sm md:text-lg">
      {{ currentDeck?.name || $t("Select one deck to edit") }}
    </span>
  </div>
</template>
