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
    <!--
      Both are `lg:hidden`, because both move into the rail above that width (#36 §4).
      The filter trigger has no panel to open once the rail is permanent, and search
      belongs with the other query controls rather than in a header that was already
      eight icon buttons wide.
    -->
    <FilterAPI />

    <div class="grow lg:hidden">
      <SearchInputAPI />
    </div>
  </AppHeader>

  <!--
    Two columns from `lg`: the rail, then the grid (D10, #36).

    `min-h-0` on this row is load-bearing, as everywhere under the flex-column shell — a
    flex child defaults to `min-height: auto` and refuses to shrink below its content, so
    without it the region would grow to fit 2,448 cards and push the footer off-screen
    (#44).
  -->
  <div class="flex min-h-0 grow">
    <FilterRail />

    <!--
      The card list takes whatever the rail and the chrome leave. The scroller itself does
      the scrolling — this is `overflow-hidden` so nothing can scroll twice. See #44.
    -->
    <main class="relative min-w-0 grow min-h-0 overflow-hidden">
      <CardListViewAPI />
    </main>
  </div>

  <!--
    The deck is a right-anchored overlay drawer (D18), no longer a panel anchored inside
    the grid region. `FloatingDeck` had to live inside `<main>` to avoid overlapping the
    filter rail; an overlay has no such constraint, so it sits at page level with the
    other chrome.
  -->
  <DeckDrawer />

  <AppFooter>
    <AppFooterCurrentDeck />
    <div class="ml-auto flex items-center gap-2">
      <AppFooterOptionsButton />
      <AppFooterDeckDrawerButton />
      <AppFooterDeckButton />
    </div>
  </AppFooter>
</template>
