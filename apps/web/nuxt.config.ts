/**
 * The site (D2, D13, ADR 0006).
 *
 * **Static, not server-rendered.** `ssr: false` + `nuxt generate` emits plain files that
 * `apps/api` binds as Worker assets with an SPA fallback. No Nitro server is deployed:
 * the Worker stays the Hono app Phase 4 built, and every non-`/api` request is a static
 * asset — free and unlimited, which is only true while they *are* assets (v2-plan §6).
 *
 * v1 ran `nuxt build` (a server build) and then shipped `.output/public`, discarding the
 * server it had just built. `nuxt generate` makes the deployable artifact the declared
 * output rather than a side effect.
 *
 * **Nuxt 4**, with the `app/` srcDir. v1 is on 3.17; the port was a file-by-file move
 * into a directory that did not exist yet, and Nuxt 4's headline breaking change is
 * exactly that move — so absorbing it cost almost nothing here and would have cost a
 * second pass over every file later.
 */

import tailwindcss from "@tailwindcss/vite";

/**
 * The public origin.
 *
 * v1 hardcoded `hololive-ocg-wiki.lichingchester.dev` into five places — `site.url`,
 * `i18n.baseUrl`, the canonical link, the og/twitter image URLs and `plugins/seo.ts` —
 * which is why moving domains is a Phase 5 chore at all. One constant here instead.
 */
const SITE_URL = process.env.NUXT_PUBLIC_SITE_URL
  ?? "https://hololive-ocg-wiki.tskrlabs.com";

/**
 * Whether this build may be indexed and may report analytics.
 *
 * **Off until Phase 7, deliberately.** v1 stays live and indexed with a year of SEO on
 * the same 2,448 cards; a second indexed copy would be duplicate content competing with
 * a site we have not yet decided how to retire (v2-plan §7 defers that decision, and an
 * indexed v2 would pre-empt it). Analytics is off for the same window so pre-launch
 * traffic — the maintainer, and agents — does not pollute the container holding v1's
 * real year of data.
 *
 * Flipping this to `true` is a Phase 7 launch step. If it is missed, the new site stays
 * invisible.
 */
const IS_PUBLIC = process.env.NUXT_PUBLIC_LAUNCHED === "true";

export default defineNuxtConfig({
  compatibilityDate: "2026-07-26",
  devtools: { enabled: false },

  // D13: the rendering mode does not change. v1 is already an SPA, and SSR/prerender was
  // considered and deliberately deferred during the v2 design.
  ssr: false,

  future: { compatibilityVersion: 4 },

  site: {
    url: SITE_URL,
    name: "Hololive OCG Wiki",
    description:
      "A fan-made wiki for Hololive OCG, featuring card information, deck builder, and more.",
    defaultLocale: "tc",
    // @nuxtjs/seo reads this: it drives robots.txt, the sitemap and the robots meta tag
    // together, so there is one switch rather than three that can disagree.
    indexable: IS_PUBLIC,
  },

  seo: { fallbackTitle: false },
  sitemap: { autoLastmod: true, enabled: IS_PUBLIC },

  runtimeConfig: {
    public: {
      siteUrl: SITE_URL,
      launched: IS_PUBLIC,
      /**
       * The card image CDN (D9).
       *
       * D1 stores an `image_key` and the client composes the URL through
       * `cardImage(key, base)` from `@holo/schema`. v1 baked the folder layout *and* the
       * `.png` extension into the database, so changing host or format meant a reseed.
       */
      imageBaseUrl:
        process.env.NUXT_PUBLIC_IMAGE_BASE_URL
        ?? "https://img.hololive-ocg-wiki.tskrlabs.com",
    },
  },

  app: {
    head: {
      // `titleTemplate` is deliberately absent here.
      //
      // v1 set `title: "Hololive OCG Wiki"` *and*
      // `titleTemplate: "%s | Hololive OCG Wiki"`, so any page that set no title of its
      // own rendered "Hololive OCG Wiki | Hololive OCG Wiki". Setting only the template
      // is worse — `%s` resolves empty and the title becomes "| Hololive OCG Wiki".
      //
      // `nuxt-seo-utils` handles this correctly from `site.name`: a page with a title
      // gets "<title> | Hololive OCG Wiki", one without gets the site name alone. That
      // is also why `seo.fallbackTitle` is false — the pages set their own titles
      // through `useSeoMeta`.
      title: "Hololive OCG Wiki",
      meta: [
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { charset: "utf-8" },
        { name: "format-detection", content: "telephone=no" },
        { name: "application-name", content: "Hololive OCG Wiki" },
        { name: "apple-mobile-web-app-title", content: "Hololive OCG Wiki" },
        { name: "apple-mobile-web-app-capable", content: "yes" },
        { name: "apple-mobile-web-app-status-bar-style", content: "default" },
        { name: "mobile-web-app-capable", content: "yes" },
      ],
      link: [
        { rel: "icon", type: "image/x-icon", href: "/favicon.ico" },
        { rel: "manifest", href: "/manifest.json" },
        // Card art comes from another origin on the very first paint (D9), so the
        // handshake is worth starting before the markup asks for an image.
        { rel: "preconnect", href: "https://img.hololive-ocg-wiki.tskrlabs.com" },
      ],
    },
  },

  css: ["~/assets/css/app.css"],

  components: [{ path: "~/components", pathPrefix: false }],

  /**
   * The SEO modules are listed individually rather than via the `@nuxtjs/seo`
   * meta-package, which is what v1 used.
   *
   * `@nuxtjs/seo` pulls six sub-modules, two of which this site does not use:
   * `nuxt-og-image` (a satori/resvg rasteriser — v1 configured it but never called
   * `defineOgImage()`, and its build output contains no generated images) and
   * `nuxt-schema-org` (v1 hand-writes its JSON-LD in `plugins/seo.ts`). The meta-package
   * installs all six unconditionally, before config is read, so `ogImage: false` cannot
   * opt out — it fails to *resolve* rather than declining to run.
   *
   * Naming the four that are actually used is both smaller and honest about the
   * dependency surface.
   */
  modules: [
    "@nuxt/fonts",
    "@nuxt/icon",
    "@nuxtjs/i18n",
    "shadcn-nuxt",
    "@nuxtjs/color-mode",
    "@vueuse/nuxt",
    "nuxt-gtag",
    "nuxt-site-config",
    "@nuxtjs/robots",
    "@nuxtjs/sitemap",
    "nuxt-seo-utils",
  ],

  // No `ogImage` block: `nuxt-og-image` is not installed (see `modules`). Pages set
  // `ogImage:` through `useSeoMeta`, which is a plain meta tag pointing at a static
  // `icon.png` — exactly what v1 shipped, minus the rasteriser it never invoked.

  gtag: {
    id: "GTM-MZHVHBGQ",
    // Configured but silent until launch — see IS_PUBLIC.
    enabled: IS_PUBLIC,
  },

  colorMode: { preference: "system", classSuffix: "" },

  i18n: {
    baseUrl: SITE_URL,
    locales: [
      { code: "tc", name: "繁體中文", language: "zh-TW", file: "tc.json" },
      { code: "ja", name: "日本語", language: "ja-JP", file: "ja.json" },
      { code: "en", name: "English", language: "en-US", file: "en.json" },
      { code: "id", name: "Bahasa Indonesia", language: "id-ID", file: "id.json" },
      { code: "ko", name: "한국어", language: "ko-KR", file: "ko.json" },
      { code: "th", name: "ภาษาไทย", language: "th-TH", file: "th.json" },
      { code: "es", name: "Español", language: "es-ES", file: "es.json" },
    ],
    // `tc` is the default and still carries a prefix, matching v1's URLs exactly. The
    // locale set is the contract's LOCALES, and a locale added there must be added here.
    defaultLocale: "tc",
    strategy: "prefix",
  },

  shadcn: { prefix: "", componentDir: "./app/components/ui" },

  vite: {
    plugins: [tailwindcss()],
  },

  nitro: {
    devProxy: {
      // Local development only. `nuxt dev` serves the site on :3000 and forwards `/api`
      // to `wrangler dev` on :8787, so relative `/api/...` paths work identically here
      // and in production — where the Worker serves both from one origin.
      //
      // This is why there is no API base URL in runtimeConfig: an absolute URL would
      // make production requests cross-origin and promote the CORS allowlist from
      // belt-and-braces to load-bearing (apps/api/src/index.ts).
      "/api": { target: "http://localhost:8787/api", changeOrigin: true },
    },
  },
});
