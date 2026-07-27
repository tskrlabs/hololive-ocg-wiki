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

  <!-- Card List -->
  <div class="grow">
    <CardListViewAPI />
  </div>

  <FloatingDeck />

  <AppFooter>
    <AppFooterCurrentDeck />
    <div class="ml-auto flex items-center gap-2">
      <AppFooterOptionsButton />
      <AppFooterDeckButton />
    </div>
  </AppFooter>
</template>
