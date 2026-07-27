# Phase 5 — grilling log

**Status:** ✅ grilling complete — 16 decisions, implementation under way
**Held:** 2026-07-27
**Outcome:** [ADR 0006](adr/0006-website.md) · progress in [`progress.md`](./progress.md)

The full record of the Phase 5 design interview, kept because the ADR states the
decisions while this states the **alternatives that were rejected and why**. Each entry
was written as the answer was given, so an interrupted session could resume without
re-asking.

Read alongside [`v2-plan.md`](./v2-plan.md) §4 (D2, D9, D13) and
[`architecture-review-v1.md`](./architecture-review-v1.md) (the four candidates).

## State at the start of Phase 5

Established by inspection, not assumption:

- **Nothing of Phase 5 exists.** No `apps/web/`, no stash, no unmerged branch. The tree
  is clean at `05a9b68`. "Interrupted" meant the session ended, not that code was left
  half-written.
- **The Worker is built but not deployed** — the one outstanding Phase 4 item.
- **`info.json` and `status.json` have no reader.** Both are in the *private* artifacts
  bucket and no Worker route serves them. v1 read `info.json` from
  raw.githubusercontent.com and `status.json` from a committed `public/status.json`.
- **`status.json` changed shape** in v2 — snake_case, `counts{}` / `changed[]` /
  `writes{}` — against v1's `source.valid` / `diff.qaUpdated` / `skipped[]`. The status
  page cannot be ported unchanged.
- Card `id` is the **official site's own detail-page id** (`scrape/fetch.py:91`), so it
  is externally stable and existing deck codes keep resolving.

### v1 frontend, measured

| area | LOC |
|---|---|
| `components/` (excluding `ui/`) | 5,106 |
| `components/ui/` (shadcn) | 3,717 |
| `composables/` | 2,115 |
| `pages/` (4 pages) | 1,123 |
| `i18n/locales/` (7 JSON) | 4,231 |
| `types/` + `constants/` + `plugins/` | 390 |

`public/` carries 1.4 MB icons, 2.9 MB screenshots, favicon, manifest, robots and a
Google verification file — **not** `card_images/` (1.0 GB), which is R2's job now (D1/D9).

## Decisions

### Q1 — When does the pending Phase 4 deploy happen?

**→ At the end of Phase 5: one deploy, with assets and the domain together.**

No API-only deploy. The first-ever `wrangler deploy` ships the Worker, the `assets`
binding, the SPA fallback and `hololive-ocg-wiki.tskrlabs.com` in one step.

*Consequence:* the whole of Phase 5 is developed against **local `wrangler dev` and the
34-card fixtures** — exactly the credential-free property D12 exists to provide. The
Phase 4 production-verification numbers (`フブキ` → 73, `filter-options.names` → 296) are
checked after that single deploy, not before.

### Q2 — Which Nuxt version?

**→ Nuxt 4 (4.5.0), with the `app/` srcDir layout.**

The port is already a file-by-file move into a directory that does not exist yet, and
Nuxt 4's headline breaking change *is* that directory move (`pages/`, `components/`,
`composables/` → `app/`). Absorbing it now is nearly free; doing it later is a second
pass over every file. v1 is on 3.17; the 3.x line is in maintenance at 3.21.9.

Every module v1 uses is Nuxt-4-ready (checked 2026-07-27): `@nuxtjs/i18n` 10.5.0,
`shadcn-nuxt` 2.8.0, `@nuxtjs/seo` 5.3.6 (peers `^3.16.0 || ^4.0.0`), `@nuxt/image` 2.0.0,
`@nuxtjs/color-mode` 4.0.1, `reka-ui` 2.10.1, `@nuxt/icon` 2.3.1.

*Accepted risk:* a v4-specific breakage during the port could be mistaken for a porting
bug. Tolerable because there is no working v2 frontend to regress against — every bug
found is a new bug either way.

### Q3 — How is the site built and served?

**→ `ssr: false` + `nuxt generate` → static files, bound as Worker assets with SPA
fallback.**

`apps/api/wrangler.jsonc` gains an `assets` block pointing at `apps/web`'s generated
output, with `not_found_handling: "single-page-application"`. **No Nitro server ships.**
The Worker stays exactly the 7-route Hono app Phase 4 built; anything outside `/api/*`
is served as a static asset instead of 404-ing.

*Why not the `nitro-cloudflare` preset:* it inverts D2 — the API would stop being the
Worker and become a route inside Nuxt's Nitro server, meaning every request runs JS
(static assets risk becoming metered, v2-plan §6) and `apps/api`'s wrangler.jsonc, tests
and `smoke.sh` would all be rewritten to suit a build tool.

*Why not v1's `nuxt build` + ship `.output/public`:* it builds a Nitro server on every
run purely to discard it, and makes the deployable artifact a side effect rather than
the declared output — which is why v1 needed a hand-written `deploy.sh`.

Consistent with D13 (no rendering-mode change — v1 is already `ssr: false`) and with
v2-plan §6 (static assets are free and unlimited only while they are *assets*).

### Q4 — Port strategy against the four refactors

**→ Purge first, then port only live code, then refactor in separate commits.**

Three ordered steps:

1. **Purge on the way in.** The dead legacy store (`useCardStore.ts`), its six forked
   views (`Filter.vue`, `SearchInput.vue`, `CardListView{,Basic,VirtualScroller}.vue`)
   and `plugins/cards.ts` **never enter this repo**. Candidate 01's deletion half is
   satisfied by construction, not by adding files and deleting them again.
2. **Get the live code building and green** against the new API, on fixtures.
3. **Apply Candidates 02–04** (Filter, Deck, `useDeckCards`) as separate reviewable
   commits on top.

*Why not a verbatim copy first:* it is not actually available. The dead store
dynamic-imports `data/cards_i18n.json` (8 MB), which does not exist here — D1 moved data
out of git. A "verbatim" copy would fail to build on precisely the files Candidate 01
deletes.

*Accepted cost:* step 2 debugs the port and the API contract change at the same time.
Mitigated by the three known contract deltas being written down in advance (see Q1 notes
and progress.md "What Phase 5 needs to know").

### Q5 — What does `make check` verify about the website?

**→ Typecheck, plus unit tests over the pure refactored modules.**

`nuxt typecheck` and a successful `nuxt generate`, plus tests on exactly the modules
Candidates 02–04 create — which are pure by design, so they need no DOM:

- the filter shape: one `createEmpty()`, one `toApiParams()`, one `isActive()`
- the deck: section routing and the 1 oshi / 50 main / 20 yell limits
- `useDeckCards`: the count → dedupe → join derivation
- `deckCode.encode/decode` round-trip (the pure transform currently welded into
  `decks-states.ts` with `window`/`localStorage`/`useI18n`)

This is the bug class v1 actually shipped: `CARD_BLOOM_LEVELS = ["debut","1st","2nd","spot"]`
against data that says `first`/`second`, and a missing `HR` rarity that made 24 cards
unfilterable. Typecheck catches the second; a `toApiParams` test catches the first.

*Not chosen:* Playwright end-to-end. It is the only option that catches a broken
template, but it puts a browser dependency inside `make check` — which is the pre-commit
hook — and browser E2E is historically the most brittle part of any local check.
Revisit post-launch if template regressions actually happen.

*Known gap, accepted:* nothing automated asserts a template renders. Templates are
verified by running the site.

### Q6 — How does the frontend read `info.json` and `status.json`?

**→ Two new Worker routes, `GET /api/info` and `GET /api/status`, streaming the R2
objects through exactly as `/api/filter-options` does. Seven endpoints become nine.**

This closes a hole Phase 4 left: `publish` uploads `info.json` and `seed` uploads
`status.json`, both into the **private** artifacts bucket, and **nothing could read
either**. v1 got them from raw.githubusercontent.com and a committed
`public/status.json` respectively — both of which D11 exists to kill.

Same shape as `filters.ts`: `ARTIFACTS.get(key)`, 404 with a written message when the
artifact is missing, `c.body(object.body)` streamed rather than parsed, explicit
`Cache-Control`. The bucket stays private, so the 21 MB `cards.json` remains unreachable.

*Why not bake `info.json` into the bundle:* it is committed at `content/info.json`, so
it *could* be imported at build time. Rejected to keep D11 intact — editing site copy
stays a `publish`, not a redeploy — and to keep both artifacts on one mechanism rather
than two.

*Why not a public custom domain on the artifacts bucket:* it would reverse ADR 0003 and
make the 21 MB `cards.json` world-readable at a guessable URL, which is the specific
thing that decision prevents.

**Note for the ADR — D11's premise has weakened.** D11 justified R2 by the
edit-without-redeploy property, but the Phase 2 amendment made `info.json` a *committed*
file, so editing it is already edit → commit → `publish`; under Workers Builds (Phase 6)
that commit auto-deploys regardless. The property is thinner than when D11 was written.
The decision above keeps R2 anyway — consistency with `status.json`, which is written by
`seed` and never committed, so it has no build-time copy to bake in.

### Q7 — The `/status` page, whose data contract broke

**→ Port it, adapted to v2's `status.json`. Drop the Skipped tab.**

The mismatch, measured:

| v1 page expects | v2 `status.json` has |
|---|---|
| `generatedAt`, `diff.qaUpdated` | `generated_at`, `qa_updated` — snake_case throughout |
| `source.total` / `source.valid` | `counts.total` only; no valid-vs-source split |
| `skipped[]` with `missingFields`, and a Skipped tab | **nothing** |
| `imagePath` | `image_key` (D9) |
| — | `writes{}`: `estimated`, `actual`, `rows_read`, `database_bytes` |
| — | `built_at`, `counts.missing_from_build` |

The port: map snake_case, use `counts.total`, render `image_key` through `cardImage()`,
keep `built_at` as a second timestamp, ignore `writes{}` (seeder telemetry, not user
information). Remove the Skipped tab and trim the ~5 now-dead `status.*` i18n keys across
all 7 locales.

*Why not restore `skipped[]` to the pipeline:* it would reopen Phase 1/3 code during
Phase 5 to build a second channel for information v2's build already reports through
collect-and-report validation.

*Why not drop the page:* it is a live v1 feature, and `seed` already uploads the artifact —
dropping it would leave `/api/status` with nothing to serve.

### Q8 — The info dialog: card count, and the release badge

**→ Card count and last-updated come from `/api/status`. The release badge is dropped.**

Two loose ends from the Phase 2 amendment to D11, both found by reading
`content/README.md` against the v2 reality.

**The count.** `content/README.md` says the card count and date come "from `cards.json`'s
own `generated_at` and card count, **which the site already loads**". That last clause is
**false in v2** — the site never loads `cards.json`. It is 21 MB, and D8 moved all
querying to D1; nothing in the frontend fetches the artifact. `status.json` already
carries `counts.total` and `generated_at`, and the info dialog is a click-to-open modal,
so the fetch is lazy and costs nothing at page load. **`content/README.md` must be
corrected** as part of Phase 5 — it currently documents a mechanism that does not exist.

*Why not fold the count into `/api/filter-options`:* it would avoid a request, but needs
a `build` change plus a republish of all 7 artifacts, and puts card-set facts into a file
named for dropdown values.

**The badge.** v1's dialog renders `<img :src="releaseImgUrl">` from
`release-shields-url`; v2's `content/info.json` **already dropped that key**. Keep it
dropped and delete the `<img>`. The repo is private until Phase 7, so a shields.io badge
would 404 for the whole pre-launch period, and nothing in this repo cuts releases. It is
also a third-party request on every dialog open.

### Q9 — The local development loop

**→ `nuxt dev` proxies `/api` to `wrangler dev`, as v1 did. Plus a composed pre-deploy
check.**

Two commands behind one `make dev`: Nuxt on :3000 with a nitro `devProxy` forwarding
`/api` → `wrangler dev` on :8787, against local D1 and the 34 committed fixtures. This is
v1's arrangement, and it means relative `/api/...` paths work identically in dev and in
production — no `runtimeConfig` API base, no environment-dependent URL construction.

Because Q1 chose a single deploy at the end, **dev is the only place the site runs before
production**. So the loop is deliberately two-tier:

- **`make dev`** — HMR, fast, but the SPA fallback and same-origin behaviour are Nuxt's,
  not the Worker's.
- **a composed check before deploying** — `nuxt generate`, then `wrangler dev` serving
  assets *and* API from one port. This is the only thing that exercises the real
  `not_found_handling: "single-page-application"` path, and skipping it would leave the
  first-ever deploy completely unrehearsed.

*Why not an absolute `NUXT_PUBLIC_API_URL`:* it would make production requests
cross-origin, promoting the CORS allowlist from belt-and-braces to load-bearing —
contradicting the design stated in `apps/api/src/index.ts`.

### Q10 — Search indexing before launch

**→ Block all indexing until Phase 7.**

`robots.txt` with `Disallow`, `X-Robots-Tag: noindex` from the Worker, and no sitemap
submission. The SEO configuration is ported in full — with `tskrlabs.com` URLs replacing
v1's hardcoded `lichingchester.dev` in `site.url`, `i18n.baseUrl`, the canonical link,
the og/twitter image URLs, `_robots.txt`, and `plugins/seo.ts`'s JSON-LD — but held
behind one flag flipped at launch.

*Why:* v2-plan §7 explicitly defers the domain/SEO strategy to Phase 7, and an indexed v2
would pre-empt that decision. v1 has a year of accumulated SEO on the same 2,448 cards; a
second indexed copy is duplicate content competing with the site we have not decided how
to retire. v2-plan §2 calls the un-announced domain "staging until launch" — this is what
makes that literally true.

*Why not decide at deploy time:* the highest-consequence, least-reversible setting on the
site would be chosen in the moment. That is how v1 ended up with the domain hardcoded in
five files.

### Q11 — Candidate 03 vs. persisted deck data

**→ Refactor the deck in memory only. The storage and wire formats stay frozen.**

Candidate 03 replaces three parallel arrays with a section-keyed model — but that exact
shape is **persisted in two places we do not control**:

- `localStorage["hololive-ocg-wiki-decks"]` in every existing user's browser
- base64 inside every shared deck-code URL (`getDeckCode`: `btoa(encodeURIComponent(
  JSON.stringify({id, name, oshiCards, mainCards, yellCards})))`), which live in Discord
  messages indefinitely

So the section model is **internal only**, with one serialize/deserialize seam at the
boundary, pinned by a round-trip test. `{oshiCardIds, mainCardIds, yellCardIds}` — and
the deck code's `{oshiCards, mainCards, yellCards}` count-map — keep their exact shape.

This is also where the review's "extract a pure `deckCode.encode/decode`" note lands
naturally: the boundary needs a module anyway, and making it pure is what lets the
round-trip be tested without `window`, `localStorage` or `useI18n`.

**What makes this safe across the cutover:** card `id` is the official site's own
detail-page id (`scrape/fetch.py:91`), not a database rowid, so ids are stable from v1 to
v2. Only the envelope was ever at risk.

*Why not migrate-on-read:* shared URLs never expire, so the legacy reader must exist
forever either way — migration would add moving parts without removing the old shape.

*Accepted cost:* the legacy shape survives, confined to one module and documented as a
compatibility boundary rather than an accident.

### Q12 — `public/` assets

**→ Game icons: WebP only, behind one `gameIcon()` helper. Screenshots: `.jpg` only.**

`public/icons/` (1.4 MB) is UI chrome — colour, type and keyword icons — not card data,
so D1 does not apply and it stays committed. But:

- **Drop the PNG halves** (~800 KB). Every browser Nuxt 4 supports has WebP; the pairs
  are v1 hedging against browsers that no longer exist, in a repo whose founding
  complaint (D1) was weight.
- **One `gameIcon(kind, key)` helper**, mirroring `cardImage()`. The architecture review
  flagged `/icons/type_${key}.png` as duplicated verbatim across `FilterAPI.vue`,
  `Filter.vue` and `CardDataRowsBlock.vue`; `Filter.vue` is already deleted by Q4, and
  this retires the rest.

**Also found while measuring:** `public/screenshots/` is 2.9 MB, of which the
`desktop.png` / `mobile.png` pair (2.3 MB) is **entirely unreferenced** — `manifest.json`
cites only the `.jpg`s. They are dead-code purge, not a decision.

Carried over unchanged: `favicon.ico`, `icon.png`, `manifest.json`, `_robots.txt` (with
Q10's `Disallow`), `how-to-use/searching-cards.png`. **Not** carried: `card_images/`
(1.0 GB — R2's job per D1/D9), `google17c60aa593f0e3b2.html` (a Search Console
verification token for the *old* domain, meaningless on `tskrlabs.com`).

### Q13 — Analytics

**→ Port `nuxt-gtag` with the same container, disabled until launch.**

Same flag as Q10: while the site is `noindex`, the tag does not fire. Pre-launch traffic
is the maintainer and possibly an agent, and recording that would pollute the GTM
container (`GTM-MZHVHBGQ`) holding v1's real year of data. Both flip at Phase 7.

### Q14 — Where the work happens

**→ A feature branch on the main checkout, PR'd to `develop`.**

Same flow as Phases 2–4. Not a worktree: Phase 5 installs a full Nuxt app and needs a
working `wrangler dev`, and progress.md records that the pipeline's working data
(`pipeline/data/`, `locales/`, `images/`, `build/`) lives in **this** checkout and needs
four `HOLO_*` env vars to be reachable from a worktree. Fewest moving parts for the phase
with the most dependency churn.

### Q15 — Delivery shape

**→ One PR on `phase-5-website`, with commits ordered by the Q4 steps.**

| # | commit |
|---|---|
| 1 | `/api/info` + `/api/status` routes, with smoke-test coverage (Q6) |
| 2 | scaffold `apps/web` on Nuxt 4, `app/` srcDir, `make dev` (Q2, Q3, Q9) |
| 3 | port the **live** code only — green on fixtures (Q4 step 2) |
| 4 | Candidate 01 — one `useCardQuery` interface |
| 5 | Candidate 02 — deep Filter module |
| 6 | Candidate 03 — Deck as sections, wire format frozen (Q11) |
| 7 | Candidate 04 — `useDeckCards` |
| 8 | `assets` binding + SPA fallback + custom domain, then the single deploy (Q1) |

Candidate 01's *deletion* half is already satisfied by commit 3 (Q4); commit 4 is the
unification half. Matches how Phases 2–4 shipped and keeps the phase atomic on `develop`.

*Why not split at the refactor boundary:* it would park a working-but-knowingly-
un-refactored site on `develop` — the exact half-done-migration state D13 identifies as
the cause of v1's problems.

### Q16 — First contact with real data

**→ Refines Q1. Still one deploy, but the domain is attached as a separate second step.**

Every check chosen above runs against the **34-card fixtures**. Production has 2,448
cards and 296 distinct names, and Phase 3's most expensive bug — 15.5M rows read on a
27,203-row write — appeared *only* against a real database, because SQLite does not
report `rows_read` and D1 does. A frontend that is correct on 34 cards is not thereby
known to be correct on 2,448.

So commit 8 (Q15) splits:

```bash
cd apps/api
npx wrangler deploy                    # Worker + assets → workers.dev
# exercise the real site against 2,448 cards on the workers.dev URL
# only then: attach hololive-ocg-wiki.tskrlabs.com
```

This preserves Q1's intent exactly — one deploy, no API-only interim, the site and API
going live together — while moving first contact with real data onto a URL nobody has.

*Why not `wrangler dev --remote` against production D1:* it needs a Cloudflare token in
the dev loop, breaking D12's credential-free property, and reads the live database — the
resource that already breached its free tier once (F-014).

## The API contract deltas, verified against real code

Phase 4 listed three. All three are confirmed to hit live v1 code:

| delta | v1 site does | must become |
|---|---|---|
| `total` omitted when `skip_count=true`, not `-1` | `useCardStoreAPI.ts:657` comments *"response.total is -1 when skip_count=true"* and keeps page 1's total | `total ?? cachedTotal` |
| over-cap batches 400, not silent truncation | `/api/cards-list/${missingIds.join(",")}` (`:448`) with no chunking | chunk to `MAX_BATCH` = 50 client-side |
| colour filters include fused cards | separate `blue_red` / `white_green` checkboxes from `constants/card-data.ts` | drop both boxes — the Worker expands via `FUSED_COLORS` (F-016) |

Plus, from Phase 4's handover: `constants/card-data.ts` → `@holo/schema/enums`, and
`normalizeCard` (`useCardStoreAPI.ts:88`) is a no-op spread over a commented-out body —
delete outright.

## Amendments this phase makes to earlier decisions

To fold into `progress.md`'s amendments table:

| Decision | Change |
|---|---|
| **Phase 4** | Seven endpoints → **nine**. `/api/info` and `/api/status` were never built, leaving `info.json` and `status.json` in a private bucket with no reader (Q6) |
| **D11** | `content/README.md` claims the card count comes from `cards.json` "which the site already loads" — **the site never loads it** (21 MB; D8 moved querying to D1). The count comes from `/api/status` (Q8) |
| **D11** | The edit-without-redeploy premise is weaker than when written: `info.json` is committed since Phase 2, so editing it is already edit → commit → publish, and Workers Builds will auto-deploy that commit anyway. R2 retained for consistency with `status.json` (Q6) |
| **D13** | "four refactors + dead-code purge" is joined by a **framework upgrade**, Nuxt 3.17 → 4.5 (Q2). Still no new features, no redesign, no rendering-mode change |
| **Phase 5 status page** | Cannot be ported unchanged — the Skipped tab and `source.valid` have no data source in v2's `status.json` (Q7) |
| **v2-plan §7** | The SEO decision stays deferred, but Phase 5 must actively **block indexing** to keep it deferrable (Q10) |

## Done when

- `make check` green, including `apps/web` typecheck + the pure-module unit tests (Q5)
- `nuxt generate` + `wrangler dev` on one port serves the site and the API, with SPA
  fallback working, against local D1 fixtures and **zero credentials** (D12, Q9)
- the four candidates are applied; the dead store, its six forked views and
  `plugins/cards.ts` are absent from this repo entirely (Q4)
- a v1 deck code and a v1 `localStorage` payload both still resolve (Q11)
- one `wrangler deploy` ships the API and the assets together; the real site is exercised
  against 2,448 cards on workers.dev, and only then does
  `hololive-ocg-wiki.tskrlabs.com` point at it (Q1, Q16)
- the site works end-to-end on the domain while returning `noindex` (Q10)
- Phase 4's production verification finally runs: `フブキ` → 73,
  `filter-options.names` → 296, `name=白上フブキ&locale=en` → 44

## Open, deliberately

- **Playwright end-to-end** — rejected for `make check` (Q5), revisit post-launch if
  template regressions actually occur.
- **Phase 6 assumes this shape.** Workers Builds must run `nuxt generate` in `apps/web`
  before `wrangler deploy` in `apps/api` — a monorepo build order Phase 6 has to
  configure, created by Q3.
- **The `noindex` / analytics flag is a Phase 7 action.** Two switches (Q10, Q13) must
  flip at launch; if they are missed, the new site stays invisible.
