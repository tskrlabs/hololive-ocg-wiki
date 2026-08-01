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

import cardUrls from "@holo/schema/card-urls" with { type: "json" };
import { cardSitemapUrls } from "./lib/cardUrls";

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

/**
 * The locales, declared once.
 *
 * `i18n.locales` below and the sitemap's card URLs must agree — a locale in one and not
 * the other means either 2,463 sitemap entries pointing at a prefix that does not route,
 * or a whole language missing from the sitemap. The set is the contract's `LOCALES`, and
 * a locale added there must be added here.
 *
 * `as const` is load-bearing: `@nuxtjs/i18n` types `locales` against the literal union of
 * its own codes, so without it every `code` widens to `string` and the array stops being
 * assignable. That the typecheck rejects a widened list is the property worth keeping —
 * it is what makes a typo here a build failure rather than a locale silently missing from
 * the sitemap.
 */
const LOCALES = [
  { code: "tc", name: "繁體中文", language: "zh-TW", file: "tc.json" },
  { code: "ja", name: "日本語", language: "ja-JP", file: "ja.json" },
  { code: "en", name: "English", language: "en-US", file: "en.json" },
  { code: "id", name: "Bahasa Indonesia", language: "id-ID", file: "id.json" },
  { code: "ko", name: "한국어", language: "ko-KR", file: "ko.json" },
  { code: "th", name: "ภาษาไทย", language: "th-TH", file: "th.json" },
  { code: "es", name: "Español", language: "es-ES", file: "es.json" },
] as const;

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

  /**
   * `nuxt-seo-utils`. Its config key is `seo`, not `seoUtils` — worth stating, because
   * the wrong key is accepted silently by Nuxt and the defaults simply stay in force.
   *
   * `canonicalLowercase` is **off** (ADR 0009 D6, #33 §4).
   *
   * Card URLs are `image_key` verbatim and case-sensitive — `hSD01/hSD01-001_OSR` — and
   * the Worker 301s a wrong-case URL to the stored form. A lowercased canonical would
   * therefore point at a URL that redirects, on all 2,463 card pages.
   *
   * ⚠️ This is **defusing a latent conflict, not fixing a live bug**, and the difference
   * matters if you are deciding whether to keep the line. Verified in Chromium and in the
   * Worker's served bytes: the canonical is already case-correct today, because
   * `app.vue`'s `useHead` sets one and `nuxt-seo-utils` sets its own at
   * `tagPriority: "low"` — so ours wins and the lowercasing never reaches the tag.
   *
   * The setting is still `true` in the shipped runtime config, is read separately by
   * `useShareLinks`, and becomes live the moment anyone removes that `useHead` — at which
   * point every card canonical silently starts pointing at a redirect. One line to make
   * the config say what the site actually does.
   */
  seo: { fallbackTitle: false, canonicalLowercase: false },

  /**
   * The sitemap (#33 §5).
   *
   * `enabled: IS_PUBLIC` is the pre-launch invisibility guarantee and predates this: with
   * the flag unset, no sitemap is emitted at all.
   *
   * **Where the card URLs come from is the whole problem this solves.** `nuxt generate`
   * runs on Cloudflare's builder with no D1 binding and no credentials, and the site never
   * loads `cards.json` (21 MB — D8 moved querying to D1), so the list cannot be queried at
   * build time. `holo-data build` emits a committed `card-urls.json` instead — 2,463
   * entries, ~190 KB, verified by `make check` — and it is a static import here. No D1, no
   * credentials, no network during the build.
   *
   * **Splitting is per locale, and it is free.** 17,241 URLs at ~116 bytes is ~1.9 MB in
   * one file, inside both sitemap.org limits (50,000 URLs, 50 MB) — so this is for
   * legibility in Search Console, not necessity. `@nuxtjs/sitemap` already derives one
   * sitemap per locale from `@nuxtjs/i18n` and indexes them in `sitemap_index.xml`;
   * `cardSitemapUrls` routes each URL into its locale's file. Chunking stays off, so each
   * is one ~0.3 MB file of 2,464 URLs.
   *
   * See `lib/cardUrls.ts` for why the URLs are absolute — it is what keeps the module from
   * inlining hreflang alternates into every entry and taking this to ~12.3 MB.
   */
  sitemap: {
    autoLastmod: true,
    enabled: IS_PUBLIC,
    urls: () => cardSitemapUrls(cardUrls, LOCALES, SITE_URL),
  },

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
        // The `noindex` tag is stated here rather than left to `@nuxtjs/robots`.
        //
        // The module does emit one from `site.indexable: false` — but only through a
        // server render, and this app is `ssr: false` + `nuxt generate`, so there is no
        // render to inject into. Verified: with the module alone, the tag was absent
        // from the generated HTML *and* after hydration; only `robots.txt` carried the
        // rule. `robots.txt` is what well-behaved crawlers obey first, but v1 stays
        // indexed on the same 2,448 cards, so this is worth belt-and-braces (Q10).
        //
        // Spread so the tag simply does not exist once launched, rather than saying
        // "index, follow" — the absence of a robots tag already means index.
        ...(IS_PUBLIC ? [] : [{ name: "robots", content: "noindex, nofollow" }]),
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

  /**
   * The typefaces (ADR 0009 D22, #47).
   *
   * `@nuxt/fonts` was in `modules` with **no configuration at all** and no `font-family`
   * set anywhere in the CSS, so it had nothing to resolve — seven locales rendered in
   * whatever each OS picked. The stack now lives in `tailwind.css` as `--font-sans`; this
   * block controls what is *downloaded* for it.
   *
   * **Weight count is the lever, and it is a CJK lever.** Measured in a browser on
   * `/tc/prototype-identity` with real card names: fonts cost **1.5 MB** on a `tc` card
   * grid, **87% of it Noto Sans TC**, at roughly **70 KB per extra CJK weight**. Varying
   * only the weights requested: 400/500/700 → 292.8 KB, 400/600 → 224.3 KB, 400 → 156.7 KB.
   *
   * So Inter carries three weights (it is ~190 KB in total, and Latin is cheap) and each
   * Noto face carries two. D3's palette has no accent hue, which means weight does real
   * work here — but 500 *and* 700 on a CJK face is ~70 KB for a distinction nobody can
   * see at 12px.
   *
   * **No manual subsetting.** Google already splits Noto Sans TC into 105
   * `unicode-range` slices, so a browser fetches only those its glyphs touch — all card
   * text across `tc`+`ja`+`ko` uses 2,051 distinct CJK glyphs, about 10% of a full font,
   * and the slicing approximates that automatically.
   *
   * `defaults.subsets` is therefore **deliberately not set**. It reads like the control
   * for this and is not: `unifont`'s Google provider passes only `weights` and `styles`
   * to the CSS API and never looks at `subsets` (it is honoured by the `local` provider
   * alone). Setting `['latin', 'latin-ext']` here would look like it excluded CJK while
   * changing nothing — worse than leaving it out.
   *
   * ⚠️ **`global: true` on the CJK faces is load-bearing, not a preference.** The module
   * discovers families by scanning CSS for `font-family` and `--font-*` declarations, and
   * it resolves only the **first** family in a stack — every later entry is recorded as a
   * *fallback*, and fallbacks are never downloaded. So with `--font-sans` listing Inter
   * first, only Inter got `@font-face` rules and every CJK glyph fell through to a system
   * font. Verified before and after on `/tc`: `document.fonts` held 48 Inter faces and
   * **zero** Noto faces, on a page that is almost entirely Chinese.
   *
   * `global` injects a family's faces regardless of detected usage, which is precisely
   * the case here — these faces exist to be reached by *fallback*, so usage detection is
   * structurally unable to see them.
   *
   * ⚠️ **`@nuxt/fonts` is pinned at ≥0.14 for a correctness reason, not for features.**
   * On 0.11.4 the Google provider fetched the CSS API once per format — woff2 *and* a
   * legacy ttf/woff pass — and Google returns the legacy formats **unsliced**, as one file
   * per weight with no `unicode-range`. Those faces are emitted *last*, so they win the
   * cascade over the 420 correctly-sliced woff2 faces and the browser downloads the whole
   * font. Measured on the real production composition (`make preview`, `/tc`): **4,340 KB
   * in 3 files**, one of them a single 4 MB Noto TC blob — 2.9× worse than the 1,499 KB
   * #47 measured, and it defeats the slicing this whole block relies on.
   *
   * 0.14 makes the format list configurable and defaults it to `['woff2']`, so the legacy
   * pass is simply gone. Re-measured the same way: **638 KB on `/tc`**, 848 KB `ja`,
   * 386 KB `ko`, 304 KB `th`, and **47 KB on `/en`** — the last of those being the proof
   * that slicing is doing its job, since an English page touches no CJK slice at all.
   */
  fonts: {
    defaults: { weights: [400, 600], styles: ["normal"] },
    families: [
      // Three weights: 400 body, 500 for a card name on a tile, 600 for headings and the
      // active state that D4 denies a colour to. First in the stack, so it is discovered
      // normally and can be preloaded — it is the only face with no `unicode-range`.
      { name: "Inter", provider: "google", weights: [400, 500, 600] },
      { name: "Noto Sans TC", provider: "google", weights: [400, 600], global: true },
      { name: "Noto Sans JP", provider: "google", weights: [400, 600], global: true },
      { name: "Noto Sans KR", provider: "google", weights: [400, 600], global: true },
      { name: "Noto Sans Thai", provider: "google", weights: [400, 600], global: true },
    ],
  },

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
    // Spread because `LOCALES` is `as const` (readonly) and this option is mutable.
    locales: [...LOCALES],
    // `tc` is the default and still carries a prefix, matching v1's URLs exactly. The
    // locale set is the contract's LOCALES, and a locale added there must be added here.
    defaultLocale: "tc",
    strategy: "prefix",
  },

  shadcn: { prefix: "", componentDir: "./app/components/ui" },

  vite: {
    plugins: [tailwindcss()],
  },

  /**
   * Strip throwaway prototype routes from production builds.
   *
   * `nuxt generate` emits one HTML file per route into `.output/public`, and
   * `wrangler deploy` uploads that directory verbatim — so a route left in the repo
   * ships, regardless of any runtime guard inside the component. A `.output`-level
   * gitignore does not help: the deploy reads the built directory, not git.
   *
   * Prototype pages are dev-only by construction (see `app/components/prototype/`), so
   * they are removed from the route table unless this is a dev server.
   */
  hooks: {
    "pages:extend"(pages) {
      // `nuxt.config` is evaluated in Node, where `import.meta.dev` is not the dev flag
      // the app runtime sees — `process.env.NODE_ENV` is what distinguishes `nuxt dev`
      // from `nuxt generate` here.
      if (process.env.NODE_ENV !== "production") return;
      for (let i = pages.length - 1; i >= 0; i--) {
        if (pages[i]!.path.includes("prototype")) pages.splice(i, 1);
      }
    },
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
