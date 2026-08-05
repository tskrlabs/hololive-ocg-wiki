# ADR 0011 — Launch posture: analytics, crawlers, and social previews

**Status:** accepted — D1 amended 2026-08-05 (analytics consent granted; see the note under D1)
**Date:** 2026-08-02
**Closes:** [#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17) (managed
`robots.txt` inverts our `Disallow`), [#42](https://github.com/tskrlabs/hololive-ocg-wiki/issues/42)
(`og:image` is WebP-only), [#64](https://github.com/tskrlabs/hololive-ocg-wiki/issues/64)
(GA sets cookies without consent)

## Context

Phase 7 is a single switch — `NUXT_PUBLIC_LAUNCHED=true` — and it flips indexing and
analytics *together*. That is convenient and it is also why these three decisions had to
be taken at once: each one is dormant today and live the instant the flag moves. A triage
pass over the open issues before flipping it found that two of the three were the kind of
question that gets re-litigated in six months ("why is there no cookie banner?"), and one
had already been fixed at the zone without the code knowing.

The site had never been read as a *launch posture* — only as a set of unrelated tickets.
Read together they are one question: what does this site do to a visitor it has never met?

## D1 — Analytics: GA4 with consent denied, permanently. No banner.

> **Amended 2026-08-05 — `analytics_storage` is now granted.** D1 denied it on the theory
> that cookieless consent-denied pings would still yield pageviews, referrers and geography.
> They do not. GA4 uses consent-denied pings only for behavioural modelling, which never
> activates below traffic thresholds a fan wiki will not reach — so the property
> `G-LCSL88VF1N` recorded **zero events for the week after launch**, verified against the
> Data and Realtime APIs (a firing tag returning `204` proved nothing; `/g/collect` accepts
> every hit regardless of whether it is ever recorded). The posture is now
> `analytics_storage: "granted"` — the `_ga` cookie and a persistent identifier are set —
> with the three `ad_*` types still `denied` (no ads run, nothing fed to Google's ad
> systems), and the collection **disclosed in the `/about` privacy copy** rather than gated
> behind a banner. The reasoning below is kept as the original record; only the
> analytics-storage value and the privacy copy changed. D2 and D3 stand unaltered.

`nuxt-gtag` shipped configured with a GTM container id and `enabled: IS_PUBLIC`, so it was
silent pre-launch and would have started setting `_ga` cookies the moment the flag moved.
The site ships **Spanish** among its seven locales, which makes EU traffic expected rather
than hypothetical, and under GDPR/ePrivacy analytics cookies need prior consent.

**Decided: swap to the GA4 property `G-LCSL88VF1N`, and run Consent Mode v2 with every
storage type denied as the permanent state.**

```ts
gtag: {
  id: "G-LCSL88VF1N",
  enabled: IS_PUBLIC,
  initCommands: [["consent", "default", {
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    analytics_storage: "denied",
  }]],
}
```

GA4 still loads and still sends pings; it sets no cookie and issues no persistent
identifier. So there is nothing to consent to, and therefore no banner.

**The banner was the obvious answer and it is the worse one.** A banner is only worth
building if consent can be *granted* — and granting it re-introduces exactly the cookies
the banner exists to ask about. Building a consent surface to arrive back at cookies is
more work, more code, a decision on every first visit, and seven locales of copy, in
exchange for data a fan wiki does not need. Removing the need for consent is cheaper and
more honest.

What it costs: returning-visitor counts and session identity. What it keeps: pageviews,
referrers, geography, which cards get read — which is the whole reason the numbers exist,
namely deciding what to work on next.

`wait_for_update` is deliberately omitted. It exists to hold pings while a banner
resolves, and there is no banner to wait for.

**The `/about` privacy copy was rewritten to match**, and two of its claims were wrong
independently of this change:

- It said analytics "sets cookies". Now it says it sets none, and says *why* there is no
  banner — the absence of a banner otherwise reads as an oversight rather than a design.
- It said "typefaces are requested from Google Fonts, so Google receives the request."
  **That was already false.** `@nuxt/fonts` downloads and self-hosts at build time — the
  build emits 362 `.woff2` files under `_fonts/` and the HTML references none of Google's
  origins. #64 listed "self-host the fonts" as an option to *take*; it had been taken
  before the issue was written, and the privacy page was describing a third party the site
  does not contact.

⚠️ **Do not add a consent banner to "improve" this.** If richer analytics ever justify one,
that is an ADR, not a config tweak.

## D2 — Crawlers: allow everyone, and own the file

[#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17) recorded that Cloudflare's
zone-level managed `robots.txt` prepended its own `User-agent: *` group with `Allow: /`
above ours with `Disallow: /`. Two groups, opposite directives, conflict resolved in
favour of the least restrictive — so the domain most likely read as crawlable, the
opposite of what ADR 0006 Q10 decided. `noindex` had been the sole indexing guard since
2026-07-27 by acceptance rather than design.

**Fixed at the zone, not in code**: managed `robots.txt` turned off, bot blocking set to
"Do not block". Verified live immediately after:

```
$ curl https://hololive-ocg-wiki.tskrlabs.com/robots.txt
# START nuxt-robots (indexing disabled)
User-agent: *
Disallow: /

# END nuxt-robots
```

That restores what Q10 wanted — pre-launch the site is now guarded by `Disallow: /` **and**
`noindex` — and, more durably, puts `robots.txt` back under version control. What
`nuxt-robots` emits is what the site serves, on both origins.

It also unblocks `workers_dev: false`, which was held open only because comparing the two
origins was the sole way this bug was visible. That reason is gone.

**Decided: no AI-crawler rules of our own.** Turning off the managed block also removed
Cloudflare's `Content-Signal: ai-train=no` and its `Disallow` for GPTBot, ClaudeBot, CCBot,
Google-Extended, meta-externalagent and others. Those are not being re-added. The card data
is already public on the official card list, so blocking training crawlers protects nothing
that is not already open, and a fan wiki being cited is reach rather than loss.

Worth stating explicitly because the point of fixing #17 was that a zone default had
become policy nobody chose. Allowing everyone is now a decision, which is the actual
improvement.

At launch our rule flips to `Allow: /` and that is the entire file.

## D3 — Social previews: accept WebP

Card pages inject a real `og:image` pointing at the card art on R2, which is WebP-only —
the PNG originals (603 MB) exist locally and were never published, deliberately, since the
site itself only requests WebP.

Verified live rather than taken from the report:

```
$ curl -A 'facebookexternalhit/1.1' .../en/card/hPR/hBD24-001_P | grep og:image
og:image" content="https://img.hololive-ocg-wiki.tskrlabs.com/hPR/hBD24-001_P.webp"
$ curl -I .../hPR/hBD24-001_P.webp   →   HTTP/2 200 · image/webp · 86516 bytes
```

**Decided: accept it.** Discord, X and Slack render WebP previews; the notable holdout is
Facebook/Messenger, with LINE unreliable. For a Hololive card wiki, Discord and X are where
a card actually gets shared — the platforms that matter work, and the ones that do not
degrade to title + description rather than breaking.

The two alternatives both lose on cost:

- **Publish the PNG tree** (#42's own recommendation): no new code, and the free tier
  absorbs it — but it doubles the bytes every future set adds, permanently, to fix one
  platform. And PNG card art is a poor social image regardless: 400×559 portrait where
  crawlers want 1200×630.
- **A JPEG social derivative** is better on the merits and is a genuinely new
  `holo-data images` stage — not launch-eve work.

The on-demand transform #42 asked us to investigate (Cloudflare Images) is **paid**, and
free tiers only is a standing constraint. Ruled out by that, not by merit.

**What would reopen this:** referrer data showing real Facebook or LINE share traffic. At
that point the right build is the JPEG derivative, not the PNG upload — aspect ratio
matters as much as format.

## Consequences

- The launch switch no longer carries a hidden legal exposure. `NUXT_PUBLIC_LAUNCHED=true`
  turns on indexing and cookieless analytics, and nothing else.
- `robots.txt` is version-controlled again, and the zone can no longer silently change what
  the Worker appears to serve. That failure mode — `curl` against two origins returning
  different bytes for the same path — is closed.
- `workers_dev: false` can flip at launch as planned.
- The `/about` privacy section now describes the site that exists, in both directions: it
  claimed a cookie it will not set and a third party it does not contact.
