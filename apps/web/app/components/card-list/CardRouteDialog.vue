<script setup lang="ts">
/**
 * The card dialog, driven by the URL and mounted above the router (D15, #39).
 *
 * ⚠️ **Why this lives in `app.vue` rather than in the list page.**
 *
 * Clicking a tile pushes `/{locale}/card/{set}/{stem}`, which is a real route — so
 * vue-router swaps the list component for the card page and *unmounts anything the list
 * owned*, including a dialog. Verified before this component existed: the URL changed
 * correctly, back and forward worked, and the dialog never appeared, because the thing
 * rendering it had just been destroyed.
 *
 * Mounted above `<NuxtPage>`, it survives the navigation. The card page then checks
 * `isOverlay` and renders nothing when this dialog is already showing the same card, so
 * the two never both draw it (#39's "a `<NuxtPage>`-level check keeps the list from
 * remounting").
 *
 * The dialog is only an *overlay* when there is something to overlay: a card URL opened
 * cold has no list behind it, so it must render as a page. `enteredFromApp` is what
 * distinguishes them, and it is a fact about this tab's history rather than a guess.
 */
import type { Card, Locales } from "@/types/card";

const { locale } = useI18n();
const cardQuery = useCardQuery();
const { openKey, closeCard, isOverlay, restoreTileFocus } = useCardRoute();

const card = ref<Card | null>(null);

watch(
  [openKey, locale, isOverlay],
  async ([key, currentLocale, overlay]) => {
    if (!key || !overlay) {
      card.value = null;
      return;
    }

    const [set, stem] = key.split("/");
    if (!set || !stem) return;

    // A card already in the grid is cached, so the common path costs no request.
    card.value =
      (await cardQuery.getCardByKey(set, stem, currentLocale as Locales)) ?? null;
  },
  { immediate: true },
);

/** Reka's `Dialog` closes by setting `open` false; that has to become a history pop. */
const onOpenChange = (open: boolean) => {
  if (!open) closeCard();
};

/**
 * Return focus to the originating tile once the dialog is gone (#48 §6).
 *
 * Driven off `card` becoming null rather off `onOpenChange`, because the dialog also
 * closes via browser back — where no open-change handler runs at all. Verified before
 * this: closing a card dialog left focus on `<body>`, so a keyboard user was returned to
 * the top of the document after viewing any card.
 */
watch(card, (now, before) => {
  if (before && !now) restoreTileFocus();
});
</script>

<template>
  <Dialog :open="!!card" @update:open="onOpenChange">
    <CardItemDialogContent v-if="card" :item="card" />
  </Dialog>
</template>
