<script setup lang="ts">
/*
 * The Toaster mount, held back during the Phase 5 scaffold and **never restored** — the
 * TODO outlived the commit it named (#49).
 *
 * `components/ui/sonner/Sonner.vue` was ported in commit 3 as planned, but nothing
 * rendered it, so every `toast.*` call in the app has been a no-op since: the deck-code
 * copy confirmation, "Please select a deck to continue", "Deck detail page not found",
 * "Deck deleted successfully". Ten call sites across three components, all silent, and
 * nothing failed — a toast that goes nowhere throws no error.
 *
 * Verified in Chromium before fixing: no `[data-sonner-toaster]` in the DOM at all.
 */
import { Toaster } from "@/components/ui/sonner";
import "vue-sonner/style.css"; // vue-sonner v2 requires this import

const { locale } = useI18n();
const route = useRoute();
const { siteUrl } = useRuntimeConfig().public;

useHead({
  htmlAttrs: { lang: locale },
  link: [
    // The canonical origin comes from config, not a literal. v1 hardcoded
    // `hololive-ocg-wiki.lichingchester.dev` here and in four other files, which is why
    // changing domains is a chore at all (nuxt.config.ts, SITE_URL).
    { rel: "canonical", href: () => `${siteUrl}${route.path}` },
  ],
});
</script>

<template>
  <Toaster rich-colors close-button position="top-center" />

  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>

  <!--
    Above `<NuxtPage>` deliberately (D15, #39).

    A tile click pushes the card's URL, which is a real route — so vue-router swaps the
    list component out, and a dialog owned by the list would be unmounted by the very
    navigation meant to open it. Mounted here it survives, and the card page defers to it
    when the same card is already on screen.
  -->
  <CardRouteDialog />
</template>
