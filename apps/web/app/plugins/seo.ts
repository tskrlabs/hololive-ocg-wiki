/**
 * Hand-written JSON-LD and social meta.
 *
 * `nuxt-schema-org` would generate most of this, but v1 wrote it by hand and D13 fences
 * Phase 5 to refactors — so it is ported as-is, with the URLs read from config instead of
 * hardcoded. v1 spelled `hololive-ocg-wiki.lichingchester.dev` into four places here.
 */
export default defineNuxtPlugin(() => {
  const { siteUrl } = useRuntimeConfig().public;

  // Add structured data for the website
  useHead({
    script: [
      {
        type: "application/ld+json",
        innerHTML: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebSite",
          name: "Hololive OCG Wiki",
          description:
            "A fan-made wiki for Hololive OCG, featuring card information, deck builder, and more.",
          url: siteUrl,
          author: {
            "@type": "Organization",
            name: "Hololive OCG Wiki Contributors",
          },
          genre: "Gaming",
          keywords:
            "Hololive, OCG, Official Card Game, trading cards, card database, deck builder, VTuber, virtual YouTuber, card search, game wiki",
          inLanguage: ["zh-TW", "ja", "en", "id", "ko", "th"],
          potentialAction: {
            "@type": "SearchAction",
            target: {
              "@type": "EntryPoint",
              urlTemplate:
                `${siteUrl}/?q={search_term_string}`,
            },
            "query-input": "required name=search_term_string",
          },
        }),
      },
    ],
  });

  // Add WebApplication structured data
  useHead({
    script: [
      {
        type: "application/ld+json",
        innerHTML: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebApplication",
          name: "Hololive OCG Wiki",
          description:
            "A fan-made wiki for Hololive OCG, featuring card information, deck builder, and more.",
          url: siteUrl,
          applicationCategory: "GameApplication",
          operatingSystem: "Web Browser",
          genre: "Card Game Database",
          offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "USD",
          },
          featureList: [
            "Card database search",
            "Deck builder",
            "Card information",
            "Multi-language support",
            "Deck sharing",
          ],
        }),
      },
    ],
  });

  // Global meta tags that should be available on all pages
  useHead({
    meta: [
      { name: "generator", content: "Nuxt.js" },
      { name: "language", content: "multiple" },
      { name: "distribution", content: "global" },
      { name: "rating", content: "general" },
      { name: "coverage", content: "worldwide" },
      { name: "target", content: "all" },
      { name: "audience", content: "all" },
      { name: "HandheldFriendly", content: "true" },
      { name: "MobileOptimized", content: "320" },
      { name: "apple-mobile-web-app-title", content: "Hololive OCG Wiki" },
      { name: "application-name", content: "Hololive OCG Wiki" },
      // { name: "msapplication-TileColor", content: "#6366f1" },
      // { name: "theme-color", content: "#6366f1" },
      // Prevent unwanted social media crawling issues
      { property: "og:locale", content: "zh_TW" },
      { property: "og:locale:alternate", content: "en_US" },
      { property: "og:locale:alternate", content: "ja_JP" },
      { property: "og:locale:alternate", content: "id_ID" },
      { property: "og:locale:alternate", content: "ko_KR" },
      { property: "og:locale:alternate", content: "th_TH" },
    ],
    link: [
      // No canonical here. v1 set a *static* one pointing at the site root from every
      // page, alongside a route-aware one in app.vue — the two disagreed on every page
      // but the home page. app.vue owns it now.
      //
      // The raw.githubusercontent.com prefetch is also gone: it existed for v1's
      // info.json fetch, which D11 replaced with /api/info from R2.
      { rel: "dns-prefetch", href: "//fonts.googleapis.com" },
      { rel: "dns-prefetch", href: "//www.google-analytics.com" },
    ],
  });
});
