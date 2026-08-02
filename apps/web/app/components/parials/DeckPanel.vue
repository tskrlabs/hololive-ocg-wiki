<script setup lang="ts">
/**
 * The deck's contents — header, three sections, card lists (ADR 0009 D18).
 *
 * **This is the surface, not the container.** Above `xl` it is rendered as a plain flex
 * sibling of the grid, so it pushes rather than covers; below, it is wrapped in a `Sheet`
 * and is modal. Both are in `pages/index.vue`. That is D15's "one `CardDetail`, two
 * containers" applied a second time, and for the same reason: the two containers differ
 * in *how they are presented*, not in what they present, and a single component that
 * tried to be both ends up carrying a portal it does not always want.
 *
 * It was `DeckDrawer`, which was a `Sheet` at every breakpoint. That is why the original
 * D18 did not deliver what it described: `SheetContent` mounts a `bg-black/80` overlay
 * and reka-ui's focus-trapping `DialogContent`, so the "overlay beside a still-visible
 * grid" was in fact a modal over a blacked-out one. The panel can only sit beside the
 * grid by not being a dialog at all — hence the split.
 *
 * The title is a heading rather than a `SheetTitle` for the same reason: `SheetTitle`
 * registers with a dialog context that does not exist in the pushed container.
 */
import { X } from "lucide-vue-next";
import { sectionByKey } from "~/composables/deckSections";

const decks = useDecks();
const panel = useDeckPanel();

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
  <!--
    `min-h-0` on the column and on the scroll region, as everywhere under the flex-column
    shell (#44): a flex child's default `min-height: auto` refuses to shrink below its
    content, so without it the sections push past the bottom instead of scrolling.
  -->
  <div class="flex min-h-0 w-full flex-col">
    <div class="shrink-0 border-b p-4">
      <h2 class="text-base font-medium">
        {{ currentDeck?.name || $t("Select one deck to edit") }}
      </h2>
      <p v-if="currentDeck?.author" class="text-sm text-muted-foreground">
        {{ `${$t("Author")}: ${currentDeck.author}` }}
      </p>
      <!--
        A panel with no deck is reachable — the footer button opens it before one is
        chosen — so it says so rather than rendering three empty sections.
      -->
      <p v-else-if="!currentDeck" class="text-sm text-muted-foreground">
        {{ $t("deck.panel.empty") }}
      </p>
    </div>

    <div v-if="currentDeck" class="flex min-h-0 grow flex-col gap-4 overflow-y-auto p-4">
      <section
        v-for="section in sections"
        :key="section.key"
        class="flex flex-col gap-3 rounded-lg border p-3"
      >
        <h3 class="flex items-center gap-2 text-sm font-medium">
          {{ $t(section.label) }}
          <DeckSectionBadge :deck="currentDeck" :section="sectionByKey(section.key)" />
        </h3>

        <DeckPanelCardList :card-ids="section.ids" />
      </section>
    </div>

    <!--
      With no deck there is no scroll region, so nothing claims the space between the
      header and the Close button and both collapse to the top of the sheet. This holds
      the button at the bottom, where it is in the other state — a control that moves
      depending on whether a deck happens to be selected is a control you have to look
      for twice.
    -->
    <div v-else class="grow"></div>

    <!--
      A real Close button, on the sheet only.

      `SheetContent`'s built-in close is a bare 16px `X` in the top-right corner — under
      WCAG 2.5.8's 24px minimum, well under a 44px comfortable touch target, and in the
      hardest corner of a phone to reach one-handed. It stays (it is what Escape and the
      overlay tap are visually anchored to), but it stops being the only way out.

      Full-width and pinned below the scroll region, so it is reachable without scrolling
      past 71 cards to find it — the same reasoning as the filter rail's pinned Apply
      footer (D10, #36 §5).

      **Sheet only.** When the panel is pushed there is nothing to close *out of* — the
      grid is right there beside it — and the footer's Deck button is the toggle. A Close
      button in a column that occludes nothing would be a control for a problem that
      does not exist at that width.
    -->
    <div v-if="!panel.isPushed.value" class="shrink-0 border-t p-4">
      <Button variant="outline" class="h-11 w-full" @click="panel.setOpen(false)">
        <X aria-hidden="true" />
        {{ $t("deck.panel.close") }}
      </Button>
    </div>
  </div>
</template>
