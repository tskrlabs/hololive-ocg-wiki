<script setup lang="ts">
/**
 * A section's "n/limit" badge (Candidate 03).
 *
 * v1 wrote this out **six times** — three sections × two views — as a nested ternary over
 * raw array lengths with the limit typed inline (`${deck.mainCardIds.length}/50`). The
 * limits had no home, so the deck rules lived in template strings and the store enforced
 * none of them.
 *
 * The state comes from `deckSections.sectionStatus`, so what "complete" means is decided
 * once. This component only maps a state to a colour.
 */
import type { Deck } from "~/types/deck";
import { sectionCount, sectionStatus, type SectionSpec } from "~/composables/deckSections";

const props = defineProps<{ deck: Deck; section: SectionSpec }>();

const STATUS_CLASS = {
  empty:
    "border-gray-400 dark:border-gray-600 bg-gray-400/20 dark:bg-gray-600/20 text-gray-700 dark:text-gray-400",
  partial:
    "border-gray-400 dark:border-gray-600 bg-gray-400/20 dark:bg-gray-600/20 text-gray-700 dark:text-gray-400",
  complete: "bg-emerald-500/15 border-emerald-500/50 text-emerald-500",
  over: "bg-red-500/15 border-red-500/50 text-red-500",
} as const;

const count = computed(() => sectionCount(props.deck, props.section));
const status = computed(() => sectionStatus(props.deck, props.section));
</script>

<template>
  <Badge
    class="px-1 text-[8px] md:text-xs"
    :class="STATUS_CLASS[status]"
    variant="outline"
    size="sm"
  >
    {{ `${count}/${section.limit}` }}
  </Badge>
</template>
