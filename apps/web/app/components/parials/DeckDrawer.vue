<script setup lang="ts">
/**
 * The deck, as a right-anchored overlay drawer (ADR 0009 D18).
 *
 * Replaces `FloatingDeck`, which was a card anchored to the bottom-left of the grid
 * region with its own Expand/Collapse button — so the deck was either a strip too short
 * to show a deck or a panel covering the cards being added to it, and the control for
 * which was a third piece of state beside "is a deck selected" and "is editing".
 *
 * A right-anchored sheet is one surface with one open state. It is an **overlay** rather
 * than a permanent third column because a column costs a full grid column at 1512px
 * (6 → 5), paid even while browsing (D18).
 *
 * Whether opening it also means *editing* is `useDeckDrawer`'s job, not this component's —
 * the rule differs by breakpoint and is stated once there.
 */
import { sectionByKey } from "~/composables/deckSections";

const decks = useDecks();
const drawer = useDeckDrawer();

const currentDeck = computed(() => decks.currentDeck.value);

/**
 * The three sections, in play order.
 *
 * Derived rather than written out three times: `FloatingDeck` repeated the same
 * heading + badge + list block per section, which is how the badge and the list drifted
 * apart in v1 (Candidate 03).
 */
const sections = computed(() => [
  { key: "oshi" as const, label: "Oshi", ids: currentDeck.value?.oshiCardIds ?? [] },
  { key: "main" as const, label: "Main Deck", ids: currentDeck.value?.mainCardIds ?? [] },
  { key: "yell" as const, label: "Yell Deck", ids: currentDeck.value?.yellCardIds ?? [] },
]);
</script>

<template>
  <Sheet :open="drawer.isOpen.value" @update:open="drawer.setOpen">
    <!--
      `side="right"` on every breakpoint. D18 calls for a right-anchored drawer; below
      `lg` it happens to cover the grid, which is exactly why `useDeckDrawer` stops
      coupling it to editing there.
    -->
    <SheetContent
      side="right"
      class="flex w-full flex-col gap-0 p-0 sm:max-w-md lg:max-w-lg"
    >
      <SheetHeader class="border-b p-4">
        <SheetTitle>
          {{ currentDeck?.name || $t("Select one deck to edit") }}
        </SheetTitle>
        <SheetDescription v-if="currentDeck?.author">
          {{ `${$t("Author")}: ${currentDeck.author}` }}
        </SheetDescription>
        <!--
          A drawer with no deck is reachable — the footer button opens it before one is
          chosen — so it says so rather than rendering three empty sections.
        -->
        <SheetDescription v-else-if="!currentDeck">
          {{ $t("deck.drawer.empty") }}
        </SheetDescription>
      </SheetHeader>

      <!--
        `min-h-0` is load-bearing here as everywhere under a flex column (#44): without it
        this region refuses to shrink below its content and the scroll never engages.
      -->
      <div v-if="currentDeck" class="flex min-h-0 grow flex-col gap-4 overflow-y-auto p-4">
        <section
          v-for="section in sections"
          :key="section.key"
          class="flex flex-col gap-3 rounded-lg border p-3"
        >
          <h2 class="flex items-center gap-2 text-sm font-medium">
            {{ $t(section.label) }}
            <DeckSectionBadge :deck="currentDeck" :section="sectionByKey(section.key)" />
          </h2>

          <DeckDrawerCardList :card-ids="section.ids" />
        </section>
      </div>
    </SheetContent>
  </Sheet>
</template>
