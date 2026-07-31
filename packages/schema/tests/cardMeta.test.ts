/**
 * The card page's `<head>`, pinned (ADR 0009 D8).
 *
 * Two emitters render these tags: the Worker injects them into the static shell with
 * `HTMLRewriter`, and the page emits them through `useSeoMeta` after hydration. A
 * difference between the two is **cloaking** — the same URL showing a crawler something
 * other than what a user sees — so `cardMetaTags()` is the single source and this is the
 * seam that keeps it single.
 *
 * The same construction as `localize.test.ts`: a committed golden file, so a change to
 * the tag set is a reviewable diff rather than a silent behaviour change. That matters
 * more here than for most tests, because the failure mode is invisible in the browser —
 * a crawler sees the injected tags and a developer sees the hydrated ones, and only a
 * fetch without JavaScript shows the difference.
 *
 * Regenerate with `node --test --test-update-snapshots`? No — the file is written by
 * `scripts/golden-meta.ts`, deliberately, so updating it is an explicit act.
 *
 * Note what is *not* asserted: the robots tag. It is compiled into the shipped JS by
 * `IS_PUBLIC` and hydration would overrule anything the Worker did with it, so
 * `cardMetaTags()` does not emit one at all (D9).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  cardDescription,
  cardImageUrl,
  cardJsonLd,
  cardMetaTags,
  cardPath,
  cardTitle,
  cardUrl,
  LOCALE_LANGUAGES,
  renderMetaTags,
} from "../src/cardMeta.ts";
import { localize } from "../src/localize.ts";
import { LOCALES, type Locale } from "../dist/enums.ts";
import type { Card } from "../dist/card.d.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = join(HERE, "..");
const REPO_ROOT = join(PACKAGE_ROOT, "..", "..");

const fixtures = JSON.parse(
  readFileSync(join(REPO_ROOT, "fixtures", "cards.json"), "utf-8"),
) as { cards: Card[] };

const SITE_URL = "https://hololive-ocg-wiki.tskrlabs.com";
const IMAGE_BASE = "https://img.hololive-ocg-wiki.tskrlabs.com";

const inputFor = (card: Card, locale: Locale) => ({
  card: localize(card, locale),
  locale,
  siteUrl: SITE_URL,
  imageBaseUrl: IMAGE_BASE,
});

test("the tag set matches the golden file for every fixture card and locale", () => {
  const golden = JSON.parse(
    readFileSync(join(PACKAGE_ROOT, "golden", "card-meta.json"), "utf-8"),
  );

  const produced: Record<string, unknown> = {};
  for (const card of fixtures.cards) {
    for (const locale of LOCALES) {
      produced[`${card.id}:${locale}`] = cardMetaTags(inputFor(card, locale));
    }
  }

  assert.deepEqual(produced, golden);
});

test("a URL is the image_key verbatim, with the locale prefix", () => {
  // D6: `{set}/{stem}` *is* `image_key`. If this ever diverges, every card URL in the
  // sitemap points somewhere the Worker cannot resolve.
  const card = fixtures.cards[0]!;
  assert.equal(cardPath(card.image_key, "tc"), `/tc/card/${card.image_key}`);
  assert.equal(
    cardUrl(card.image_key, "en", SITE_URL),
    `${SITE_URL}/en/card/${card.image_key}`,
  );
  // A trailing slash on the site URL must not double up.
  assert.equal(
    cardUrl(card.image_key, "en", `${SITE_URL}/`),
    `${SITE_URL}/en/card/${card.image_key}`,
  );
});

test("every locale is linked, plus x-default pointing at the site default", () => {
  // hreflang is what tells a crawler seven URLs are one card rather than seven
  // near-duplicates — which matters more here than usual, because the art is identical
  // across all seven.
  const card = fixtures.cards[0]!;
  const tags = cardMetaTags(inputFor(card, "tc"));
  const alternates = tags.filter((t) => t.attrs.rel === "alternate");

  assert.equal(alternates.length, LOCALES.length + 1);

  for (const locale of LOCALES) {
    const language = LOCALE_LANGUAGES[locale];
    const found = alternates.find((t) => t.attrs.hreflang === language);
    assert.ok(found, `no alternate for ${locale}`);
    assert.equal(found!.attrs.href, cardUrl(card.image_key, locale, SITE_URL));
  }

  const fallback = alternates.find((t) => t.attrs.hreflang === "x-default");
  assert.ok(fallback);
  // `tc` is the site's default locale, so an unmatched language lands there.
  assert.equal(fallback!.attrs.href, cardUrl(card.image_key, "tc", SITE_URL));
});

test("every tag carries the dedupe key unhead will adopt it under", () => {
  // The keys are the mechanism, not decoration. unhead's `createDomState` walks existing
  // `<head>` children on hydration and keys them by `dedupeKey`; a client `useSeoMeta`
  // then *updates* the Worker's element rather than appending a second one — but only
  // when both sides agree on the key. A wrong key here means duplicate tags in the wild.
  const tags = cardMetaTags(inputFor(fixtures.cards[0]!, "ja"));

  for (const tag of tags) {
    if (tag.tag === "meta") {
      const name = tag.attrs.name ?? tag.attrs.property;
      assert.equal(tag.key, `meta:${name}`, `wrong key for ${JSON.stringify(tag.attrs)}`);
    } else if (tag.attrs.rel === "canonical") {
      assert.equal(tag.key, "canonical");
    } else {
      assert.equal(tag.key, `alternate:${tag.attrs.hreflang}`);
    }
  }

  // ...and no two tags share one, or adoption would collapse them.
  const keys = tags.map((t) => t.key);
  assert.equal(new Set(keys).size, keys.length);
});

test("no robots tag is emitted, deliberately", () => {
  // `noindex` is compiled into the shipped JS by IS_PUBLIC, so hydration would overrule
  // anything injected here. Phase 7's build flag stays the single control (D9), and this
  // asserts the Worker never grows a second opinion about it.
  const tags = cardMetaTags(inputFor(fixtures.cards[0]!, "tc"));
  assert.equal(
    tags.find((t) => t.attrs.name === "robots"),
    undefined,
  );
});

test("CJK survives rendering to HTML, and quotes cannot break out", () => {
  // The site's default locale is tc and its source is ja, so almost every title is CJK.
  const card = fixtures.cards.find((c) => c.translations?.ja?.name) ?? fixtures.cards[0]!;
  const html = renderMetaTags(cardMetaTags(inputFor(card, "ja")));
  const name = localize(card, "ja").name!;

  assert.ok(html.includes(name), "the Japanese name should render intact");
  // Attribute injection: a name containing a quote must not close the attribute.
  const hostile = {
    ...localize(card, "ja"),
    name: 'x" onload="alert(1)',
  };
  const escaped = renderMetaTags(
    cardMetaTags({ card: hostile, locale: "ja", siteUrl: SITE_URL, imageBaseUrl: IMAGE_BASE }),
  );
  assert.ok(!escaped.includes('onload="alert(1)"'));
  assert.ok(escaped.includes("&quot;"));
});

test("the title and description name the card and its number", () => {
  // `card_number` is not unique — 2,463 cards over 1,228 numbers — but it is what
  // disambiguates the nine printings that can share a name, and what someone searching
  // for a specific one types.
  const card = fixtures.cards[0]!;
  const localized = localize(card, "tc");

  assert.ok(cardTitle(localized).includes(localized.card_number));
  assert.ok(cardTitle(localized).endsWith("| Hololive OCG Wiki"));
  assert.ok(cardDescription(localized).includes(localized.card_number));
  assert.ok(cardDescription(localized).includes(localized.rarity_code));
});

test("og:image points at the card's own art on the public CDN", () => {
  const card = fixtures.cards[0]!;
  const tags = cardMetaTags(inputFor(card, "tc"));
  const image = tags.find((t) => t.attrs.property === "og:image");

  assert.ok(image);
  // WebP, because that is all the public bucket holds — Phase 2 published WebP only.
  // Some social crawlers prefer JPEG/PNG; tracked as #42.
  assert.equal(image!.attrs.content, `${IMAGE_BASE}/${card.image_key}.webp`);
  assert.equal(cardImageUrl(card.image_key, `${IMAGE_BASE}/`), image!.attrs.content);
});

test("the JSON-LD describes the same card as the tags", () => {
  const card = fixtures.cards[0]!;
  const input = inputFor(card, "tc");
  const jsonLd = cardJsonLd(input) as Record<string, string>;

  assert.equal(jsonLd.url, cardUrl(card.image_key, "tc", SITE_URL));
  assert.equal(jsonLd.headline, cardTitle(input.card));
  assert.equal(jsonLd.inLanguage, LOCALE_LANGUAGES.tc);
});

test("the language map covers every locale the contract declares", () => {
  // A locale added to the contract without a BCP 47 tag here would emit
  // `hreflang="undefined"`, which a crawler reads as a broken alternate.
  for (const locale of LOCALES) {
    assert.ok(LOCALE_LANGUAGES[locale], `no language tag for ${locale}`);
    assert.match(LOCALE_LANGUAGES[locale], /^[a-z]{2}-[A-Z]{2}$/);
  }
  assert.equal(Object.keys(LOCALE_LANGUAGES).length, LOCALES.length);
});
