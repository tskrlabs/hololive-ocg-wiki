/**
 * The card page, served with real metadata and a real status (ADR 0009 D7, D8, D9).
 *
 * `/{locale}/card/{set}/{stem}` is the one non-`/api` path the Worker handles, and it
 * exists because two things there cannot be done by a static asset:
 *
 * 1. **Metadata a crawler can read.** The generated shell carries no description, no
 *    canonical, no `og:*` and not even a `lang` attribute — everything meaningful is set
 *    after hydration, which a crawler that runs no JavaScript never sees. `HTMLRewriter`
 *    injects the same tags the page emits, from the same function (D8).
 * 2. **An honest status.** `not_found_handling: "single-page-application"` serves
 *    `index.html` with **HTTP 200** for any unmatched path. Verified against production:
 *    `/tc/card/hSD01/NOPE` returned 200 with generic site metadata — a textbook soft 404,
 *    and Google treats a site that emits them as lower quality across the board.
 *
 * **Prerendering was the alternative and does not fit**: 2,463 cards x 7 locales is
 * 17,241 files against a 20,000 free-tier asset cap. It would fit today and break within
 * two card sets.
 *
 * `HTMLRewriter` streams, so the 6 KB shell is never buffered — measured at 0-1 ms
 * against a 10 ms CPU limit. **Do not `await response.text()` here**: buffering is the
 * one thing that would make this expensive.
 */

import { Hono } from "hono";

import type { Env } from "../types.ts";
import { cardByImageKeySql, cardKeyByLowercaseSql, rowToCard, type CardRow } from "../db/cards.ts";
import { imageKeySegmentSchema } from "../lib/schemas.ts";
import {
  cardJsonLd,
  cardMetaTags,
  cardTitle,
  LOCALE_LANGUAGES,
  renderMetaTags,
} from "@holo/schema/card-meta";
import { LOCALES, type Locale } from "@holo/schema/enums";

export const cardPage = new Hono<{ Bindings: Env }>();

const DEFAULT_SITE_URL = "https://hololive-ocg-wiki.tskrlabs.com";
const DEFAULT_IMAGE_BASE = "https://img.hololive-ocg-wiki.tskrlabs.com";

/** How long a card page may be edge-cached. Matches the API's card TTL. */
const CARD_PAGE_TTL = 3600;

/** Escape text for insertion into an element's content. */
function escapeText(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Replace the shell's `<title>`, rather than appending a second one.
 *
 * The shell ships `<title>Hololive OCG Wiki</title>`; leaving it and adding another
 * would give a crawler two, and which one wins is not something to leave to chance.
 */
class SetTitle {
  constructor(private readonly title: string) {}

  element(element: Element) {
    element.setInnerContent(escapeText(this.title));
  }
}

/**
 * Set `<html lang>`, which the generated shell omits entirely.
 *
 * `nuxt generate` emits a bare `<html>`; the locale is applied on hydration. A crawler
 * therefore sees seven locale variants with no declared language, which is exactly what
 * the `hreflang` alternates are trying to tell it about.
 */
class SetLang {
  constructor(private readonly lang: string) {}

  element(element: Element) {
    element.setAttribute("lang", this.lang);
  }
}

/** Append the card's tags and its JSON-LD to `<head>`. */
class InjectHead {
  constructor(private readonly html: string) {}

  element(element: Element) {
    element.append(this.html, { html: true });
  }
}

/**
 * `/{locale}/card/{set}/{stem}`.
 *
 * The locale is validated against the contract rather than passed through: a bad locale
 * is a 404 like a bad key, not a card rendered in the default language at a URL that
 * claims otherwise (#33 §3).
 */
cardPage.get("/:locale/card/:set/:stem", async (c) => {
  const locale = c.req.param("locale");
  const set = imageKeySegmentSchema.safeParse(c.req.param("set"));
  const stem = imageKeySegmentSchema.safeParse(c.req.param("stem"));

  const url = new URL(c.req.url);
  const siteUrl = c.env.SITE_URL ?? DEFAULT_SITE_URL;
  const imageBaseUrl = c.env.IMAGE_BASE_URL ?? DEFAULT_IMAGE_BASE;

  /**
   * The SPA shell, with whatever status this request deserves.
   *
   * The body is always the shell — the client router renders a proper in-app screen for
   * a missing card — but the *status* is what a crawler reads, and the two are
   * independent. That is the whole point: a 404 that still renders the app.
   */
  const shell = async (status: number, inject?: string, lang?: string, title?: string) => {
    const shellLocale = (LOCALES as readonly string[]).includes(locale) ? locale : "tc";
    const asset = await c.env.ASSETS.fetch(new URL(`/${shellLocale}/`, url));

    let rewriter = new HTMLRewriter();
    if (lang) rewriter = rewriter.on("html", new SetLang(lang));
    if (title) rewriter = rewriter.on("title", new SetTitle(title));
    if (inject) rewriter = rewriter.on("head", new InjectHead(inject));

    const response = rewriter.transform(asset);

    // A new Response, because `status` is immutable on the transformed one.
    return new Response(response.body, {
      status,
      headers: {
        "content-type": "text/html; charset=utf-8",
        // A missing card must not be cached as long as a real one: the usual reason a
        // key 404s is that it is about to exist.
        "cache-control":
          status === 200 ? `public, max-age=${CARD_PAGE_TTL}` : "public, max-age=60",
        // No `Vary`: the locale is in the path, not in a header.
      },
    });
  };

  if (!(LOCALES as readonly string[]).includes(locale)) return shell(404);
  if (!set.success || !stem.success) return shell(404);

  const imageKey = `${set.data}/${stem.data}`;
  const query = cardByImageKeySql(imageKey);
  const row = await c.env.DB.prepare(query.sql)
    .bind(...query.params)
    .first<CardRow>();

  if (!row) {
    // A wrong-case URL redirects to the canonical form rather than 404-ing (#33 §4).
    // Costs one extra scan, on the error path only.
    const alternate = cardKeyByLowercaseSql(imageKey);
    const canonical = await c.env.DB.prepare(alternate.sql)
      .bind(...alternate.params)
      .first<{ image_key: string }>();

    if (canonical) {
      return c.redirect(`${url.origin}/${locale}/card/${canonical.image_key}`, 301);
    }
    return shell(404);
  }

  const card = rowToCard(row, locale as Locale);
  const meta = { card, locale: locale as Locale, siteUrl, imageBaseUrl };

  /**
   * The tags, plus JSON-LD.
   *
   * **The robots tag is deliberately not among them** (D9). `noindex` is compiled into
   * the shipped JS by `IS_PUBLIC`, so stripping or adding it here would be overruled by
   * hydration moments later — Phase 7's build flag stays the single control.
   */
  const injected =
    renderMetaTags(cardMetaTags(meta)) +
    `<script type="application/ld+json">${JSON.stringify(cardJsonLd(meta)).replace(
      /</g,
      "\\u003c",
    )}</script>`;

  return shell(200, injected, LOCALE_LANGUAGES[locale as Locale], cardTitle(card));
});
