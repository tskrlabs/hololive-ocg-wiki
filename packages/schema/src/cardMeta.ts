/**
 * A card page's `<head>` tags — one function, two emitters (ADR 0009 D8).
 *
 * The Worker injects these into the static shell with `HTMLRewriter` so a crawler that
 * runs no JavaScript sees them; the page emits the same set through `useSeoMeta` so
 * client-side navigation is correct. **A mismatch between the two is cloaking** — the
 * same URL serving different content to a crawler than to a user — so they are generated
 * from this one function rather than written twice.
 *
 * That is not a theoretical risk. unhead *adopts* server-rendered tags on hydration: its
 * `createDomState` walks every existing `<head>` child, computes a `dedupeKey`, and
 * registers it, so a client `useSeoMeta({ ogTitle })` **updates the Worker's `og:title`
 * element in place** rather than appending a second one — provided both sides emit the
 * same key. Same keys and same values means the transition is invisible; different values
 * means the page silently rewrites itself the moment JS runs.
 *
 * Pinned by a golden test, exactly as `localize()` is pinned across Python and
 * TypeScript (ADR 0001). Pure and dependency-free so both callers can import it.
 *
 * **Deliberately absent: the robots tag.** `noindex` is compiled into the shipped JS by
 * `IS_PUBLIC`, so a Worker that stripped or added it would be overruled by hydration
 * moments later. Phase 7's build flag stays the single control (D9), and stating that
 * here is the point — "inject metadata on the Worker" otherwise invites someone to handle
 * robots there too, creating two disagreeing sources for the one thing that must not
 * disagree.
 */

import type { LocalizedCard } from "../dist/localized-card.d.ts";
import { LOCALES, type Locale } from "../dist/enums.ts";

/** BCP 47 tags, matching `nuxt.config.ts`'s `i18n.locales[].language` exactly. */
export const LOCALE_LANGUAGES: Readonly<Record<Locale, string>> = {
  tc: "zh-TW",
  ja: "ja-JP",
  en: "en-US",
  id: "id-ID",
  ko: "ko-KR",
  th: "th-TH",
  es: "es-ES",
};

/**
 * One `<meta>` or `<link>`, named by the key unhead would dedupe it under.
 *
 * The `key` is not decoration: it is what makes adoption work, so it is part of the
 * contract this function guarantees rather than an implementation detail of the Worker.
 */
export interface MetaTag {
  /** `meta` or `link`. */
  tag: "meta" | "link";
  /** unhead's dedupe key — `meta:og:title`, `canonical`, `alternate:ja`. */
  key: string;
  /** Rendered attributes, in the order they are written. */
  attrs: Record<string, string>;
}

export interface CardMetaInput {
  card: LocalizedCard;
  locale: Locale;
  /** The site origin, no trailing slash — e.g. `https://hololive-ocg-wiki.tskrlabs.com`. */
  siteUrl: string;
  /** The public image CDN origin, no trailing slash. */
  imageBaseUrl: string;
}

/** A card's canonical path in one locale. `image_key` is the path verbatim (D6). */
export function cardPath(imageKey: string, locale: Locale): string {
  return `/${locale}/card/${imageKey}`;
}

/** The absolute canonical URL. */
export function cardUrl(imageKey: string, locale: Locale, siteUrl: string): string {
  return `${siteUrl.replace(/\/+$/, "")}${cardPath(imageKey, locale)}`;
}

/**
 * The page title.
 *
 * Name and card number, because the number is what disambiguates the nine cards that can
 * share a name — and it is what someone searching for a specific printing types. The
 * suffix matches `nuxt-seo-utils`' own `"<title> | <site name>"` so a card page reads
 * like every other page.
 */
export function cardTitle(card: LocalizedCard): string {
  const name = card.name ?? card.card_number;
  return `${name} · ${card.card_number} | Hololive OCG Wiki`;
}

/**
 * The description.
 *
 * Facts a searcher can match against, not prose: the name, the number and the rarity.
 * Rules text is deliberately excluded — it is long, it is the part most likely to be
 * truncated mid-sentence in a result snippet, and it is nearly identical across the
 * rarity variants that share a number.
 *
 * **The card type is deliberately absent**, though it would be a useful facet. Its only
 * human-readable form lives in `apps/web/i18n/locales/*.json` — `oshiCharacter` renders
 * as 推しホロメン — and the Worker cannot import the site's locale files. Including the
 * raw enum would put developer vocabulary into the meta description of 17,241
 * crawler-facing URLs in seven languages, which is worse than omitting the facet.
 *
 * Rarity codes need no such treatment: they are printed on the cards in Latin and are
 * identity strings in every locale (verified — `rarity.OSR` is `"OSR"` in all seven).
 */
export function cardDescription(card: LocalizedCard): string {
  const name = card.name ?? card.card_number;
  return [name, card.card_number, card.rarity_code].filter(Boolean).join(" · ");
}

/** The card's own art, on the public CDN. Always WebP — see the note in `cardMetaTags`. */
export function cardImageUrl(imageKey: string, imageBaseUrl: string): string {
  return `${imageBaseUrl.replace(/\/+$/, "")}/${imageKey}.webp`;
}

/**
 * Every tag a card page contributes to `<head>`, in a stable order.
 *
 * Order is part of the golden file: it is not semantically meaningful to a crawler, but
 * pinning it is what makes a diff between the two emitters readable rather than a set
 * comparison that hides a reordering.
 */
export function cardMetaTags(input: CardMetaInput): MetaTag[] {
  const { card, locale, siteUrl, imageBaseUrl } = input;
  const url = cardUrl(card.image_key, locale, siteUrl);
  const description = cardDescription(card);
  const image = cardImageUrl(card.image_key, imageBaseUrl);
  const title = cardTitle(card);

  const tags: MetaTag[] = [
    { tag: "meta", key: "meta:description", attrs: { name: "description", content: description } },
    { tag: "link", key: "canonical", attrs: { rel: "canonical", href: url } },

    { tag: "meta", key: "meta:og:type", attrs: { property: "og:type", content: "article" } },
    { tag: "meta", key: "meta:og:title", attrs: { property: "og:title", content: title } },
    {
      tag: "meta",
      key: "meta:og:description",
      attrs: { property: "og:description", content: description },
    },
    { tag: "meta", key: "meta:og:url", attrs: { property: "og:url", content: url } },
    // ⚠️ WebP is all the public bucket holds — Phase 2 published WebP only, and several
    // social crawlers prefer JPEG/PNG. Link previews may therefore not render art on some
    // platforms. Tracked as #42; it is a publish decision, not a code one.
    { tag: "meta", key: "meta:og:image", attrs: { property: "og:image", content: image } },
    {
      tag: "meta",
      key: "meta:og:site_name",
      attrs: { property: "og:site_name", content: "Hololive OCG Wiki" },
    },

    {
      tag: "meta",
      key: "meta:twitter:card",
      attrs: { name: "twitter:card", content: "summary_large_image" },
    },
    { tag: "meta", key: "meta:twitter:title", attrs: { name: "twitter:title", content: title } },
    {
      tag: "meta",
      key: "meta:twitter:description",
      attrs: { name: "twitter:description", content: description },
    },
    { tag: "meta", key: "meta:twitter:image", attrs: { name: "twitter:image", content: image } },
  ];

  // hreflang, one per locale plus x-default. These are what tell a crawler the seven
  // locale URLs are one card rather than seven near-duplicates competing with each other
  // — which matters here more than usual, since the *art* is identical across all seven.
  for (const alternate of LOCALES) {
    tags.push({
      tag: "link",
      key: `alternate:${LOCALE_LANGUAGES[alternate]}`,
      attrs: {
        rel: "alternate",
        hreflang: LOCALE_LANGUAGES[alternate],
        href: cardUrl(card.image_key, alternate, siteUrl),
      },
    });
  }
  tags.push({
    tag: "link",
    key: "alternate:x-default",
    attrs: {
      rel: "alternate",
      hreflang: "x-default",
      // `tc` is the site's default locale (`nuxt.config.ts`), so it is what an unmatched
      // language should land on.
      href: cardUrl(card.image_key, "tc", siteUrl),
    },
  });

  return tags;
}

/** HTML-escape a value for an attribute. */
function escapeAttr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * The tags as HTML, for the Worker's `HTMLRewriter` injection.
 *
 * The page does not use this — it feeds the same tags to `useSeoMeta`, which builds real
 * elements. Both start from `cardMetaTags()`, which is where agreement is guaranteed.
 */
export function renderMetaTags(tags: readonly MetaTag[]): string {
  return tags
    .map((tag) => {
      const attrs = Object.entries(tag.attrs)
        .map(([name, value]) => `${name}="${escapeAttr(value)}"`)
        .join(" ");
      return `<${tag.tag} ${attrs}>`;
    })
    .join("");
}

/**
 * JSON-LD for the card.
 *
 * Separate from the tag list because it is a `<script>`, not a meta tag, and unhead keys
 * it differently. v1 hand-wrote its JSON-LD in `plugins/seo.ts`; this keeps that approach
 * (ADR 0006 declined `nuxt-schema-org`) but derives it from the same card.
 */
export function cardJsonLd(input: CardMetaInput): Record<string, unknown> {
  const { card, locale, siteUrl, imageBaseUrl } = input;
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: cardTitle(card),
    description: cardDescription(card),
    image: cardImageUrl(card.image_key, imageBaseUrl),
    inLanguage: LOCALE_LANGUAGES[locale],
    url: cardUrl(card.image_key, locale, siteUrl),
    isPartOf: {
      "@type": "WebSite",
      name: "Hololive OCG Wiki",
      url: siteUrl.replace(/\/+$/, ""),
    },
  };
}
