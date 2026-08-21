# v2 rebuild — progress

**Where we are:** Phases 0–5 **and 8** are done and **deployed**. The site is live at
`hololive-ocg-wiki.tskrlabs.com` — one Worker serving the API and the static site from one
origin (D2), against **2,559 cards** in D1 and images on R2.

✅ **`v2.0.1` is tagged and published** (2026-08-19), retroactively covering the analytics
fix that had shipped unannounced on 2026-08-05, plus the pipeline repair below. Everything
on `main` is now tagged. The release procedure is a skill: `.claude/skills/release/`, with
the reasoning in [`docs/agents/release.md`](agents/release.md).

**Its central distinction is that a card-set update is *not* a release** — the API reads D1
and R2 directly, so card data goes live with no deploy and `/status` reports it at runtime.
Only the sitemap waits on a merge. So `cards` mode never tags, and stops if anything outside
a two-path allowlist rode along; `site` mode drafts both notes files, enforces the house
style, and refuses to tag notes nobody has read.

⚠️ **A deploy cannot be verified by grepping `_nuxt/` chunks.** Confirming v2.0.1 took far
longer than it should have because three plausible checks are all invalid: chunk **filenames
repeat across builds** and are served `immutable` for a year, so a familiar name is a CDN
`HIT` on the *old* bytes; a missing chunk returns the **SPA fallback HTML** with
`content-type: text/javascript`, so a naive grep silently searches a 6.6 KB HTML page; and
the page's own component is **lazily imported**, so it appears in no `<link modulepreload>`
and no crawl of the entry chunk's dep map finds it. The check that works is
`/_nuxt/builds/latest.json`, whose `timestamp` is the build time — compare it to the merge.
To confirm specific *copy*, read the route table out of the entry chunk to get the page
component's real name (`changelog___en` → `5gR7uFX3.js`), then grep that.

## ✅ The card set is at 2,650 — an alt-art run, 2026-08-21

The official list grew 2,559 → 2,651 entries, of which one is the rules notice `build`
splits out to R2, so **2,650 cards**. The 91 additions are alt-art and variant printings
spread across *existing* sets (27 hBP01, 16 hBP02, 11 hBP03, 9 hEB01, 7 hBP05, 6 hBP04, the
rest scattered), not a new set.

| step | result |
|---|---|
| `backup-cache --remote` | both caches snapshotted and verified, local + R2 (11 backups, 180.6 MB) |
| `scrape` | 2,651 entries, **no unmapped enum values** |
| `images` | 92 converted, 2,560 skipped; PNG 815 MB → WebP 225 MB (72% smaller) |
| `translate-units --confirm` | 24 units × 6 locales, **9,473 tokens** |
| `build` | 2,650 cards, **100% coverage in all 7 locales**, 0 dropped |
| `publish` | 101 objects (92 images + 9 artifacts) |
| `seed --confirm` | 1,627 cards, **38,611 rows written** against a 40,635 estimate |

**`build` succeeded before the translation pass, which the runbook says should fail.** That
expectation assumes a new set; alt-art printings reuse existing card text, so every unit was
already cached. The failure is a signal about *what kind* of update this is, not a step to
tick off — worth reading before treating a passing build as a skipped gate.

**1,536 cards reported as edited, and it was real.** All 1,536 verified field by field
against D1, not sampled: 1,530 moved `card_sets` only, every one of them gaining
`【使用可能カード】hGS 2026 大阪 セレクションロード` as the official site tagged them legal
for that event. Nothing removed, no card text rewritten. Same shape as the Selection Cup
update `source_payload`'s docstring already records, and `source_hash` correctly called it an
official change rather than something we did.

### The official site normalised CRLF, and it cost two cards their translations

The remaining 6 of those 1,536 moved `translations` too. The official site rewrote `\n\r\n`
to `\n\n` in the JP source — invisible to a reader, but the v2 cache is **content-addressed
on the source string**, so the key moved and the lookup fell through to the v1 legacy cache
underneath. Four cards landed on merely older text. Two landed on worse:

- **hBP02-095** — the Indonesian ability came back as raw Japanese
  (`◆〈Houshou Marine〉なら能力追加`), and `tc` rendered Arts as 藝術 (artwork).
- **hBP01-126** — the same 藝術 mistranslation in `tc`.

**The v1 fallback held a wrong-source value.** Under hBP02-095's key sat a translation of a
*different card* — Yukihana Lamy's mascot, not Houshou Marine's. Because a fallback hit
counts as fresh, `translate-units` planned nothing for it and `build` would have written it
without complaint. A whitespace edit upstream was enough to surface it.

Fixed by evicting the two units from the v2 cache (12 entries, 2 units × 6 locales) so they
re-translated. Both verified correct in the build and then live. Filed as
[#78](https://github.com/tskrlabs/hololive-ocg-wiki/issues/78) — the eviction fixes these two
cards, not the reason a wrong-source value was in the cache at all.

**A repo-wide scan found 382 cards with kana in a non-JP locale, but only one is this run's
doing.** 373 were already live, and 8 of the 9 apparent regressions are false positives from
the detector: `・` (U+30FB) is ordinary punctuation in Chinese transliterated names, and
`博衣こより` is Koyori's official name. Any future kana-leak check needs both exclusions or it
will cry wolf on ~380 healthy cards.

**Two things worth knowing about editing the translation cache.** Its on-disk key is
`locales`, not `entries` (`entries` is the in-memory field) — hand-editing the JSON against
the wrong key silently writes an empty cache. Use `TranslationCacheV2.load()`/`.save()`.
And identify a unit by **exact** source match: a substring match on shared mascot phrasing
selected 17 units instead of 2 here, which would have spent calls re-translating text nobody
approved touching. Both mistakes were caught and reverted from backups taken first.

Live after the seed: total **2,650** · `/api/info` **3** · hBP02-095 `id` naming Houshou
Marine with no kana · hBP01-126 `tc` reading Arts.

## ✅ The card set is at 2,559 — the first real update run, 2026-08-19

The official list grew 2,463 → 2,559, and the whole pipeline ran end to end:
`backup-cache` → `scrape` → `images` → `translate-units` → `build` → `publish` → `seed` →
merge to `main`. Deployed as [#72](https://github.com/tskrlabs/hololive-ocg-wiki/pull/72).

| step | result |
|---|---|
| `backup-cache --remote` | both caches snapshotted and verified, local + R2 |
| `scrape` | 2,559 cards, **no unmapped enum values** — the new set printed nothing new |
| `images` | 96 converted, 2,464 skipped; PNG 777 MB → WebP 218 MB (72% smaller) |
| `translate-units --confirm` | 720 units × 6 locales, **87,306 tokens** |
| `build` | 2,559 cards, **100% coverage in all 7 locales**, 0 dropped |
| `publish` | 105 objects (96 images + 9 artifacts); a second run uploads nothing |
| `seed --confirm` | 757 cards, **16,718 rows written** against a 16,542 estimate |

Live after the seed: total **2,559** · `フブキ` **74** (was 73) · `白上フブキ&locale=en`
**45** (was 44) · filter names **306** (was 296) · `tag=0期生` **178** (was 165) ·
`set_code=hEB01` **35** · sitemap **2,563** URLs per locale (was 2,467).

**The data went live before the deploy, and the sitemap did not.** The API reads D1 and R2
directly, so cards, images and card pages served the new set the moment `seed` and
`publish` finished — the merge to `main` was needed only for the sitemap, which is baked
into the static build from the committed `card-urls.json`. Worth knowing when planning an
update: the crawlable surface is the part that waits on a deploy.

**`translate-units` could not onboard a new card set at all** — found here, fixed here
(`b0338b7`). It collected its work from the built `cards.json`, which is the one artifact
guaranteed not to contain a new set: `build` refuses to write a card whose locales are
missing, so on an update the build on disk is the *previous* set. The two commands
deadlocked, and silently — `translate-units` reported "everything is up to date" while
`build` failed validation on the cards needing exactly the translations it had declined to
fetch. 132 new units were invisible to it. `translate` has always read `load_i18n()`; only
the v2 units path diverged. Guarded by a test pinned by sabotage.

Two more things this run turned up, neither a defect:

- **The rules notice is gone.** Card 2459 is no longer in the official list, so
  `notices.json` is now empty. `publish` and `/api/notices` already treat that as a normal
  state rather than an error — F-020's split held.
- **Three Spanish art names were rejected on the first pass**, the masking guard catching
  the model inventing a `[[N0]]` placeholder absent from the source. Left stale as designed;
  a targeted `--locale es` re-run translated all three for 414 tokens. This is the "failure
  is loud" rule doing its job on live data for the first time.

✅ **Analytics now records data** (2026-08-05, [ADR 0011 D1](adr/0011-launch-posture.md)
amended). The launch posture ran GA4 with `analytics_storage` denied, betting that cookieless
consent-denied pings would still yield pageviews and geography. They do not — GA4 uses those
pings only for behavioural modelling, which never activates at this traffic, so
`G-LCSL88VF1N` recorded **zero events for the week after launch** (confirmed against the Data
and Realtime APIs; a firing tag returning `204` proved nothing, since `/g/collect` accepts
every hit whether or not it is recorded). Now `analytics_storage: granted` sets the `_ga`
cookie and a persistent identifier, the `ad_*` types stay denied (no ads run), and the
collection is disclosed in the `/about` privacy copy rather than behind a banner. Takes
effect on the next deploy.

✅ **Set-code filtering and the two search fixes are merged and live** (2026-08-02,
[ADR 0010](adr/0010-set-code-and-search.md)). Merged as `b2ed102`; verified in production
— `/api/cards/filter?search=hBP03` returns **HTTP 200**, where it was a 500. Migration
0004 and the full reseed (52,060 rows) had already been applied, so the code was the last
piece.

What it does: a set code (`hBP03`) becomes a filter dimension of its own, typing one into
the search box applies it, and `?set_code=hBP03` is the first filter with a URL. What it
fixed on the way: every search matching >100 cards was a 500 ([#66](https://github.com/tskrlabs/hololive-ocg-wiki/issues/66)),
and Q&A text was 88% of the search index, so a ruling outranked the card it cited
([#67](https://github.com/tskrlabs/hololive-ocg-wiki/issues/67)).

🚀 **Phase 7 launched 2026-08-02.** The site is public, indexable and reporting analytics.
[#68](https://github.com/tskrlabs/hololive-ocg-wiki/pull/68) merged to `main` and Workers
Builds deployed it. Its three blocking questions were settled first in
[ADR 0011](adr/0011-launch-posture.md): GA4 `G-LCSL88VF1N` runs Consent Mode v2 with every
storage type denied, so it sets no cookies and needs no banner; `robots.txt` is ours alone
again (the zone's managed block is off) and allows every crawler including AI ones,
deliberately; `og:image` stays WebP.

Verified live, not assumed: `robots.txt` indexable with a `Sitemap:` line ·
`sitemap_index.xml` served as real `text/xml` rather than the SPA fallback · gtag
initialising as `G-LCSL88VF1N` with all four consent types `denied` · no `noindex` meta and
no `X-Robots-Tag` (the one `noindex` in the HTML is the module's inert
`robotsDisabledValue` config string) · `workers.dev` origin unreachable · `/api/health` ok,
2,463 cards.

**The launch was three switches and only one lived in the repo.**
`NUXT_PUBLIC_LAUNCHED=true` is a Workers Builds **build** variable — it is read by
`nuxt generate`, and `vars` in `wrangler.jsonc` are runtime-only, so they never reach the
build. Worth knowing before anyone looks for it in version control: the flag that makes the
site visible is not in this repo, and the two switches are independently sufficient to
produce an invisible deploy.

**What remains is the maintainer's**: make the repo public, archive v1 (v2-plan §7).

**Phase 8 went live 2026-08-02** together with ADR 0009 D26, and
[#63](https://github.com/tskrlabs/hololive-ocg-wiki/pull/63) merged it to `main`. Both
migrations are applied, the seed has run, and every number Phases 3 and 4 measured came
back exactly — see [the deploy record](#-phase-8--d26-deployed-2026-08-02).

🔎 **The merge appears to have triggered a build — which means Workers Builds may already
be connected.** `82c4ad6b` was the manual `wrangler deploy` at 03:02; #63 merged at
03:13:59; version **`6922d991`** appeared at **03:15:28** and is now serving 100%. Nobody
ran `wrangler deploy` in between. That is 90 seconds after a merge to `main`, which is what
push-to-deploy looks like.

**Not confirmed, and worth confirming**: `wrangler versions list` reports `Source: Unknown
(version_upload)` for both, and the seeder token is scoped to D1 so it cannot read the
Workers service to see a build trigger. **A maintainer should check the dashboard.** If it
is connected, Phase 6's remaining step is done and this file's "needs the dashboard step"
is stale; if it is not, something else uploaded a version and *that* is worth knowing.

What *is* verified: the version serving now is byte-identical to the audited local build —
`_nuxt/DlbQCJnW.js` matches on sha256 — and it carries D26's copy. So whatever produced it
produced the right bytes.

✅ **Phase 8 — the UI/UX rework — is done.** All six prerequisites (`61b2793..77720d0`) and
all sixteen commits (`95c75fc..441c885`) are on `develop`, `make check` green after each.

✅ **D26 was added and deployed on 2026-08-02: `/status` reports what the *official card
list* did, not just what our database did.** `content_hash` covers all seven locales' text,
so the translation rework marks every card `changed` while the official site published
nothing — a true number telling a false story, and the only number the page had. A third
column, `source_hash`, hashes the JP source alone (minus Q&A, mirroring `qa_hash`'s split),
so the page leads with `source_added` / `source_changed` / `faq_changed` and keeps the
re-seed count as a self-explaining footnote. The write plan is untouched; the report sets
are independent, which also fixes `qa_updated` reading 0 whenever a card was edited *and*
re-FAQ'd. The artifact dropped **329 KB → 644 bytes** in production (lists capped at 100,
counts stay true), which the about dialog also pays.
See [ADR 0009 D26](adr/0009-ui-rework.md#supporting-surfaces).

🔄 **D18 was amended on 2026-08-01: the deck is a *pushed* panel from `xl`, not an overlay
drawer.** Building it revealed the original had never actually run — `DeckDrawer` was a
`Sheet` at every width, so the "overlay beside a still-visible grid" was a modal over a
blacked-out one, and the deck-open ⇒ editing coupling applied to a grid you could not
click. It now pushes: `<main>` shrinks and #43's rule turns the narrower box into fewer
columns rather than smaller cards (6 → 4 at 1512px, tile 205 → 212px). Two bugs found and
fixed, both invisible to `make check` and both wiring rather than logic — see
[ADR 0009 D18](adr/0009-ui-rework.md#deck-building). Phase 5's D13 had fenced the website to
refactors, so v2's *inside* was new while its **outside was still v1's** — a stock shadcn
theme, an art-only grid, and **no URL for a card**. Every card now has one, the sitemap
lists all 17,241, and a bad key returns a real 404. Twenty-five decisions in
[ADR 0009](adr/0009-ui-rework.md); the sequence and what it found are
[below](#phase-8--the-uiux-rework).

✅ **Both migrations are applied** (2026-08-02). `0002-phase8-image-key-unique.sql` wrote
2,464 rows building the index, which is also proof no duplicate `image_key` existed;
`EXPLAIN QUERY PLAN` on a card lookup now reports
`SEARCH cards USING INDEX idx_cards_image_key` rather than the 2,463-row scan it would
otherwise be. `0003-source-hash.sql` followed. See
[the deploy record](#-phase-8--d26-deployed-2026-08-02).

⚠️ **Phase 5 needed a follow-up.** Visual QA of the live site found the homepage serving
**200 of 2,448 cards** — infinite scroll had never fired, because `RecycleScroller` gates
its `scroll-end` emit behind an `emit-update` prop the card list did not pass. One prop
fixed it. The reason it survived a whole phase is the part worth keeping: all 44 web tests
targeted pure functions, so a prop that was never passed was invisible to `make check`,
and `make dev`'s 34-card fixture set is too small to ever produce a second page. Web tests
now include a mounted component; local QA of pagination still requires pointing the dev
server at the deployed Worker. See [F-019](./archive/findings.md#f-019).

✅ **The site is double-guarded again** (2026-08-02). Cloudflare's zone-level managed
`robots.txt` used to prepend `Allow: /` above ours, leaving `noindex` as the sole indexing
guard by acceptance rather than design. The maintainer turned the managed block off, and
`curl` now returns our `Disallow: /` alone — so ADR 0006 Q10's two independent guards are
back, and `robots.txt` is version-controlled again. That also unblocks `workers_dev: false`,
which was held open only so the two origins could be compared.
Closes [#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17); see
[ADR 0011 D2](adr/0011-launch-posture.md) and [F-017](./archive/findings.md#f-017).

**Phase 5's design is recorded.** Sixteen decisions, in
[ADR 0006](adr/0006-website.md). **Phase 6's** is fifteen decisions, in
[ADR 0007](adr/0007-push-to-deploy.md).

## ✅ The translation rework is done, and live

All six locales are re-translated through a content-addressed cache. **Divergence is
zero** on every name field in every locale — not reduced, but *unrepresentable*: one
source string has one cache slot, so two cards printing the same Japanese cannot
disagree. That closes [#20](https://github.com/tskrlabs/hololive-ocg-wiki/issues/20) and
[#21](https://github.com/tskrlabs/hololive-ocg-wiki/issues/21).

Twelve decisions, in [ADR 0008](adr/0008-content-addressed-translations.md), which
supersedes ADR 0002's cache key. Execution tracked in
[#23](https://github.com/tskrlabs/hololive-ocg-wiki/issues/23); the design is in
[`translation-rework-plan.md`](./translation-rework-plan.md).

Cost: 1,493,321 tokens, ~356k points, **0 failures**. 204 API calls for a full cold run
against 14,778 under the old per-card scheme.

✅ **Published and seeded.** The seed ran 2026-07-30 (2,463 cards); production serves the
new translations. This section said "nothing is published or seeded" until 2026-08-02,
when it was checked against the live API and found stale — a reminder that a claim about
production is worth re-verifying rather than reading.

✅ **The tag filter is fixed in production**, verified 2026-08-02: `tag=0期生` returns 165
cards. `filter-options` had shipped `#`-prefixed values against a junction table holding
unprefixed ones, so **every tag returned zero cards, in every locale**
([#26](https://github.com/tskrlabs/hololive-ocg-wiki/issues/26)); the corrected artifact
reached production with the same publish.

### ✅ Thai `エール` normalised — published and seeded 2026-08-02

The game's cheer resource was rendered **four** ways in Thai rules text
([#28](https://github.com/tskrlabs/hololive-ocg-wiki/issues/28) reported three; the cache
had moved on). `holo-data normalise-cache` rewrites such cases deterministically, with no
API call — the model produced the inconsistency, so re-translating has no reason to fix
it.

| step | result |
|---|---|
| `normalise-cache --write` | 360 replacements across 263 entries, `th` only |
| `build` | 2,463 cards, 100% coverage in all seven locales |
| `publish --artifacts-only` | 9 objects (`cards.json`, 7 filter-options, `notices.json`); **0 images** |
| `seed --confirm` | 578 cards, **13,284 rows written — exactly the estimate** |
| live check | 100 `th` cards: 0 bad variants, `เยล` correct |

**D26 earned its keep here.** The seed reported `added 0, edited 0` for the official card
list beside 511 changed cards — so the diff said plainly "this churn is ours", which is
the distinction that column was added to make.

⚠️ **The near-miss is the part worth keeping.** #28's suggested one-line rewrite
(`เอล` → `เยล`) would have corrupted **Shirogane Noel**: `โนเอล` contains the variant, 9
times, and the glossary says `白銀ノエル` → `ชิโรกาเนะ โนเอล`. Verified in production
after the seed that she still renders correctly. Two other things the tests caught are in
[#28's thread](https://github.com/tskrlabs/hololive-ocg-wiki/issues/28) and in
`normalise.py` — including that "longest-first" is the *wrong* invariant for this table.

🔄 **Q&A masking is fixed in code but not yet in the data.** `batcher` masked strings
only, so Q&A units — dicts — reached the model unmasked, leaving **~5,900 Japanese card
names across six locales** in text where 99% of them had a curated glossary translation
waiting. The fix changes what is *sent*, so it takes effect only on a re-translation:
`translate-units --include-qa`, which is an API spend and a separate decision.

This file is the resume point for a new session. Read it, then
[`v2-plan.md`](./v2-plan.md) for the design, then the ADRs for decisions made during
execution. Progress is mirrored to GitHub issue
[#2](https://github.com/tskrlabs/hololive-ocg-wiki/issues/2); this file is the offline
copy and is authoritative if they disagree.

## Phases

| # | Phase | Status | Record |
|---|---|---|---|
| 0 | Repo skeleton + `packages/schema` | ✅ done | [ADR 0001](adr/0001-card-contract-generation.md) · `2d23999` |
| 1 | Pipeline migration | ✅ done | [ADR 0002](adr/0002-field-level-translation-cache.md) · `6be38ff` |
| 2 | CF resources + R2 publish | ✅ done | [ADR 0003](adr/0003-r2-publish.md) · live |
| 3 | D1 redesign + seeder | ✅ done | [ADR 0004](adr/0004-d1-schema-and-seeder.md) · live |
| 4 | Worker rewrite (Hono + Zod) | ✅ done — deploys with Phase 5 | [ADR 0005](adr/0005-worker-api.md) |
| 5 | Website (new API/R2, 4 refactors) | ✅ done | [ADR 0006](adr/0006-website.md) · live |
| 6 ✅ `49bb856` | Workers Builds + fixtures + docs | 🔎 **built — the dashboard step may already be done**, see the note at the top | [ADR 0007](adr/0007-push-to-deploy.md) |
| 7 ✅ `2a10d57` | Launch | ⬜ **unblocked, not taken** — the site is deployed but still `noindex` | |
| 8 | UI/UX rework | ✅ **done and live** — 16 commits + D26, deployed 2026-08-02 | [ADR 0009](adr/0009-ui-rework.md) · [#31](https://github.com/tskrlabs/hololive-ocg-wiki/issues/31) |

## Working agreement

- Work on **`develop`**, not `main`. Push is fine.
- **From Phase 6, a merge to `main` deploys the site.** `main` is the production branch
  for Workers Builds, so merging `develop` → `main` is the release action rather than a
  bookkeeping step. A failed build promotes nothing, so the live site is never at risk
  from a bad push — the failure mode is "no deploy", not "broken deploy".
- **Never use GitHub Actions** — the maintainer has had an account banned over Actions
  usage. Verification is local: `make check`, plus an opt-in pre-commit hook
  (`make hooks`). Workers Builds (Phase 6) is unaffected; it runs on Cloudflare and
  GitHub only sends a webhook.
- Free Cloudflare tiers only. A paid service is a decision, not an assumption.
- Each phase is grilled before it is built. The decisions in `v2-plan.md` §4 are settled;
  if implementing one shows it was wrong, say so and propose the change.
- **Surprises go to the issue tracker, not into a file.** Needs a maintainer judgement →
  a GitHub issue (`needs-triage`). Broke while fixing something else → an issue
  (`ready-for-agent`). Now *understood* → the code comment, test docstring, or ADR it
  explains. Anything unambiguously broken with an obvious fix still gets fixed on the
  spot. [`docs/archive/findings.md`](./archive/findings.md) is the closed phases-0–6
  record; 80 code comments cite its IDs, so it stays, but nothing is appended.

## Open questions

Tracked as **GitHub issues**, not in this repo. `gh issue list --state open` is the live
view; this table is the offline copy.

Triaged against launch on 2026-08-02. **Everything still open is post-launch** — nothing
below blocks the flip.

| # | what | label |
|---|---|---|
| [#28](https://github.com/tskrlabs/hololive-ocg-wiki/issues/28) | Re-translate the `legacy` Q&A corpus — the mechanical half is done | `ready-for-agent` |
| [#62](https://github.com/tskrlabs/hololive-ocg-wiki/issues/62) | `original.tags` is rendered nowhere, and the deck panel has no source names | `ready-for-human` |

✅ **#22 is closed** (2026-08-21) by
[ADR 0013](adr/0013-normalised-dual-colours.md), and **not** by fixing the icon.

`transform` now normalises `青赤` → `["blue", "red"]` and `白緑` → `["white", "green"]` at
extraction, which is the one place the source's two spellings of dual-colour differ. The
low-resolution asset becomes unnecessary rather than replaced, so #22's real question —
whether to ship our own redraw in place of official art — never has to be answered. Both
icons are deleted; the blur is now unrepresentable rather than fixed.

**It deleted more than it changed.** The query-time `expandColors`, the `FILTERABLE_COLORS`
exclusion list and F-016's matching machinery all existed to make a `blue` filter find a
`blue_red` card. A dual-colour card now holds one row per badge, so the plain filter hits
it. Verified against a real Worker and local D1: all three `blue_red` cards return under
both `blue` and `red`, SorAZ under both `white` and `green`.

**Eight pinning tests were inverted**, across four packages and both languages — every one
asserted a fused code stays fused. That is the expected shape of the change, and also
exactly where a test rewrite can hide a regression, so the replacements assert the new
property against the real card images and fixtures rather than restating the code. Two more
turned up only when `make check` ran: a TypeScript mirror of a Python test, and the web
contract test.

Three defects surfaced while building it, none by reading:

- **Cards 1 and 2 were coincidental fixtures.** Card 2 was selected only because it covered
  `color=green`, which SorAZ took over once it normalised — so the greedy pass dropped it,
  and with it the second `oshiCharacter`/`OSR` the group-AND smoke check needs to
  distinguish AND from OR. Pinning card 2 then displaced card 1, which a dozen smoke
  assertions name directly. Both are pinned now, with the reason recorded.
- **`computed` was a Nuxt auto-import** in `CardDataRowsBlock.vue` and undefined outside
  Nuxt. Caught by the new component test, which is the only thing that mounts it.
- **`:8787` was serving a stale Worker** from an earlier session, so the first round of
  API checks returned `internal error` against a database predating hBP08 entirely. Worth
  recording because the failure looked exactly like a code bug.

The one deliberate visual change: a dual-colour card renders **two full-size badges** where
it rendered one blurry composite, and keeps the name the game gives the pair — "Blue-Red",
not "Blue, Red". `COLOR_PAIRS` carries that, and the `colors.blue_red` i18n keys survive in
all seven locales although the codes do not.

⚠️ **Not yet live.** `color_code` is a populated D1 column, so this needs `publish` and
`seed` before the deploy — data first, per the card-set runbook.

✅ **#18 is closed** (2026-08-21) by
[ADR 0012](adr/0012-committed-translation-corrections.md) —
`pipeline/corrections/{locale}.json` is committed, and the cache folds it in on load and
holds it back on save, so a hand-written translation lives in exactly one place: the file
a contributor can diff.

The 2026-08-02 triage kept this open waiting for *"a real report of a badly worded effect"*
before designing against a hypothetical. **#78 was that report.** Two things that were
expensive in July had also become cheap: ADR 0008 re-keyed the cache on the source string,
so a correction is addressable without a card path, and verification turned out to need no
Poe key — folding a file into a dict is testable offline, which was the third of the three
worries named in the triage.

The four F-003 `tc` strings are **committed at last** — recovered in Phase 0, applied to
the cache in Phase 3, and deliberately kept out of git until there was a reviewable place
to put them. They are `corrections/tc.json`'s first entries.

Two bugs surfaced while building it, both caught by verification rather than by reading:
folding corrections into *any* cache load broke `backup.stats_for`, which verifies a
snapshot by loading it and would have reported a `manual` count including entries the
snapshot does not contain; and `holo-data corrections` returned early on "no corrections
recorded", making orphan `manual` entries silent in exactly the pre-migration state
`--extract` exists for. Both are pinned by tests.

✅ **#27 is closed** (2026-08-21) and **#28 is partly applied**, done as one pass in
`0c05e68` — 1,201 replacements, no API call.

**The bracket half was not cosmetic, and both the issue and its triage said it was.**
`ability_text` renders through `v-html`, so an ASCII `<Hakui Koyori>` is parsed as an
unknown tag and **dropped**: 54 character names were invisible on 24 live card pages, with
the rule reading "attached to 1st or higher" and then stopping. Verified against production
before and after. Two measurements settled the direction — the JA source writes `〈〉` 6,804
times and ASCII zero times, and every `<` in the cache already formed a closed pair — and
normalising the other way would have taken 54 swallowed names to roughly 1,600.

**The quoted-name half had an answer nobody looked up.** A card quoting another card's skill
name in `「…」` sat untranslated while the canonical value was one cache entry away. 855
exact-match substitutions; card-text kana-quotes 34 → 14.

**Three of the issues' claims were a year out of date**, which is the reason to re-measure
before planning rather than after: `normalise.py` already existed and had simply never been
run (27 Thai replacements pending); `en`'s quote defect was already 0, not 7; and the
bracket count was 306, not 166.

**`パソコン` — #27's open question, answered the other way.** The issue guessed that
translating it might be *wrong* because the rule matches a card-name substring. Measured:
the cards it matches are named `Gaming PC` / `電競電腦`, so leaving it Japanese made the rule
unfollowable — it told a reader to search for a string no card displays. Per-locale, so it
landed as 11 entries in `pipeline/corrections/` (the surface #18 delivered the same day),
across **two** source units rather than the one the issue implies.

**#28's glossary thesis is re-scoped by measurement, not adopted.** The kana leakage looks
large but ~95% of it is in the `legacy` Q&A corpus ADR 0008 deliberately left alone; card
text carries only **6 units** of untranslated game grammar across all six locales. That does
not justify a fourth glossary kind, which would mean widening `combined_table` and
`Restorer` (both hardcode two positional glossaries) plus seven call sites. #28 stays open
with its scope narrowed to what it really is: re-translate the legacy Q&A, an API spend
decision.

Also closed a blind spot found while checking safety: `manual` entries were excluded from
the completeness check as well as from rewriting, so a bad variant inside a committed
correction was invisible and `normalise-cache` still printed `✓`.

⚠️ **Not yet live** — this is a cache edit, so it needs `publish` and `seed`.

✅ **#20 and #21 are closed** by the translation rework — see
[ADR 0008](adr/0008-content-addressed-translations.md). ✅ **#26 is closed** (the tag
filter returned zero cards for every tag), fixed locally and awaiting a publish.

✅ **#16 is closed** — it was the only urgent one. `holo-data build` produces 2,463 cards
with zero failures again, so a card-set refresh is possible. See
[the pipeline section](#phase-1--the-pipeline) for the new `transform` command.

✅ **#19 is closed** — the `unknown` card-type valve now blocks like the other three
enums. Grilling it found two premises of the issue were false: `--allow-unknown-enums`
had **never worked** (`build` discarded the flag on a length check that is true exactly
when a card fails validation, untested since Phase 0), and no report could name the
offending value, because the sentinel replaces the site's string and throws it away. Both
were fixed first — the escape hatch now drops the bad cards and ships the rest, and
`holo-data transform` prints the source value — which is what made blocking cheap enough
to choose. See [the pipeline section](#phase-1--the-pipeline).

✅ **#29 is closed** by Phase 8 commit 2 (the grid has names to toggle now) and ✅ **#57 by
commit 12** — the reading pass found four real defects, not just stale copy. ✅ **#59 and
#60** closed with Phase 8 (dialog scroll position; the grid's ~40 tab stops).

### The pre-launch triage — six closed, 2026-08-02

✅ **#58** — `cardTypes.supportStaff` *and* `rarity.HR` were missing from all seven locales.
`contract.test.ts:105` now sweeps 4 generated enums × 7 locale files. The lesson is the
by-hand audit: it declared three enums complete and missed `rarity.HR`, the exact bug
ADR 0001 exists to catch, live in production in every language. The automated check found
what the careful human pass did not.

✅ **#61** — the show-original toggle had never rendered on the detail page or dialog:
`pathPrefix: false` registered the component as `OriginalText` while five call sites asked
for `CardListOriginalText`. Shipped broken from day one, because an unresolved component
is a console *warning*. Guarded twice now — a mounted test pinning the auto-import name,
and a `smoke.sh` sweep comparing every PascalCase tag against the generated registry. The
bundle-grep the issue proposed was tried and rejected with evidence: the minifier renames
`resolveComponent` to a per-chunk alias, matching 73 false positives against 1 real hit.

✅ **#65** — a literal `@` in a locale value blanks *every* key in that language, silently.
Now guarded in `smoke.sh`. **The fix as proposed did not work**: `generateJSON` does not
throw on a bad value — it reports through an `onError` callback and otherwise returns
normally, so the obvious try/catch implementation passes on the exact input it exists to
reject. Verified by injecting the real bug and watching it fail by name.

✅ **#17, #42, #64** — the launch-posture three, decided together in
[ADR 0011](adr/0011-launch-posture.md): cookieless GA4 with no banner, `robots.txt` ours
alone and allowing every crawler, `og:image` stays WebP.

Everything settled during phases 0–6 is in
[`docs/archive/findings.md`](./archive/findings.md), which is closed.

## What exists now

```
packages/schema/   the card contract — pydantic → JSON Schema → TS types → D1 DDL
packages/schema/sql/schema.sql       generated D1 schema (Phase 3)
packages/schema/sql/migrations/      evolving an already-populated database (Phase 4)
pipeline/          holo-data CLI: scrape … publish, seed
apps/api/          the Worker — Hono + Zod over D1 and R2 (Phase 4)
apps/web/          the site — Nuxt 4 SPA, generated static (Phase 5)
content/           info.json — editorial site copy, uploaded by publish
fixtures/          34 cards + fixtures.sql + artifacts/ — credential-free local dev (D12)
                   volume.sql — 620 bulk cards, so local dev reaches page 4 (#59)
docs/adr/          decisions made during execution
docs/infra.md      the Cloudflare runbook — what exists and which command made it
docs/archive/findings.md   data anomalies awaiting maintainer review
CONTRIBUTING.md    what needs credentials and what does not (Phase 6)
Makefile           `make check` — the single verification entry point
```

```bash
npm install    # enough for the site and the API — Node 24, no Python
make dev       # site on :3000 + Worker on :8787, fixtures, no credentials
make check-api # just the Worker: 25 unit tests + every endpoint check
make help

make setup     # uv sync + npm install — needed to work on the contract
make hooks     # opt-in pre-commit check (once per clone)
make check     # schema, pipeline, seeder, TS parity, Worker units + endpoints, typecheck
make check-site # builds the site twice and asserts what `nuxt generate` emitted (Phase 8)

uv sync --extra publish   # adds boto3, only needed for `holo-data publish`
```

## Phase 0 — the card contract

The card shape was written out in four places in v1 and had measurably drifted. It is now
defined **once**, as pydantic models; the JSON Schema, TypeScript types, enum arrays, and
(from Phase 3) the D1 DDL are generated from them.

Key decisions — full reasoning in [ADR 0001](adr/0001-card-contract-generation.md):

- Two shapes: `Card` (canonical, all 7 locales) and `LocalizedCard` (API, one locale),
  with `localize()` as the single projection between them
- `localize()` exists in Python **and** TypeScript, because the pipeline is Python (D3)
  while the Worker projects at request time (D8). Golden files pin them together; the TS
  test asserts byte identity across 34 cards × 7 locales
- Generated output is **committed**, so a frontend contributor needs no Python toolchain.
  `make check` fails if it is stale
- Closed enums, collect-and-report validation, `--allow-unknown-enums` escape hatch —
  which **had never worked** and was repaired by
  [#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19); it now drops the
  offending cards and ships the rest, and `publish`/`seed` refuse the short artifact
- snake_case everywhere
- Colours modelled **as-is** — the source's two encodings kept, not normalised. F-007 has
  since confirmed the cards are printed identically, so normalising is now open rather
  than ruled out; see [F-007](./archive/findings.md#f-007)
- Storage annotations (`Column`/`Blob`/`FullText`) recorded now, DDL emitted in Phase 3

Drift this removed: `HR` rarity missing from the TS union (24 cards unfilterable in the
live UI), `unknown` card type missing, `oshi_skill.cost` declared in three files but never
present in data, `special_values` typed `string[]` when it is `number[]`, and
`CARD_BLOOM_LEVELS` using `1st`/`2nd` against the data's `first`/`second`.

The `unknown` card type has **since been removed from the contract**
([#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)) — not a reversal of the
drift fix, but a stronger answer to it: an unclassifiable card now stops the build rather
than shipping with a name for its own unclassifiability.

## Phase 1 — the pipeline

v1's 9 numbered scripts are now a `pipeline/` module with one `holo-data` CLI.

```
holo-data scrape / transform / images / translate / build / verify / status  ← working
holo-data publish / verify-images / migrate-images                 ← Phase 2
holo-data seed                                                     ← Phase 3 stub
```

**`transform` re-runs `cards_structured.json` → `cards_i18n.json` without re-scraping**
([#16](https://github.com/tskrlabs/hololive-ocg-wiki/issues/16)). `scrape` always ran the
transform as its final step, so before this the only supported repair after a contract
change was re-fetching 2,464 pages from a small operator's site. That is not
hypothetical — dropping `cost_count` from the contract left a stale `cards_i18n.json`
that failed `build` on 1,991 arts, against scraped data that was perfectly fine.

### What happens when the site prints something new (#19)

The three commands now answer this together, which is
[#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)'s whole subject. Before
it, an unrecognised **card type** was absorbed: the card validated, shipped, was excluded
from every deck section, and nothing counted or printed it. The other three enums blocked.

```
holo-data transform   ⚠ 1 card(s) carry a value no mapping covers:
                          card_type   サポート・新種別
                                        1 card(s): 2480
holo-data build       ✗ build failed — nothing written
                        (add the mapping, or:)
holo-data build --allow-unknown-enums
                      ✓ wrote cards.json — 2462 cards, 1 dropped
                      ⚠ publish and seed will refuse it
```

Three things had to be true for blocking to be the right answer, and only one was:

- **`--allow-unknown-enums` had never worked.** `build()` honoured the flag and then
  discarded the result on a length check true exactly when a card fails validation. It
  had no test, and F-008 had reasoned that blocking was cheap *because this existed*.
- **Nothing could name the offending value.** The sentinel replaces what the site printed
  and discards it, so `build` reports the values we accept — never `サポート・新種別`.
- The absorption itself was deliberate, and stayed deliberate; what was missing was the
  census.

So the fix runs in that order: repair the hatch, make `transform` name the value, then
narrow the enum. A dropped card is recorded in `cards.json` and refused by both `publish`
and `seed` with no override flag — the escape hatch unblocks `build` alone and never
reaches the site (D4: gates are facts, not ceremony).

Key decisions — full reasoning in
[ADR 0002](adr/0002-field-level-translation-cache.md):

- **Parsing moved verbatim.** The BeautifulSoup selectors and HTTP/retry logic are
  character-for-character from v1 (D3). Everything around them was rewritten
- **Field-level translation caching** replaces v1's whole-card `_source_hash`. Measured
  across v1's dated snapshots, a card's printed text does not change once published —
  Q&A is the only real churn — so v1 re-translated ~50× more than needed
- **Manual corrections are cache entries** marked `source: "manual"`, superseding D14's
  overlay. The whole card still goes to the model; only *stale* fields are read back, so
  a correction survives even when the card is re-sent
- `holo-data images` — PNG → WebP at q90. Measured over the real set in Phase 2:
  **191 MB**, 68% smaller than the PNGs and well under the 425 MB the sample predicted.
  New: nothing in v1 produced WebP
- `holo-data verify` is permanent, with a `--baseline` path argument

**Verified:** `verify` reports zero base-field differences against v1's 2,448-card
published data. With the cache seeded from v1 (`python -m holo_data.import_v1`, 81,124
entries), `translate --dry-run` reports **2,228 of 2,448 cards already current**.

Three bugs were caught by diffing against real data, all in the rewritten plumbing: the
特攻 icon also appearing in `cost_icons` (482 cards got `unknown` cost types), a keyword's
type being its icon's `alt` rather than its `name` (1,124 cards lost their keyword), and
the 特攻 alt being `紫+50` rather than `紫` (every special art lost its targets). None
would have been visible without a known-good baseline.

## Amendments to `v2-plan.md`

Recorded in the ADRs; listed here so they are not missed.

| Decision | Change |
|---|---|
| **D5** | "pydantic → JSON Schema → TS types **+ SQL**" — SQL moves to Phase 3, where the D1 schema is actually designed |
| **D11** | `status.json` moves from `publish` to the **seeder (Phase 3)**. It is written by v1's `migrate.js`, not the pipeline, and describes a *database diff* — knowledge `publish` cannot have |
| **D14** | The `corrections/` overlay is superseded by field-level caching. Same goal, no separate merge layer. Scripts 7/8 dropped (never used) |
| **Phase 1 done-when** | "reproduces today's `cards.json` **shape**" → reproduces today's **data**. The artifact is snake_case now, so a byte-diff would show every key renamed |
| **Phase 1 image tree** | Flat `images/{png,webp}/` → **set-scoped** `images/{png,webp}/{set}/`. Amended in Phase 2: the flat layout could not hold F-006's two same-named-different-artwork reprints, which is a data-loss bug, not a layout preference ([ADR 0003](adr/0003-r2-publish.md)) |
| **D11** | `info.json` is **committed** at `content/info.json` and uploaded by `publish`, not pushed by hand. The card count comes out of its prose and is rendered from `cards.json` instead — a Phase 5 dependency |
| **D8** | "filterable fields stay real indexed columns" → the three **multi-valued** ones become **junction tables**. A JSON array filtered with `LIKE` cannot use an index, so v1's three such indexes never fired. Measured on the real query shape: ~2,448 rows read vs ~50–100 ([ADR 0004](adr/0004-d1-schema-and-seeder.md)) |
| **D8** | `/api/filter-options` and `/api/static-filters` move **off D1** to R2 artifacts — same answer for every user until the next reseed, currently four full scans per call |
| **Plan §3** | D1 free storage is **500 MB**, not 5 GB — the plan quoted the paid tier. Not a problem: 17 MB data + 36 MB index |
| **Phase 3 done-when** | "`seed --dry` reports ~2,500 rows" → **~47,300 writes for a full reseed, ~2,320 for a new set**. The original counted only `cards` rows, ignoring index writes, junction rows and FTS shadow tables |
| **D8** | `color_codes` and `card_sets` are **also in `payload`**, not only in their junction tables. `localize()` reads both, so without them the Worker could not rebuild a card from the row it just selected. Junction = how a card is found, payload = what it is (+3.2%, [ADR 0005](adr/0005-worker-api.md)) |
| **D8** | New indexed **`name_ja`** column. The `name` filter needs an index and the name lives inside a JSON payload no index can reach. `CARD_INDEX_COUNT` 4 → 5, so a full reseed is **~49,785 writes** |
| **D8** | `/api/static-filters` is **deleted**, not moved to R2. It returned enum values the contract already owns, and v1's frontend never called it — it read a hand-maintained constants file that had drifted |
| **Phase 4 done-when** | "All 8 endpoints; SPA + API from one Worker" → **7 endpoints, API only**. `apps/web` does not exist until Phase 5, so there are no assets to bind; the `assets` block, SPA fallback and apex domain move there |
| **Phase 3 schema** | `schema.sql` is `CREATE TABLE IF NOT EXISTS`, so it **cannot evolve a populated database** — re-applying it silently skips a new column, then fails on the index using it. `packages/schema/sql/migrations/` added |
| **Phase 4** | Seven endpoints → **nine**. `/api/info` and `/api/status` were never built, so `info.json` (uploaded since Phase 2) and `status.json` (since Phase 3) sat in a private bucket **with no reader at all** ([ADR 0006](adr/0006-website.md)) |
| **D11** | `content/README.md` claimed the card count comes from `cards.json` "which the site already loads" — **the site never loads it** (21 MB; D8 moved querying to D1). It comes from `/api/status`, which already carries `counts.total` and `generated_at` |
| **D11** | The edit-without-redeploy premise is **weaker than when written**: `info.json` has been *committed* since Phase 2, so editing it is already edit → commit → publish, and Workers Builds will auto-deploy that commit anyway. R2 retained for consistency with `status.json`, which has no committed copy |
| **D13** | "four refactors + dead-code purge" is joined by a **framework upgrade**, Nuxt 3.17 → 4.5. Still no new features, no redesign, no rendering-mode change |
| **Phase 5 status page** | v2's `status.json` dropped `skipped[]` and `source.valid` and is snake_case throughout, so `/status` **cannot be ported unchanged**. Ported adapted; the Skipped tab has no data source in v2 and is dropped |
| **v2-plan §7** | The SEO decision stays deferred — which means Phase 5 must **actively block indexing** to keep it deferrable |
| **Phase 6 done-when** | "fresh clone runs with zero CF creds" was already true and **still failed the intent**: `make dev` needed a *Python toolchain* to generate the R2 artifacts. Met by **committing** them (`fixtures/artifacts/`, 64 KB), extending ADR 0001's rule from the contract to the fixtures ([ADR 0007](adr/0007-push-to-deploy.md)) |
| **D14** | "a `corrections/` overlay makes a translation fix a reviewable PR" — ADR 0002 replaced the mechanism with cache entries but the cache is **gitignored**, so no reviewable surface exists. A fix goes through an issue. Logged as [F-018](./archive/findings.md#f-018), not closed |
| **Phase 0 contract** | `TranslatedArt.value` is **dropped**. v2 has no path that writes it — a stray key on 4 `tc` arts in v1's data, caused by the translation prompt's own 「只翻譯 value」 wording. `localize()` never emitted it, so the golden files are byte-identical across the removal ([F-003](./archive/findings.md#f-003)) |
| **Fixture corpus** | ~~`fixtures/cards.json` is generated but **both its generators fail today**~~ — **fixed**, [#16](https://github.com/tskrlabs/hololive-ocg-wiki/issues/16). F-002 dropped `cost_count` and hand-edited the corpus rather than regenerating, leaving `make fixtures` broken on 1,715 cards and `holo-data build` on 1,991 arts, with `make check` running neither. New `holo-data transform` repairs derived data without re-scraping; the corpus now selects from `holo-data build` output; `v1_adapter.py` is deleted |
| **Phase 1 pipeline** | `scrape → images → translate → build` gains a **`transform`** rung. `scrape` always ran the transform as its last step, so the only supported repair after a contract change was re-fetching 2,464 pages from a small operator's site ([#16](https://github.com/tskrlabs/hololive-ocg-wiki/issues/16)) |
| **Fixture corpus** | Merge rule 2 (arts pair by index, tolerating a short list) is covered by a **synthetic fixture**, card `9000001`. F-004 warned repointing the generator would lose the coverage; the census found it worse — **zero** of 2,463 cards have an arts-length mismatch in any locale, so no real card can cover a rule that still runs in production in two languages |
| **Phase 0 contract** | `"unknown"` is **no longer a `card_type_code`** ([#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)). ADR 0001 modelled it as legitimate so the build would not fail on cards we already ship; it was the pipeline's fallback in four enums but a member of only this one, so an unmapped value blocked the build in three fields and shipped silently in the fourth — into no deck section, counted by nothing. All four now behave identically |
| **ADR 0001 §4** | `--allow-unknown-enums` **had never worked** — `build()` honoured the flag then discarded the result on a `len(validated) != len(cards)` check that is true exactly when a card fails validation, untested since Phase 0. Its documented promise ("publishes anyway") was also unimplementable against closed `Literal`s: such a card cannot be constructed. It now **drops** those cards, records their ids in `CardCollection.dropped`, and `publish`/`seed` refuse a non-empty list with no override ([#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)) |
| **Phase 1 pipeline** | `transform` now reports the **source values no mapping covers**. The sentinel discards what the site printed, so every downstream error could name only the values we accept — an operator got `Input should be 'debut', 'first', 'second' or 'spot'` and a card id, never `超進化`. Two lookups that *omit* rather than substitute (skill timing, keyword type) are reported too: they fail nothing, so the card ships with no timing badge or no keyword at all ([#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)) |

## Phase 8 — the UI/UX rework

Full reasoning in [ADR 0009](adr/0009-ui-rework.md); the map that produced it is
[#31](https://github.com/tskrlabs/hololive-ocg-wiki/issues/31), whose fifteen closed
tickets hold every measurement.

**This phase blocks Phase 7.** Launch is a one-time SEO event and card pages are the part
that cannot be retrofitted: 2,463 URLs either exist when Google first crawls us or the
opportunity is spent.

Phase 5's D13 fenced the website work to refactors, so v2's *inside* is new and its
**outside is still v1's** — stock shadcn slate, an art-only grid, a screen-covering filter
sheet, and **no URL for a card at all**.

### ✅ Prerequisites — all six done

Landed on `develop` as `61b2793..77720d0`, one commit each, **each green under
`make check` checked out in isolation** — verified in a scratch worktree, not only
cumulatively.

| # | issue | commit | what changed |
|---|---|---|---|
| P1 | [#40](https://github.com/tskrlabs/hololive-ocg-wiki/issues/40) `EXISTS` rewrite | `2998a8d` | filtered queries read 4–8× more rows than needed; **66% → 15%** of the read tier |
| P2 | [#43](https://github.com/tskrlabs/hololive-ocg-wiki/issues/43) grid ladder | `4972b82` | widening the window shrank the cards; columns now derive from a target tile width |
| P3 | [#44](https://github.com/tskrlabs/hololive-ocg-wiki/issues/44) `100dvh` scroller | `078b126` | hid 138px of the list; **this is D12, so commit 3 of the sequence is already done** |
| P4 | [#45](https://github.com/tskrlabs/hololive-ocg-wiki/issues/45) offline lies | `b2de00c` | "No cards found" on a network error |
| P5 | [#49](https://github.com/tskrlabs/hololive-ocg-wiki/issues/49) silent partial add | `51628c8` | `CardItem` discarded `addCardToDeck`'s return |
| P6 | [#51](https://github.com/tskrlabs/hololive-ocg-wiki/issues/51) unnamed buttons | `77720d0` | 4 of 8 header controls had no accessible name |

The four UI fixes were verified **in Chromium**, not only by unit test. Three of the six
are precisely the class of bug pure-function tests cannot see, which is F-019's lesson;
the browser was the check that mattered.

#### What the prerequisites changed for the rework

Three findings that alter commits already in the sequence below:

- **`<Toaster />` was never mounted.** A `TODO(commit 3)` in `app.vue` outlived the Phase 5
  commit it named, so **22 `toast.*` call sites across 8 components** had been silent since
  the scaffold. #49's stated fix assumed vue-sonner worked "because it is used elsewhere" —
  the *calls* existed, the renderer did not. Restoring it made twenty never-seen messages
  live at once; [#57](https://github.com/tskrlabs/hololive-ocg-wiki/issues/57) tracks the
  reading pass, and **commit 12 is where it belongs**.
- **D11's `Math.round` does not hold its own band** — it peaks at a 284px tile. `floor`
  plus a 150–240px clamp reproduces #43's measured table exactly, and is what shipped.
  Commit 4 recomputes this for the 280px rail, so note the property to preserve: *strict*
  tile monotonicity is unachievable for any integer-column grid, because crossing into
  another column always shrinks the tile. What must hold is the **envelope** — the smallest
  tile each column count produces must not fall as columns are added. The old ladder broke
  that three times. (D13 is satisfied as-is: 2 columns at every width from 320–430px, a
  180px tile at 375px against D13's measured 170px.)
- **P3 changed the scroll contract for every page.** The shell no longer scrolls as a
  document, so each page owns its scroll region and must mark it `min-h-0 overflow-y-auto`.
  `min-h-0` is load-bearing — a flex child's default `min-height: auto` refuses to shrink
  below its content and would push the footer off-screen, restoring the bug elsewhere.
  Commits 3, 4 and 12 all touch this shell.

Three more were ruled on by the maintainer and **closed as `wontfix`** — none blocks:

| issue | ruling |
|---|---|
| [#50](https://github.com/tskrlabs/hololive-ocg-wiki/issues/50) no per-card copy limit | **keep as-is** — this is a wiki and a deck sketchpad, not a legality validator; a wrong rule would reject legal decks |
| [#41](https://github.com/tskrlabs/hololive-ocg-wiki/issues/41) site-wide soft 404s | **skipped on cost** — Worker-first on every navigation makes each page view a billable invocation. Card URLs are still covered: D7 extends `run_worker_first` to `/*/card/*` only, so the URLs in the sitemap return real 404s |
| [#56](https://github.com/tskrlabs/hololive-ocg-wiki/issues/56) English-only disclaimer | **accepted** — it quotes Cover's English-language guidelines; D19 already scoped the dialog to restyle only |

### ✅ The commit sequence is done

All sixteen landed on `develop` as `95c75fc..441c885`, one commit each, `make check` green
after every one. **Deployed 2026-08-02** with D26 — see
[the deploy record](#-phase-8--d26-deployed-2026-08-02).

Each row is independently green under `make check`.

| # | commit | why here |
|---|---|---|
| 1 ✅ `4942d3a` | tokens — variant D into `tailwind.css`, `--border-strong`, type + spacing scale, `fonts:` block, reduced-motion | everything downstream refers to these |
| 2 ✅ `6c24fdd` | `useCardDensity` + tile: art + name + card number, density persisted | closes [#29](https://github.com/tskrlabs/hololive-ocg-wiki/issues/29); needs 1 |
| ~~3~~ | ~~flex-column shell; header/footer stop being sticky; drop `pb-[65vh]`, un-float the summary~~ | ✅ **done in `078b126`** — this row *is* D12, and P3 could not fix #44 without doing all of it |
| 4 ✅ `fdbbf90` | the filter rail from `lg`; search + count move in; per-group pending markers | needs 1, ~~3~~ |
| 5 ✅ `06b500a` | query state as a discriminated union; skeletons; error + empty states; `SimpleImage` placeholder | needs 1; **P4 landed the error/empty split** (`b2de00c`) — the union itself is still this commit's job |
| 6 ✅ `49bb856` | migration: unique index on `image_key` | before anything reads by key |
| 7 ✅ `2a10d57` | `GET /api/cards/by-key/:set/:stem` + `cardMetaTags()` + its golden test | needs 6 |
| 8 ✅ `8d8f123` | extract `CardDetail`; dialog becomes a thin wrapper | no behaviour change |
| 9 ✅ `1766f7a` | the card route + dialog pushes/pops history | needs 7, 8 |
| 10 ✅ `0539b0b` | `HTMLRewriter` head injection; `run_worker_first` extended to `/*/card/*`; real 404s | needs 7, 9 |
| 11 ✅ `850af0c` | sitemap from a committed `card-urls.json`; pipeline emits it; `canonicalLowercase: false` | 2,465 URLs × 7 locales. `canonicalLowercase` was **not** the live bug #33 predicted — `app.vue` already outranked it |
| 12 ✅ `eceb35b` | deck drawer; editing mode; delete `DeckDetailCompactModeCardList` | closes [#57](https://github.com/tskrlabs/hololive-ocg-wiki/issues/57) — the reading pass found **four real defects**, not just stale copy. The compact list was already dead code |
| 13 ✅ `5d6e394` | header overflow menu, `.sr-only` labels, scroller focus, `alt` text | labels landed in P6 (`77720d0`), `alt` text in commit 5; this was the menu + **two focus-loss bugs**, both reproduced in Chromium. #48 §6's roving tabindex is deferred to [#60](https://github.com/tskrlabs/hololive-ocg-wiki/issues/60) |
| 14 ✅ `53496d2` | `/status` narrowed; delete the three status components | needs 1, 2 |
| 15 ✅ `3c6e73d` | `apps/web/tests/smoke.sh` + `make check-site` | 39 checks over two builds; verified by sabotage, which corrected two of them |
| 16 ✅ `441c885` | delete `app/components/prototype/` and its route | the design has landed for real |

### ✅ Done when — all four met

Verified 2026-08-01, on `develop`:

| clause | result |
|---|---|
| `make check` green | ✅ 366 Python, 21 schema TS, 29 Worker unit, every endpoint check, 148 web tests |
| `make check-site` green | ✅ **new target** — 39 checks over the generated site |
| a card resolves with injected metadata | ✅ `/tc/card/hSD01/hSD01-001_OSR` — title, canonical, `og:image`, `hreflang` in the served bytes |
| a real 404 for a bad key | ✅ `/tc/card/hSD01/NOPE` → **404**, and the good key → 200 |
| the sitemap lists card URLs | ✅ 2,465 per locale × 7, 1.8 MB total |
| the prototype is gone | ✅ deleted; no file emitted, and the route renders the app's 404 |

**Phase 7 is unblocked**, and Phase 8 is deployed — see the record below.

### ✅ Phase 8 + D26 — deployed 2026-08-02

Version `82c4ad6b` on `hololive-ocg-wiki-tskrlabs-com`, 390 assets (52 unchanged),
644 KiB / 104 KiB gzipped, 20 ms startup. **The site is still `noindex`**: this shipped the
rebuild behind the pre-launch guard, not the launch.

**Order was forced, and it is not the obvious one.** The migrations went first. Deploying
the Worker before `0002` would have made every card page a 2,463-row scan — and card pages
are billable invocations with 17,241 sitemap URLs aimed at them, against the read tier this
site has already breached once (F-014).

| step | result |
|---|---|
| `0002` unique index | 2,464 rows written — which is also proof no duplicate `image_key` existed |
| `0003` source_hash | applied; column present |
| `seed --confirm` | **0 cards rewritten**, 2,463 pure backfills. Estimate 2,463, actual 2,463 |
| baseline check | 0 rows left with a NULL `source_hash`; a second `--dry` reports "already up to date" |
| `EXPLAIN QUERY PLAN` on a card lookup | `SEARCH cards USING INDEX idx_cards_image_key` |

The seed is the first real exercise of D26's backfill path, and it behaved as designed:
`unchanged 2463` with a separate backfill line, and the source report reading 0/0/0 under
the honest note that no baseline existed yet. The run after it drops that note.

**Verified against the real 2,463 cards** — every Phase 3/4 number came back exactly:

| check | expected | actual |
|---|---|---|
| `フブキ` search | 73 | **73** |
| `name=白上フブキ&locale=en` | 44 | **44** |
| `filter-options.names` | 296 | **296** |
| `status.counts.total` | 2,463 | **2,463** |
| `info.contents` | 3 | **3** |
| `a AND` (FTS5 syntax error) | 200 | **200** |
| 51-id batch / 50-id batch | 400 / 50 cards | **400 / 50** |
| `tag=0期生` (#26) | non-zero | **165** |
| `colors=blue` includes fused | ~329 | **331** (the set grew 2,448 → 2,463) |

And the four things that were **broken before this deploy**, because production was still
running Phase 5's Worker:

| check | before | after |
|---|---|---|
| `/api/cards/by-key/hSD01/hSD01-001_OSR` | 404 | **200** |
| a bad card key (`/tc/card/hSD01/NOPE`) | 200 | **404** |
| injected `og:title` on a card page | absent | **present in the served bytes** |
| `/api/status` source vocabulary | absent | **present**, artifact 329 KB → **644 bytes** |

The pre-launch guard is intact: `noindex` present on `/tc/`, `robots.txt` disallowing, and
`NUXT_PUBLIC_LAUNCHED` unset at build time.

#### Re-verified after #63 merged (version `6922d991`)

The merge produced a *second* version, so everything above was checked again against it —
a build nobody on this side ran is a build whose environment nobody on this side chose.

| | |
|---|---|
| core API | `フブキ` 73 · `白上フブキ` 44 · names 296 · total 2,463 · info 3 · `tag=0期生` 165 |
| card identity | `by-key` 200 · card URL 200 · **bad key 404** · `og:title` injected |
| D26 artifact | source vocabulary present · `list_cap` 100 · **644 bytes** |
| pages | `/tc/` · `/tc/status` · SPA fallback · sitemap index — all 200 |
| **`noindex`** | **present on `/tc/` *and* on a card page**; `robots.txt` still disallowing |

`noindex` was the one worth checking hardest: a Workers Builds run does not inherit the
local environment, so `NUXT_PUBLIC_LAUNCHED` being unset here guarantees nothing about
what a remote build sets. It came back correct.

**The strongest evidence is a checksum, not a status code.** `_nuxt/DlbQCJnW.js` — the
chunk holding D26's copy — is **sha256-identical** to the locally built, `make check`-green
artifact, and the deployed copy contains the new strings (`最近一次更新`, `官方卡表新增`).
The page HTML cannot show this directly: the site is `ssr: false`, so `/tc/status` serves a
shell and the copy lives in the chunk.

Driving D26's own selection logic against the live artifact yields `status.reseed.none` and
`status.source.quiet` — correct, because the last seed was a pure backfill that rewrote no
cards while the official list published nothing. The `reseed.ours` branch (rows churned,
source silent) fires on the next real reseed; it is covered by the mounted tests.

### What the rework found

Nine pre-existing bugs were found *specifying* it (ADR 0009); building it found more, all
of the same class — wiring and composition, invisible to pure-function tests, which is
F-019's lesson holding for a second phase:

- the site's `<Toaster />` was never mounted, so **22 toast calls across 8 components** had
  been silent since Phase 5 ([#57](https://github.com/tskrlabs/hololive-ocg-wiki/issues/57),
  closed) — and reading them found a clipboard check running *after* the copy, an
  undismissable error toast, and one guard written five times
- **keyboard focus was lost to `<body>` twice** — once when `RecycleScroller` recycled the
  focused tile, once when closing a card dialog (Reka blurs the element it restored to,
  during unmount). Both reproduced in Chromium first
- **status, GitHub and Discord were desktop-only** — `hidden sm:inline-flex` meant a phone
  silently lost all three
- `canonicalLowercase` was **not** the live bug #33 predicted: `app.vue`'s own canonical
  already outranked it. Turned off anyway, as a latent one
- two i18n gaps ([#58](https://github.com/tskrlabs/hololive-ocg-wiki/issues/58)), now
  guarded by a coverage test over 4 enums × 7 locales *and* every new UI string

Two follow-ups are open and neither blocks launch:
[#59](https://github.com/tskrlabs/hololive-ocg-wiki/issues/59) (closing a card dialog loses
the grid's scroll position — a routing restructure) and
[#60](https://github.com/tskrlabs/hololive-ocg-wiki/issues/60) (the card grid is ~40 tab
stops; #48 §6's roving tabindex).

## Phase 2 — R2 publish

Full reasoning in [ADR 0003](adr/0003-r2-publish.md); the Cloudflare runbook is
[`infra.md`](./infra.md).

```
holo-data publish          images + artifacts → R2   (--dry-run, --force)
holo-data verify-images    coverage; --remote re-checks bytes against the source
holo-data migrate-images   one-time: v1's flat images → the set-scoped tree
```

- **Two buckets.** `hololive-ocg-wiki-images` is public behind
  `img.hololive-ocg-wiki.tskrlabs.com`; `hololive-ocg-wiki-artifacts` is private. The
  images bucket is world-readable forever by design — artifacts have a different
  lifecycle and stay out of it
- **The local image tree is now set-scoped** — `images/{png,webp}/{set}/{stem}.ext`,
  mirroring `image_key`, so `publish` is a directory sync with no lookup. This is a
  **Phase 1 amendment**, and it is a bug fix: see F-006 below
- **`publish` diffs by listing R2** (size, then MD5/ETag), never deletes, and has
  **no `--confirm`**. Instead it refuses on a *stale* `cards.json` or an incomplete image
  set — gates an agent cannot satisfy by adding a flag
- **Custom domain from the start, `r2.dev` disabled.** `r2.dev` is rate-limited and gets
  no CDN cache at all; the custom domain is what keeps R2 reads near zero
- **Cache headers set explicitly at upload** — images `immutable` for a year, artifacts
  `no-cache` — rather than inherited from Cloudflare's default extension list
- **`boto3` is an optional extra** (`uv sync --extra publish`). 27 MB, and only the
  maintainer can publish anyway (D14)
- **`info.json` is committed editorial copy** at `content/info.json`, carrying no facts
  about the data. v1's hardcoded *"2448 cards (June 19, 2026)"* is gone — Phase 5 renders
  that from `cards.json`'s `generated_at`

**F-006 resolved, and it was a live bug.** The two `hCO01` reprints were fetched and
hashed: `hBP03-044_SR` and `hBP03-055_SR` are **different artwork by different
illustrators** in `hBP03` and `hCO01`, not duplicate files. v1's flat image directory
skipped any filename already on disk, so only one of each pair was ever downloaded and
both cards rendered the same art. The set-scoped tree is what fixes it — the image key
alone does not, since two keys can still point at one flat file.

### Phase 2 execution

The code is built and `make check` is green, but **the Cloudflare resources do not exist
yet** and the maintainer creates them. Until then `publish` fails with instructions.

Commands are `uv run holo-data …` — the CLI lives in the project venv, not on your PATH.

**✅ Phase 2 is complete and live.** Executed 2026-07-27:

| | result |
|---|---|
| Buckets | both created, `r2.dev` disabled on each |
| Custom domain | `img.hololive-ocg-wiki.tskrlabs.com` → CDN `HIT`, `immutable` cache header |
| Images migrated | 2,448 PNG across 34 set folders (603 MB) |
| WebP converted | 2,448 (191 MB — **68% smaller**, and well under the 425 MB estimate) |
| `build` | 2,448 cards, 100% translation coverage in all 7 locales, 21.3 MB |
| `verify` vs v1 | only the 2 known F-001 cards + the F-003/F-004 arts — **zero unexplained drift** |
| `verify-images --remote` | **2,448/2,448 byte-identical to source** (after F-012) |
| `publish` | 2,450 objects; a second run uploads nothing |

R2 usage: images 191.4 MB, artifacts 21.4 MB — **2% of the 10 GB free tier.**

**F-012 found during this run.** The first provenance check reported 12 images differing
from source — not wrong cards, but stale copies: the official site had silently
re-uploaded 7 at higher resolution and re-compressed 5. `download_image()` skips files
already on disk, so a *replaced* upstream file is never noticed. Re-fetched and clean.
This is why `verify-images --remote` exists, and worth re-running after each new set.

### Working data lives in the main checkout

`pipeline/data/`, `locales/`, `images/` and `build/` are gitignored, and they were
populated in the **main checkout** (`/Users/chingli/tskrlabs/projects/hololive-ocg-wiki`)
rather than in a worktree, so they survive this branch being merged. A worktree run needs:

```bash
MAIN=/Users/chingli/tskrlabs/projects/hololive-ocg-wiki/pipeline
export HOLO_DATA_DIR=$MAIN/data HOLO_LOCALES_DIR=$MAIN/locales \
       HOLO_IMAGES_DIR=$MAIN/images HOLO_BUILD_DIR=$MAIN/build
```

The translation cache is seeded (81,124 entries from v1), so `translate` has nothing to
do until new cards ship.

Done when images resolve at `img.hololive-ocg-wiki.tskrlabs.com/{set}/{stem}.webp` and a
second `publish` uploads nothing.

## Phase 3 — D1 redesign + seeder

Full reasoning and the measurements behind every choice in
[ADR 0004](adr/0004-d1-schema-and-seeder.md).

```
holo-data seed --dry        row counts + write estimate   (reads only)
holo-data seed --confirm    diff-based upsert into D1     (writes)
holo-data seed --full       rewrite everything            (gated separately)
holo-data seed --prune      delete cards missing from the build
```

**The measurements changed the design.** Reading v1's live D1 analytics turned up that
**reads, not writes, are the binding constraint** — the site scans 882 rows per query on
a 2,448-row table and **breached the 5M/day free tier on 2026-07-12** (F-014). D8
optimised the row count, which is the resource with slack.

More sharply: the JSON-payload design *on its own* would have made the live problem
worse. With `color_codes` as a JSON column, a filtered and sorted page is a full 2,448-row
scan — worse than v1's 882 — because `ORDER BY` evaluates every match before `LIMIT`
applies. The junction tables are what make the payload design pay off.

| design | rows read per 50-card filtered page |
|---|---|
| v1 today | ~882 (measured in production) |
| payload + JSON colour | ~2,448 — **worse** |
| payload + junction colour | **~50–100** |

- **Junction tables** for `color_codes`, `tags`, `card_sets` — `WITHOUT ROWID`, value
  leading the PK, so the key is the storage and a filter is a covering-index range scan
- **`payload` / `qa_payload` split.** Q&A is 53% of the translation bytes and the only
  part that churns after a card is printed (ADR 0002). List endpoints never read it
- **FTS5 `tokenize='trigram'`**, one row per card, all 7 locales concatenated. This
  **fixes a live search bug** — F-013: `白上フブキ` returns 62 cards on v1 but `フブキ`
  returns **zero**, because `unicode61` treats an unbroken CJK run as one token. Verified
  on the real set: `フブキ` now returns 73
- **The diff baseline is D1 itself** — `content_hash`/`qa_hash` columns rather than v1's
  committed 648 KB hash file, which can disagree with the database. An interrupted run
  resumes with no reconciliation
- **Writes go through the D1 REST API** from Python, fully parameterised. D1 batches are
  **transactional** (verified), so one batch per card means a card is never half-written
- **`seed` reads today's actual write usage** from analytics and refuses if the estimate
  will not fit — not the flat 100k, which is blind to a seed that already ran
- **Deleting needs `--prune`**, plus a hard refusal if the card count drops >10%
- **`schema.sql` is generated** from the same pydantic models, via a new `Junction`
  annotation. Applied with `wrangler`, never by `seed`

**Write accounting** (replaces the plan's "~2,500 rows"):

| scenario | writes | % of 100k/day |
|---|---|---|
| Full reseed | ~47,300 | 47.3% |
| New card set (~120 cards) | ~2,320 | 2.3% |
| Q&A-only update (100 cards) | ~700 | 0.7% |

Every constant behind these was measured against production, not estimated.

### Phase 3 execution

**✅ Phase 3 is complete and live.** Executed 2026-07-27 against
`hololive-ocg-wiki-db` (`75238170-4525-4a06-bfd3-5a32c4daef57`):

| | result |
|---|---|
| Schema applied | 4 tables + FTS virtual table, 7 indexes |
| `seed --confirm` | 2,448 cards, 27,203 rows written, 327 batches, 81s |
| Row counts | cards 2,448 · colors 2,032 · tags 5,443 · sets 2,592 · fts 2,448 |
| CJK search | `フブキ` **73 hits** (v1 returns 0), `宝鐘マリン` 45, `ときのそら` 52 |
| Second `seed --dry` | "D1 is already up to date — nothing to write" |
| Database size | 53.8 MB (11% of the 500 MB free tier) |

**The first seed found a bug no local test could have.** It wrote 27,203 rows but
**read 15,508,419** — three times the daily read budget — because the seeder's
`DELETE … WHERE card_id = ?` could not use the junction tables' `(value, card_id)` key
and skip-scanned each table per card. The read path and the write path want opposite
key orders. Adding a `card_id` index to each junction, and keying the FTS table on rowid
instead of an UNINDEXED column, took a full reseed from **15.5M rows read to ~22,850** —
a 679× reduction. SQLite does not report `rows_read`; D1 does, which is why only a real
run surfaced it. Both are now pinned by query-plan tests.

`seed` needs `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in `pipeline/.env` — a
**different token from the R2 one**, scoped to D1 Edit on this database plus Account
Analytics Read (the write-budget gate). See [`infra.md`](./infra.md).

~~One follow-up: `status.json` was written locally but not uploaded~~ — done in Phase 4.

### Local development needs no credentials (D12)

Run from `apps/api/`, where `wrangler.jsonc` declares the bindings. Note the database is
`hololive-ocg-wiki-db`; `hololive-ocg-wiki` is the *Worker's* name and does not resolve —
the command printed here before Phase 4 was wrong.

```bash
cd apps/api
npx wrangler d1 execute hololive-ocg-wiki-db --local \
    --file=../../packages/schema/sql/schema.sql
npx wrangler d1 execute hololive-ocg-wiki-db --local --file=../../fixtures/fixtures.sql
npx wrangler d1 execute hololive-ocg-wiki-db --local --file=../../fixtures/volume.sql
```

Or just `make check-api`, which does both and then exercises every endpoint.

`fixtures.sql` is committed and generated from the 34 fixture cards — every card type,
every rarity, all 9 colours, all 7 locales, 539 Q&A items. No token, no network, no
Python. `seed` is deliberately not involved: it only ever writes to production.

**`volume.sql` is a second corpus, and the split is deliberate.** The coverage set is 34
cards and `pageSize` is 200, so locally `hasMore` was always false — `loadMore` could not
fire, and infinite scroll, the append path and the scroll restore were all unreachable.
That is why [#59](https://github.com/tskrlabs/hololive-ocg-wiki/issues/59) was found in
production three times: the third was a truncation that silently undid a restore once the
list was more than one page deep, and no local session could reach a second page to see it.

`volume.sql` adds 620 bulk cards, putting the local database at 654 — past three full
pages. Growing `fixtures.sql` instead would have meant rewriting ~100 exact-total
assertions in `smoke.sh` and multiplying 1.6 MB of golden files by twenty, to test
something none of them are about. So coverage stays coverage, volume is volume, and
`smoke.sh` keeps loading the 34-card corpus alone. `make volume` regenerates; Q&A and
`extra` are trimmed from these rows, since `fixtures.sql` already covers both.

33 of the 34 are real cards selected from `holo-data build` output; **one is synthetic**
(`9000001`), carrying the only remaining cover for `localize()`'s short-arts merge rule
([#16](https://github.com/tskrlabs/hololive-ocg-wiki/issues/16)). It appears in local dev
with an image that does not resolve, which is itself worth seeing.

Done when `seed --dry` reports the estimate above, production D1 is populated, and a
second `seed` writes nothing.

## Phase 4 — the Worker

Full reasoning and every measurement in [ADR 0005](adr/0005-worker-api.md).

```
apps/api/src/index.ts        app wiring, CORS, error handling
apps/api/src/routes/         cards (search/filter/detail/batch), filters (R2)
apps/api/src/db/             query builders and FTS escaping — pure, unit-tested
apps/api/src/lib/            Zod input schemas, response + cache helpers
apps/api/tests/smoke.sh      boots wrangler dev and curls every endpoint
```

**Grilling found five things the plan did not know.** Each changed the work, and two
were blockers:

1. **The Worker could not rebuild a card from what D1 stored.** `localize()` reads
   `color_codes` and `card_sets`; neither was a column and neither was in `payload` —
   they lived only in the junction tables, keyed for filtering rather than lookup. Both
   now go in the payload too (+3.2%), so a list page is one query with no fan-out.
2. **`/api/static-filters` was dead code**, returning enum values the contract already
   owns. Deleted; Phase 5 imports `@holo/schema/enums`. Eight endpoints became seven.
3. **Raw input crashes FTS5** — `a AND`, `-x` and a bare `"` are syntax errors. Every
   query is now wrapped as a literal phrase, so they return 200 with zero hits.
4. **The `name` filter was broken in v1**: 41% of characters are spelled inconsistently
   across their own cards ([F-015](archive/findings.md#f-015)). It keys on `name_ja` now.
5. **`apps/web/` does not exist**, so the phase's own done-when was unmeetable. Scope
   became API-only.

**A sixth turned up while building:** v1's colour filter silently omits fused
dual-colour cards ([F-016](archive/findings.md#f-016)). Filtering `blue` misses the 5 `blue_red`
cards, because `LIKE '%"blue"%'` does not match `"blue_red"`. The Worker expands the
filter instead of the storage.

### Phase 4 execution

**Executed 2026-07-27.** Schema migrated, production reseeded, artifacts published:

| | result |
|---|---|
| Migration | `name_ja` column + index added to the live database |
| `seed --confirm` | 2,448 cards, **49,785 rows written — exactly the estimate**, 18,762 read |
| Database size | 73.0 MB (15% of the 500 MB free tier) |
| `name_ja` populated | 2,448/2,448, **296 distinct characters** (was 381 name entries in `en`) |
| `publish` | 8 artifacts — `cards.json` + 7 `filter-options/` files; a second run uploads nothing |
| `make check` | green — 167 Python, 11 TS parity, 25 Worker unit, 34 endpoint checks |

**The deploy moved to Phase 5**, by decision — one deploy shipping the Worker and the
site together, rather than an API-only interim. It still needs a token with **Workers
Scripts Edit**; the seeder's token is scoped to D1 Edit + Analytics Read only, which is
correct and worth keeping. Commands are in [Phase 5](#phase-5--the-website).

## Phase 5 — the website

Full reasoning in [ADR 0006](adr/0006-website.md).

**The grilling found three holes, all of them gaps *between* phases rather than bugs
inside one:**

1. **`info.json` and `status.json` had no reader.** Uploaded to the private artifacts
   bucket since Phases 2 and 3; no Worker route served either. The site would have had no
   way to render its about dialog or its status page. → `/api/info`, `/api/status`.
2. **`content/README.md` documents a mechanism that does not exist** — it says the card
   count comes from `cards.json` "which the site already loads". The site never loads it.
3. **`status.json` changed shape**, so `/status` cannot be ported unchanged, and its
   Skipped tab has no data source in v2 at all.

### The commit sequence

| # | commit | state |
|---|---|---|
| 1 | `/api/info` + `/api/status` | ✅ done |
| 2 | scaffold `apps/web` on Nuxt 4 (`app/` srcDir, `nuxt generate`, `make dev`) | ✅ done |
| 3 | port the **live** code only — green on fixtures | ✅ done |
| 4 | Candidate 01 — one `useCardQuery` interface | ✅ done |
| 5 | Candidate 02 — deep Filter module | ✅ done in 3 — see below |
| 6 | Candidate 03 — Deck as sections, **wire format frozen** | ✅ done |
| 7 | Candidate 04 — `useDeckCards` | ✅ done |
| 8 | `assets` binding + SPA fallback + `run_worker_first` | ✅ built, rehearsed |
| — | **deploy to workers.dev** | ✅ done — verified against 2,448 cards |
| — | **attach the custom domain** | ✅ done — live at `hololive-ocg-wiki.tskrlabs.com` |
| — | Cloudflare's managed `robots.txt` conflict | 🔍 accepted, deferred to Phase 7 — [F-017](./archive/findings.md#f-017) |

**Candidate 02 arrived early, by necessity.** The empty-filter literal was written out
five times in v1, each a hand-maintained list of every colour, card type, rarity and bloom
level — and the typecheck rejected all five against the contract's enums (missing `HR`,
`supportStaff`, `unknown`). Correcting five copies by hand to match a generated enum would
have been the bug the refactor exists to prevent, so `createEmpty()` landed in commit 3
instead. `useDeckCards` was written there for the same reason and wired up in commit 7.

**All four candidates are done.** What they removed, measured:

| | before | after |
|---|---|---|
| `useCardStoreAPI` → `useCardQuery` + `cardSource` | 581 | 240 + 155 (seam, no Vue) |
| `filter-states.ts` | 413 | 158, and ~25 members → 9 |
| `decks-states.ts` | 488 | 254 + 158 `deckSections` + 103 `deckCode` |
| `DeckDetailCompactModeCardList.vue` | 219 | 120 |
| `DeckDetailCardList.vue` | 122 | 55 |
| `FloatingDeckCardList.vue` | 137 | 108 |

### Working on the site

```bash
make dev       # site on :3000 + Worker on :8787, HMR, fixtures, no credentials
make preview   # rehearsal: nuxt generate, then the Worker serves site + API on one port
make check-web # the site's unit tests
```

`make dev` proxies `/api` to the Worker, which is Nuxt's behaviour. `make preview` is the
only thing that exercises the **real** SPA fallback and same-origin requests — run it
before deploying, since the first deploy is otherwise unrehearsed.

**Indexing and analytics are off** unless `NUXT_PUBLIC_LAUNCHED=true`. Verified in both
directions: unset gives `Disallow: /`, `noindex, nofollow` and no sitemap; set gives an
indexable `robots.txt`, `sitemap_index.xml` and `index, follow`.

### Three API changes the frontend must adapt to

Verified against v1's live code, not assumed:

- **`total` is absent** when `skip_count=true`, rather than `-1`. `useCardStoreAPI.ts:657`
  comments *"response.total is -1 when skip_count=true"*. Read it as `total ?? cachedTotal`.
- **Over-cap batch requests 400** instead of silently returning the first 50.
  `useCardStoreAPI.ts:448` joins ids with no chunking. Chunk to 50 client-side.
- **Colour filters include fused cards**, so the separate `blue_red` / `white_green`
  checkboxes go — those cards now appear under both constituent colours (F-016).

Also: `constants/card-data.ts` → `@holo/schema/enums`, and `normalizeCard`
(`useCardStoreAPI.ts:88`) is a no-op spread over a commented-out body — delete outright.

### Two switches that must flip at Phase 7

The pre-launch site is deliberately invisible: **`noindex`** (v2-plan §7 defers the SEO
decision, and an indexed v2 would pre-empt it) and **analytics off** (pre-launch traffic
would pollute the container holding v1's real year of data). If these are missed at
launch, the new site stays invisible.

### The deploy — maintainer steps

**Everything is built and rehearsed.** `wrangler.jsonc` has the `assets` binding, the SPA
fallback and `run_worker_first`; `make preview` runs the exact production composition
locally and is green. What is left needs a token only the maintainer has.

Split in two deliberately (Q16): everything so far is verified against **34 fixture
cards**, and Phase 3's lesson was that the expensive bug appears only against a real
database.

#### 1. Build the site and deploy

```bash
make check                       # green before anything is uploaded
npm run generate --workspace @holo/web    # ⚠️ required — wrangler uploads this directory
cd apps/api
npx wrangler login               # needs Workers Scripts Edit; the seeder token is
                                 # scoped to D1 Edit + Analytics Read and will not do
npx wrangler deploy              # Worker + assets → workers.dev
```

`nuxt generate` is not optional: `assets.directory` points at `apps/web/.output/public`,
which is gitignored, so a fresh clone has nothing there and would deploy an empty site.

#### 2. Verify against the real 2,448 cards, before the domain

These are the numbers Phases 3 and 4 measured, so they double as a check that the reseed
landed:

```bash
API=https://hololive-ocg-wiki-tskrlabs-com.<your-subdomain>.workers.dev
curl -s "$API/api/health"
curl -s "$API/api/cards/search?q=フブキ"    | jq '.cards | length'   # expect 73
curl -s "$API/api/cards/search?q=そら"      | jq '.cards | length'   # 2 chars → LIKE path
curl -s "$API/api/cards/search?q=a%20AND"   | jq                     # 200, not 500
curl -s "$API/api/cards/filter?name=白上フブキ&locale=en" | jq '.total'  # expect 44
curl -s "$API/api/filter-options?locale=en" | jq '.names | length'   # expect 296
curl -s "$API/api/status" | jq '.counts.total'                       # expect 2448
curl -s "$API/api/info"   | jq '.contents | length'                  # expect 3
```

And the site itself:

```bash
curl -sL  "$API/tc/" -o /dev/null -w '%{http_code}\n'          # 200
curl -sL  "$API/tc/" | grep -c noindex                          # 1 — still invisible
curl -s   "$API/robots.txt"                                     # Disallow: /
curl -s   "$API/tc/deck/ANYTHING" -o /dev/null -w '%{http_code}\n'  # 200, SPA fallback
```

Then walk it in a browser — filter, search, open a card, build a deck, share a deck code,
switch locale. This is the first time any of it meets 2,448 cards rather than 34.

#### ✅ Steps 1 and 2 are done — executed 2026-07-27

Deployed to `hololive-ocg-wiki-tskrlabs-com.liching-chester.workers.dev`, version
`c44d51a1`. 75 asset files uploaded (9 unchanged), 632.50 KiB, 13 ms startup.

| check | expected | actual |
|---|---|---|
| `フブキ` search | 73 | **73** |
| `そら` (2 chars → LIKE path) | works | 56 |
| `a AND` (FTS5 syntax error) | 200 | **200** |
| `name=白上フブキ&locale=en` | 44 | **44** |
| `filter-options.names` | 296 | **296** |
| `status.counts.total` | 2,448 | **2,448** |
| `info.contents` | 3 | **3** |
| 51-id batch | 400 | **400** |
| 50-id batch | 50 cards | **50** |
| `colors=blue` | includes fused | 329 |
| `/api/status` under `Sec-Fetch-Mode: navigate` | JSON | **application/json** |
| `Cache-Control` on cards / filter-options | 3600 / 86400 | **3600 / 86400** |
| `robots.txt` + `noindex` | present | **present** |
| SPA fallback on an unknown deck code | 200 | **200** |

Every page loads in a browser with **zero exceptions, zero console errors and zero failed
requests**. The card grid renders real production art
(`img.hololive-ocg-wiki.tskrlabs.com/hPR/hBD24-001_P.webp`), and `/tc/status` shows
**已收錄 2,448** with the real seed timestamp.

Two notes: `/api/info` and `/api/status` were built this phase and had **never been read
before** — they work. And `run_worker_first` is confirmed doing its job: without it, every
one of the `curl` checks above would have returned HTML.

#### ✅ 3. The domain — attached 2026-07-27

`hololive-ocg-wiki.tskrlabs.com` serves the site and the API from one origin, which is
D2's whole point. Verified: `/tc/` 200, `/api/health` ok, SPA fallback on an unknown deck
code, `noindex` meta present.

**It turned up one thing local rehearsal could not** — a zone-level Cloudflare setting
rewrites what the Worker appears to serve. See [F-017](./archive/findings.md#f-017): the managed
`robots.txt` prepends `User-agent: * / Allow: /` above our `Disallow: /`. Accepted and
deferred; `noindex` carries the guard alone until Phase 7, when the conflict resolves
itself.

The site stays `noindex` until Phase 7 (Q10) — **the domain going live is not the
launch.** `NUXT_PUBLIC_LAUNCHED=true` flips indexing and analytics together.

#### About push-to-deploy

`wrangler deploy` is a **direct upload**; it creates no GitHub connection and Cloudflare
never learns this repo exists. Workers Builds is a separate, dashboard-only git
integration, and Cloudflare supports connecting an *existing* Worker — so Phase 6 can add
push-to-deploy on top of a Worker first deployed by hand, with no rework.

Two things to know when Phase 6 arrives:

- The dashboard Worker name must match `name` in `wrangler.jsonc` —
  `hololive-ocg-wiki-tskrlabs-com`. Deliberately **not** `hololive-ocg-wiki`: a Pages
  project of that name already exists (v1, which stays live until cutover). Workers and
  Pages do not share a namespace so it would not have collided, but two same-named things
  in one dashboard is avoidable confusion, and settling it now avoids a
  disconnect/reconnect after the git integration exists.
- Manual and build-triggered deploys both produce **versions**; whichever is promoted
  last becomes active. After Phase 6, a manual `wrangler deploy` would override the last
  pushed build until the next push.
- **Which branch triggers it is a Phase 6 decision.** Work lands on `develop` per the
  working agreement, so pointing Workers Builds at `main` makes merging to `main` the
  release action — which matches how the branches are already used.

## Phase 6 — push-to-deploy

Full reasoning in [ADR 0007](adr/0007-push-to-deploy.md).

Three things, in the order they depend on each other: make the deploy reproducible from a
clean checkout, close the last gap between "fresh clone" and "working site", then write
the docs a repo that goes public at Phase 7 needs.

### What the rehearsal found

Phase 6's own lesson, and it arrived the same way Phase 3's did — by running the thing
rather than reasoning about it. Rehearsing the Cloudflare build sequence in a scratch
clone, **`npm ci` failed on the first command**:

```
npm error `npm ci` can only install packages when your package.json and
npm error package-lock.json are in sync.
npm error Missing: vue-router@5.2.0 from lock file
```

The lockfile recorded `vue-router: ^4.5.1` for `apps/web` while `apps/web/package.json`
declares `^5.2.0` — the Nuxt 4 upgrade in `fce28d9` updated the manifest but not the lock.
Cloudflare's auto-install runs `npm ci`, so **the first push-to-deploy build would have
failed**, on a repo where everything looked green locally.

It also means the live site was built against a tree the manifests do not describe: local
`node_modules` held vue-router **4.6.4**, which does not satisfy Nuxt 4.5's own `^5.2.0`.
A clean install resolves 5.2.0 under `node_modules/nuxt/`. `make check` is green on it —
no `package.json` changed, only the lock.

This is the argument for rehearsing in a scratch clone rather than trusting a working
laptop, and it is why the rehearsal is a permanent per-phase step rather than a one-off.

### The fresh-clone walk

Run from `/tmp/holo-fresh`, cloned from the branch, with `uv` replaced by a shim that
exits 127 on invocation — so any Python toolchain dependency fails loudly rather than
silently succeeding off the maintainer's machine.

| check | result |
|---|---|
| `npm ci` | ✅ after the lockfile fix (failed before) |
| `npm run generate --workspace @holo/web` | ✅ builds |
| `npx wrangler deploy --dry-run --config apps/api/wrangler.jsonc` | ✅ 98 assets, 632.50 KiB, all 4 bindings |
| `make check-api` | ✅ 25 unit tests + every endpoint check |
| `npm test --workspace @holo/web` | ✅ 44 tests |
| `seed-local-r2.sh` | ✅ 7 filter-options + info + status, no Python |
| `/api/filter-options` in **all 7 locales** | ✅ 25 names each (the bug the committed artifacts fix) |
| `/api/status` · `/api/info` · `/api/health` | ✅ 34 cards · 3 sections · ok |

The `--dry-run` numbers match the live deploy exactly, which is the point: the build
Cloudflare will run produces what was deployed by hand.

### `make dev` no longer needs Python

`seed-local-r2.sh` generated the R2 artifacts on every start by running a script that
imports `holo_data.build`, and therefore pydantic — so a frontend contributor needed
`uv sync`, a venv and a Python toolchain before the site's filter dropdowns worked in six
of seven locales.

The artifacts are **committed** now (`fixtures/artifacts/`, 64 KB), which is ADR 0001's
rule applied to fixtures rather than to the contract: generated output lives in git so no
Python is needed to consume it, and `make check` fails if it is stale. The generator
gained `--check`, catching stale *and* orphaned files, and is wired into `make generate`
and `make check-schema`.

`filter_options()` is deliberately **not** reimplemented in Node. It encodes F-015 — 41%
of characters are spelled inconsistently across their own cards — and a second copy of
that rule is the drift ADR 0001 exists to prevent.

Verified with a `python3` shim that exits 127: local R2 seeding still succeeds.

### Docs for a public repo

- **`CONTRIBUTING.md`** (D14) — what needs no credentials, what needs the maintainer and
  why, how to report a bad translation, and the one trap: regenerate after touching the
  contract.
- **`LICENSE`** — Apache-2.0, matching v1. Without it, "public at Phase 7" means
  all-rights-reserved, which would contradict a `CONTRIBUTING.md` inviting contributions.
  Code only; card data and art stay Cover Corp.'s under the Derivative Works Guidelines.
- **[F-018](./archive/findings.md#f-018)** — writing the above surfaced that D14 promised
  translation fixes as a reviewable PR, and ADR 0002 replaced the mechanism without
  replacing that property: the cache is gitignored, so there is no file to edit. Logged,
  not fixed — closing it is pipeline design work, and the repo is private until Phase 7.

### The dashboard step — maintainer

Everything above is committed and verified. What is left needs the Cloudflare dashboard.

Settings for the connection are in [`infra.md` §7](./infra.md) — production branch `main`,
the build and deploy commands, root directory `/`, non-production branch builds off,
caching off.

Then **merge `develop` → `main`**, which is both the release action and the test: the tree
is already what is live, so a successful build produces a version identical in behaviour
to the running one. A failed build promotes nothing, so the site is never at risk.

Verify afterwards — build log green, a new version in the dashboard, and the Phase 5 checks
against the custom domain:

```bash
SITE=https://hololive-ocg-wiki.tskrlabs.com
curl -s "$SITE/api/cards/search?q=フブキ" | jq '.cards | length'   # 73
curl -s "$SITE/api/filter-options?locale=en" | jq '.names | length' # 296
curl -s "$SITE/api/status" | jq '.counts.total'                     # 2448
curl -sL "$SITE/tc/" | grep -c noindex                              # 1 — still invisible
```

### Three switches to flip at Phase 7 — flipped 2026-08-02

Was two; the rehearsal added a third.

| switch | where | state |
|---|---|---|
| `NUXT_PUBLIC_LAUNCHED=true` | Workers Builds **build** variable (dashboard) | ✅ set — flips indexing **and** analytics together |
| `workers_dev: false` | `wrangler.jsonc` | ✅ flipped in [#68](https://github.com/tskrlabs/hololive-ocg-wiki/pull/68) — was kept only to compare origins while [#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17) was open; that closed, and once indexing is on a live `workers.dev` origin is a second indexable copy of all 17,241 URLs our canonical tags do not govern |
| repo public + v1 archived | GitHub | ⬜ outstanding — v2-plan §7 |

**Where the first switch lives is the part worth remembering.** It is a *build* variable,
not a runtime one: `nuxt generate` reads it, and `vars` in `wrangler.jsonc` are runtime-only
and never reach the build. So it cannot be moved into version control the way
`workers_dev` was, and searching the repo for the reason the site is visible will find
nothing.

**Neither issue this section used to gate is still gating.**
[#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17) is **closed** — fixed at the
zone rather than resolving itself at launch, which is the better outcome:
`robots.txt` is back under version control instead of merely agreeing with Cloudflare's
copy. [#18](https://github.com/tskrlabs/hololive-ocg-wiki/issues/18) stays **open** and
lost its `phase-7` label — launch does not build the correction mechanism, it creates the
contributors who need it.

What the launch switch now carries is settled in
[ADR 0011](adr/0011-launch-posture.md): indexing on, cookieless analytics on, and nothing
else. Archiving v1 also retires [F-014](./archive/findings.md#f-014)'s standing read-tier
failure mode.
