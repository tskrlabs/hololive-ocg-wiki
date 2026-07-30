<script setup lang="ts">
const { t, locale } = useI18n();
const { siteUrl } = useRuntimeConfig().public;

// SEO Meta tags for the main page
useSeoMeta({
  title: t("Card List"),
  description: t("nuxtSiteConfig.description"),
  author: "Hololive OCG Wiki Contributors",
  ogTitle: t("Card List"),
  ogDescription: t("nuxtSiteConfig.description"),
  ogType: "website",
  ogUrl: siteUrl,
  ogImage: `${siteUrl}/icon.png`,
  ogSiteName: t("Card List"),
  twitterCard: "summary_large_image",
  twitterTitle: t("Card List"),
  twitterDescription: t("nuxtSiteConfig.description"),
  twitterImage: `${siteUrl}/icon.png`,
});

useHead({
  // The body must not scroll: the shell is exactly one viewport tall and the card
  // scroller does the scrolling inside it (#44). Without this, iOS Safari still
  // rubber-bands the whole document over a page that has nowhere to go.
  bodyAttrs: {
    class: "overflow-hidden",
  },
  htmlAttrs: {
    lang: locale.value,
  },
});
</script>

<template>
  <AppHeader>
    <!-- filter -->
    <FilterAPI />

    <!-- search -->
    <SearchInputAPI />
  </AppHeader>

  <!--
    The card list takes whatever the chrome leaves. `min-h-0` is load-bearing: a flex
    child defaults to `min-height: auto` and refuses to shrink below its content, so
    without it this region would grow to fit 2,448 cards and push the footer off-screen.

    The scroller itself does the scrolling — this is `overflow-hidden` so nothing can
    scroll twice. See #44.
  -->
  <main class="relative grow min-h-0 overflow-hidden">
    <CardListViewAPI />

    <!--
      Inside the list region, not a sibling of the footer (#44). It anchors to the bottom
      of this region, so "just above the footer" is a position rather than an arithmetic
      guess about how tall the footer is. It stays bottom-*left*; the results summary is
      right-aligned, which is what keeps the two from colliding.
    -->
    <FloatingDeck />
  </main>

  <AppFooter>
    <AppFooterCurrentDeck />
    <div class="ml-auto flex items-center gap-2">
      <AppFooterOptionsButton />
      <AppFooterDeckButton />
    </div>
  </AppFooter>
</template>
