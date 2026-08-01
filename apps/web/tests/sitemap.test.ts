/**
 * The sitemap's card URLs (#33 §5).
 *
 * This exists because the failure mode is silent. If the committed manifest were empty, or
 * the expansion returned nothing, `nuxt generate` would still succeed and still emit valid
 * XML — listing two URLs per locale instead of 2,465. Launch is a one-time SEO event, so
 * "the build was green and the sitemap was empty" is the expensive outcome, and it is
 * exactly the shape of bug F-019 recorded: real, shipped, and invisible to every test.
 *
 * The properties asserted are the ones a crawler depends on, not the implementation:
 * every card appears in every locale, at the URL the Worker actually serves, spread across
 * the per-locale sitemaps the index names.
 */

import { describe, expect, it } from "vitest";

import cardUrls from "../../../packages/schema/data/card-urls.json" with { type: "json" };
import { cardSitemapUrls, type SitemapLocale } from "../lib/cardUrls";

const LOCALES: SitemapLocale[] = [
  { code: "tc", language: "zh-TW" },
  { code: "ja", language: "ja-JP" },
  { code: "en", language: "en-US" },
  { code: "id", language: "id-ID" },
  { code: "ko", language: "ko-KR" },
  { code: "th", language: "th-TH" },
  { code: "es", language: "es-ES" },
];

const SITE_URL = "https://hololive-ocg-wiki.tskrlabs.com";

describe("the committed card manifest", () => {
  it("is not empty", () => {
    // The whole point. An empty manifest is a green build with no cards in the sitemap.
    expect(cardUrls.length).toBeGreaterThan(0);
  });

  it("carries a set and a stem in every image_key", () => {
    // `image_key` is the URL's two path segments verbatim (D6), so a key with the wrong
    // number of segments is a route that does not resolve.
    for (const card of cardUrls) {
      expect(card.image_key.split("/")).toHaveLength(2);
    }
  });

  it("needs no percent-encoding", () => {
    // All 2,461 stems are URL-safe unescaped (#33 §1). If that ever stops being true the
    // sitemap and the Worker must agree on the encoding, which is a decision, not a fix.
    for (const card of cardUrls) {
      expect(encodeURI(card.image_key)).toBe(card.image_key);
    }
  });
});

describe("cardSitemapUrls", () => {
  const urls = cardSitemapUrls(cardUrls, LOCALES, SITE_URL);

  it("emits every card in every locale", () => {
    expect(urls).toHaveLength(cardUrls.length * LOCALES.length);
  });

  it("builds the URL the Worker serves, casing intact", () => {
    const first = cardUrls[0]!;
    expect(urls[0]!.loc).toBe(`${SITE_URL}/tc/card/${first.image_key}`);
  });

  it("preserves the stored casing", () => {
    // A lowercased URL is one the Worker 301s away from — the same conflict
    // `canonicalLowercase: false` settles for the canonical tag.
    const mixedCase = cardUrls.find((card) => /[A-Z]/.test(card.image_key));
    expect(mixedCase).toBeDefined();
    expect(urls.some((url) => url.loc.endsWith(mixedCase!.image_key))).toBe(true);
  });

  it("routes each URL to its locale's sitemap by language, not code", () => {
    // `@nuxtjs/sitemap` names per-locale sitemaps from `language` (`__sitemap__/zh-TW.xml`).
    // Using `code` would create seven extra sitemaps instead of filling the existing ones.
    const sitemaps = new Set(urls.map((url) => url._sitemap));
    expect([...sitemaps].sort()).toEqual(LOCALES.map((l) => l.language).sort());
  });

  it("spreads the cards evenly across the locales", () => {
    for (const locale of LOCALES) {
      const forLocale = urls.filter((url) => url._sitemap === locale.language);
      expect(forLocale).toHaveLength(cardUrls.length);
    }
  });

  it("emits absolute URLs, which is what keeps hreflang out of the sitemap", () => {
    // The module skips its `xhtml:link` transform for absolute `loc` values. Relative
    // paths here would inline seven alternates per entry: ~1.9 MB becomes ~12.3 MB.
    for (const url of urls.slice(0, 50)) {
      expect(url.loc.startsWith("https://")).toBe(true);
    }
  });

  it("does not double the slash when the site URL has a trailing one", () => {
    const trailing = cardSitemapUrls(cardUrls.slice(0, 1), LOCALES.slice(0, 1), `${SITE_URL}/`);
    expect(trailing[0]!.loc).toBe(`${SITE_URL}/tc/card/${cardUrls[0]!.image_key}`);
  });
});
