/**
 * The card URLs the sitemap lists (ADR 0009 D6, #33 §5).
 *
 * **Build-time only.** This sits beside `nuxt.config.ts` rather than under `app/` because
 * nothing here ships to the browser — it runs once, during `nuxt generate`, to turn the
 * committed manifest into `<url>` entries. The app itself never needs a list of every
 * card; it queries D1.
 *
 * It is a module rather than a lambda inside `nuxt.config.ts` for the reason F-019 cost a
 * whole phase: logic that lives only in config is logic no test can see. `CardListViewAPI`
 * was missing one prop and served 200 of 2,448 cards for a phase, because a prop that is
 * never passed exists only in a template. An empty sitemap would fail exactly as quietly —
 * `nuxt generate` succeeds, the file is valid XML, and it lists two URLs.
 */

/** One line of `packages/schema/data/card-urls.json`. */
export interface CardUrlEntry {
  /** `{set}/{stem}` — the URL's two path segments verbatim (D6). */
  image_key: string;
  card_number: string;
}

/** The subset of `@nuxtjs/i18n`'s locale config this needs. */
export interface SitemapLocale {
  /** The URL prefix — `tc`, `ja`, … (`strategy: "prefix"`, so every locale has one). */
  code: string;
  /** The BCP 47 tag, e.g. `zh-TW`. Also the per-locale sitemap's name — see below. */
  language: string;
}

/** A `@nuxtjs/sitemap` URL entry, as far as this file is concerned. */
export interface SitemapCardUrl {
  loc: string;
  _sitemap: string;
}

/**
 * Every card, in every locale, as absolute URLs.
 *
 * Two properties of the output are load-bearing and neither is obvious:
 *
 * **1. `loc` is absolute, and that is what keeps the sitemap small.** `@nuxtjs/sitemap`
 * auto-generates `xhtml:link` hreflang alternates for every i18n URL it recognises — seven
 * extra elements per entry, which #33 §5 measured at **~12.3 MB** against ~1.9 MB without.
 * Its transform skips any entry whose `loc` is already absolute (the `_abs` guard in
 * `dist/runtime/server/sitemap/builder/sitemap.js`), so emitting absolute URLs opts out.
 *
 * Card hreflang is not lost — it is carried in the page head instead (#34, and asserted by
 * `apps/api/tests/smoke.sh`), which is where Google reads it for a page it is fetching
 * anyway. **Do not "fix" these to relative paths**: it will look tidier, change nothing
 * visible, and 6× the sitemap.
 *
 * **2. `_sitemap` is the locale's `language`, not its `code`.** The module derives one
 * sitemap per locale and names it from `locale.language` (`nuxtseo-shared/dist/i18n.mjs`),
 * which is why the emitted files are `__sitemap__/zh-TW.xml` and not `tc.xml`. Using
 * `code` here would silently create seven *extra* sitemaps rather than filling the
 * existing ones.
 *
 * `lastmod` is deliberately absent. The pipeline knows when it *built*, not when a card
 * changed, so a per-card `lastmod` would be the same timestamp on 2,463 URLs — which tells
 * a crawler every card changed whenever any did, and is worse than saying nothing.
 */
export function cardSitemapUrls(
  cards: readonly CardUrlEntry[],
  locales: readonly SitemapLocale[],
  siteUrl: string,
): SitemapCardUrl[] {
  const origin = siteUrl.replace(/\/+$/, "");
  const urls: SitemapCardUrl[] = [];

  for (const locale of locales) {
    for (const card of cards) {
      urls.push({
        loc: `${origin}/${locale.code}/card/${card.image_key}`,
        _sitemap: locale.language,
      });
    }
  }

  return urls;
}
