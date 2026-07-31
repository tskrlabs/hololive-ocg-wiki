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

      <!--
        Inside the list region, not a sibling of the footer (#44). It anchors to the
        bottom of this region, so "just above the footer" is a position rather than an
        arithmetic guess about how tall the footer is.

        Being inside `<main>` is also what keeps it off the rail (#36 §6): it was `fixed`
        to the viewport's bottom-left, which above `lg` is exactly where the rail now is.
        Anchoring to the grid column instead makes that overlap impossible rather than
        merely unlikely.
      -->
      <FloatingDeck />
    </main>
  </div>

  <AppFooter>
    <AppFooterCurrentDeck />
    <div class="ml-auto flex items-center gap-2">
      <AppFooterOptionsButton />
      <AppFooterDeckButton />
    </div>
  </AppFooter>
</template>
