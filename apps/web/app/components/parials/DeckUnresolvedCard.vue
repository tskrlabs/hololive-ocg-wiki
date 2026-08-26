<script setup lang="ts">
/**
 * A deck slot that names no card (ADR 0014).
 *
 * Two ways to arrive here: the migration could not translate a legacy id (a hand-edited
 * `localStorage`, or a code from some other tool), or the `image_key` resolves to nothing
 * because the official list withdrew that card after the deck was saved.
 *
 * **It occupies the slot rather than vanishing.** Dropping it would make a missing card in
 * a 50-card deck invisible, and the user is the only one who knows what was meant. The
 * reference is shown verbatim so they have something to search on, and the button hands
 * them to the card list to pick a replacement.
 */
import type { UnresolvedDeckCard } from "~/composables/useDeckCards";

defineProps<{ item: UnresolvedDeckCard }>();

const localePath = useLocalePath();
</script>

<template>
  <div
    class="relative flex aspect-400/559 flex-col items-center justify-center gap-2 rounded-sm border border-dashed border-muted-foreground/40 bg-muted/30 p-2 text-center"
  >
    <Icon name="lucide:help-circle" class="size-6 text-muted-foreground" />

    <p class="text-xs font-medium text-muted-foreground">
      {{ $t("deck.migration.unresolvedTitle") }}
    </p>

    <p class="text-[10px] leading-tight text-muted-foreground/80">
      {{ $t("deck.migration.unresolvedDetail", { id: item.originalId }) }}
    </p>

    <span v-if="item.count > 1" class="text-[10px] text-muted-foreground/80">
      ×{{ item.count }}
    </span>

    <NuxtLink
      :to="localePath('/')"
      class="rounded-sm bg-secondary px-2 py-1 text-[10px] hover:bg-secondary/80"
    >
      {{ $t("deck.migration.unresolvedReplace") }}
    </NuxtLink>
  </div>
</template>
