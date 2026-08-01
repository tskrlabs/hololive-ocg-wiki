<script setup lang="ts">
/**
 * Opens the deck panel (ADR 0009 D18).
 *
 * This is the control `FloatingDeck`'s Expand/Collapse button used to be, moved into the
 * footer beside the other deck controls. The old one lived *inside* the floating panel,
 * so the panel had to be on screen to collapse it — and the only way to get it there was
 * to select a deck, which also silently turned editing on.
 *
 * It stays enabled with no deck selected: opening the panel is how you find out the deck
 * is empty, and the panel says so. The five "Please select a deck to continue." guards
 * exist because *actions* need a deck (#57); looking does not.
 *
 * `aria-expanded` rather than only an `sr-only` label: above `xl` the panel is a plain
 * region rather than a dialog, so nothing else tells a screen reader that this button
 * controls a disclosure or what state it is in.
 */
import { PanelRight } from "lucide-vue-next";

const decks = useDecks();
const panel = useDeckPanel();

/** How many cards are in the deck — the panel's own summary, so it need not be opened. */
const cardCount = computed(() => {
  const deck = decks.currentDeck.value;
  if (!deck) return 0;
  return deck.oshiCardIds.length + deck.mainCardIds.length + deck.yellCardIds.length;
});
</script>

<template>
  <Button
    variant="outline"
    :aria-expanded="panel.isOpen.value"
    aria-controls="deck-panel"
    @click="panel.toggle()"
  >
    <PanelRight aria-hidden="true" />
    <span class="hidden md:inline-flex">{{ $t("Deck") }}</span>
    <!--
      The count is the only state this button carries, and it is a number rather than a
      dot — D4 leaves no accent hue to signal "has contents", and a count says more than
      a marker would anyway.
    -->
    <Badge v-if="cardCount > 0" variant="outline" class="tabular-nums">
      {{ cardCount }}
    </Badge>
    <span class="sr-only">
      {{ panel.isOpen.value ? $t("deck.panel.close") : $t("deck.panel.open") }}
    </span>
  </Button>
</template>
