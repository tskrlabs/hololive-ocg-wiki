<script setup lang="ts">
/**
 * ⚠️ PROTOTYPE — throwaway. The decision it answered is recorded on
 * https://github.com/tskrlabs/hololive-ocg-wiki/issues/35 and in `NOTES.md`.
 *
 * **Chosen: variant D** — B "Console" structure and typography with C "Gallery"'s
 * ink-only neutral palette. The losing variants (A/B/C/E) and the switcher are deleted;
 * what remains is the winner, kept runnable so the build session has a visual target.
 *
 * Delete this route and `components/prototype/` once the identity lands in
 * `assets/css/tailwind.css` for real.
 */
import type { Card, Locales } from "@/types/card";

definePageMeta({ layout: false });


const { locale } = useI18n();
const cardQuery = useCardQuery();

const cards = ref<Card[]>([]);
const total = ref(0);

onMounted(async () => {
  const filter = (await import("~/composables/filter-states")).createEmpty();
  cards.value = await cardQuery.getFilteredCards(filter, locale.value as Locales, 1, 60);
  total.value = cardQuery.total.value;
});

useHead({ title: "PROTOTYPE — visual identity (D)" });
</script>

<template>
  <div>
    <VariantTokens />
    <VariantShell variant="B" :cards="cards" :total="total" />
  </div>
</template>
