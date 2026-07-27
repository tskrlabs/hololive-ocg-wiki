# ADR 0006 — the website

**Status:** accepted, in execution
**Date:** 2026-07-27
**Phase:** 5
**Supersedes nothing. Amends:** D11, D13, and Phase 4's endpoint count.

The decisions behind `apps/web` and the final shape of the Worker. Every one was put to
the maintainer individually during a grilling session; the full interview, including the
options rejected and why, is in [`../phase-5-grilling.md`](../phase-5-grilling.md).

## Context

Phases 0–4 built the contract, the pipeline, R2, D1 and the API. The site itself is still
v1's: a Nuxt 3.17 SPA in another repo, pointed at v1's Worker, carrying two half-finished
migrations (a dead client-side card store, and an abandoned camelCase card shape).

D13 fixed the scope in advance — the four candidates from
[`../architecture-review-v1.md`](../architecture-review-v1.md) plus a dead-code purge, no
new features, no redesign, no rendering-mode change.

## The holes this phase found

Three, none of which were in the plan. They are recorded here because each was a gap
between phases rather than a bug inside one — the class of defect a phase boundary hides.

### 1. Two artifacts had no reader

`holo-data publish` has uploaded `info.json` since Phase 2 and `holo-data seed` has
uploaded `status.json` since Phase 3, both into the **private** artifacts bucket. **No
Worker route served either.** Phase 4 built the seven card endpoints and stopped; the
site would have had no way to render its about dialog or its status page.

**Decision: add `GET /api/info` and `GET /api/status`.** Same shape as
`/api/filter-options` — fetch the R2 object, stream the bytes through unparsed, 404 with
a written message naming the command that produces it. The bucket stays private, which is
what keeps the 21 MB `cards.json` beside them unreachable.

**Nine endpoints.** v1 had eight; Phase 4 deleted `/api/static-filters` to make seven;
this restores two that are genuinely new.

TTLs are set per artifact rather than shared. `info.json` is one hour — its entire
purpose is being edited without a redeploy (D11), and a day-long TTL would leave a typo
in the disclaimer visible until tomorrow. `status.json` matches `CARD_TTL`, because it
changes on exactly the event that changes the card data.

### 2. `content/README.md` documents a mechanism that does not exist

It states the info dialog's card count comes from "`cards.json`'s own `generated_at` and
card count, **which the site already loads**." The site never loads `cards.json` — it is
21 MB and D8 moved all querying to D1.

**Decision: the count and last-updated date come from `/api/status`**, which already
carries `counts.total` and `generated_at`. The dialog is click-to-open, so the fetch is
lazy. `content/README.md` is corrected as part of this phase.

The rule that file states — *"a number in this file is a number nobody will remember to
change"* — is right and is preserved. `info.json` still carries no facts about the data.

### 3. `status.json` changed shape, so `/status` cannot be ported as written

| v1 page expects | v2 artifact has |
|---|---|
| `generatedAt`, `diff.qaUpdated` | `generated_at`, `qa_updated` — snake_case throughout |
| `source.total` / `source.valid` | `counts.total` only |
| `skipped[]` with `missingFields`, and a Skipped tab | **nothing** |
| `imagePath` | `image_key` (D9) |

**Decision: port the page adapted, and drop the Skipped tab.** Restoring `skipped[]` to
the pipeline would reopen Phase 1/3 code to build a second channel for information the
build already reports through collect-and-report validation.

## Decisions

| | decision |
|---|---|
| **Framework** | **Nuxt 4.5** with the `app/` srcDir. The port is already a file-by-file move into a directory that does not exist; Nuxt 4's headline breaking change *is* that move. Absorbing it now is nearly free, later is a second pass over every file. Amends D13, which was silent on the framework version. |
| **Build** | `ssr: false` + **`nuxt generate`** → static files, bound as Worker assets with `not_found_handling: "single-page-application"`. **No Nitro ships.** The Worker stays the Hono app Phase 4 built. Using the `nitro-cloudflare` preset would invert D2 — the API would become a route inside Nuxt's server, and every request would run JS, risking the free-and-unlimited status of static assets (v2-plan §6). |
| **Port order** | Purge → port live code → refactor. The dead store, its six forked views and `plugins/cards.ts` **never enter this repo**, so Candidate 01's deletion half is satisfied by construction. A verbatim-copy-first approach was not available anyway: the dead store imports `data/cards_i18n.json`, which D1 removed from git. |
| **Deck format** | Candidate 03's section model is **in-memory only**. `localStorage["hololive-ocg-wiki-decks"]` and the base64 deck-code URL keep their exact v1 shape behind one serialize/deserialize seam, pinned by a round-trip test. Shared deck codes live in Discord messages indefinitely. Card `id` is the official site's own detail-page id (`scrape/fetch.py:91`), so ids stay valid across the cutover — only the envelope was ever at risk. |
| **Verification** | `nuxt typecheck` plus unit tests over the pure modules the refactors create — filter shape, deck sections and limits, the `useDeckCards` join, `deckCode` round-trip. No Playwright in `make check`: it is the pre-commit hook, and browser E2E is the most brittle thing that could live there. **Accepted gap:** nothing automated asserts a template renders. |
| **Dev loop** | `nuxt dev` proxies `/api` → `wrangler dev`, as v1 did, so relative paths work identically in dev and production and no `runtimeConfig` API base exists. Plus a composed `nuxt generate` + `wrangler dev` rehearsal before deploying — the only thing that exercises the real SPA fallback. |
| **Indexing** | **Blocked until Phase 7.** `robots.txt` Disallow, `noindex`, no sitemap submission; analytics configured but not firing. v2-plan §7 defers the SEO strategy to Phase 7, and an indexed v2 would pre-empt it — a second copy of the same 2,448 cards competing with a site we have not decided how to retire. |
| **Assets** | Game icons stay committed (UI chrome, not card data) but **WebP only**, behind one `gameIcon()` helper mirroring `cardImage()`. Not carried: `card_images/` (1.0 GB, R2's job), the unreferenced 2.3 MB screenshot PNGs, and the Search Console token for the old domain. |
| **Deploy** | One deploy — Worker and assets together — **to workers.dev first**, exercised against the real 2,448 cards, and only then is the domain attached. |

## Why the deploy is split from the domain

Everything above is verified against the **34-card fixtures**. Production has 2,448 cards
and 296 distinct names, and Phase 3's most expensive bug — 15.5M rows read on a
27,203-row write — appeared *only* against a real database, because SQLite does not
report `rows_read` and D1 does.

A frontend correct on 34 cards is not thereby known to be correct on 2,448. Attaching the
domain as a second step keeps the number of deploys at one while moving first contact
with real data onto a URL nobody has.

Running `wrangler dev --remote` against production D1 instead was rejected: it needs a
Cloudflare token in the dev loop, breaking D12's credential-free property, and it reads
the live database — the resource that already breached its free tier once (F-014).

## D11's premise is weaker than when written

Worth recording, because it will look like an oversight later. D11 justified moving
`info.json` to R2 by the edit-without-redeploy property. The Phase 2 amendment then made
it a **committed** file at `content/info.json`, so editing it is already edit → commit →
`publish`; under Workers Builds (Phase 6) that commit auto-deploys regardless.

R2 is kept anyway, for consistency with `status.json` — which is written by `seed` against
a live database, is never committed, and therefore has no build-time copy to bake in.
Splitting the two across different mechanisms would cost more than the redundancy does.

## Found while scaffolding (commit 2)

Five dependencies in v1's `package.json` do not survive the purge, found by grepping for
actual usage rather than trusting the manifest:

| dropped | why |
|---|---|
| `fuse.js` | used only by `useCardStore.ts` — the dead store Q4 never ports |
| `@tanstack/vue-table` | used only by `components/ui/table/utils.ts`, itself unreferenced — `StatusCardTable.vue` is a raw `<table>` |
| `@tanstack/vue-virtual` | zero references anywhere |
| `@nuxtjs/tailwindcss` | zero references; v1 styles through the `@tailwindcss/vite` plugin |
| `gh-pages` | v1 deployed to GitHub Pages; this deploys to a Worker |
| `@nuxt/scripts` | registered as a module, never used |

**`@nuxtjs/seo` is replaced by the four sub-modules actually used** — `nuxt-site-config`,
`@nuxtjs/robots`, `@nuxtjs/sitemap`, `nuxt-seo-utils`. The meta-package pulls six, and
two of them are dead weight here: `nuxt-og-image` (a satori/resvg rasteriser — v1
configured an `ogImage` block but never called `defineOgImage()`, and its build output
contains no generated images; the pages set `ogImage:` via `useSeoMeta`, a plain meta tag
pointing at a static `icon.png`) and `nuxt-schema-org` (v1 hand-writes its JSON-LD in
`plugins/seo.ts`).

This was forced rather than chosen: in a workspace install npm nested `nuxt-og-image`
under `@nuxtjs/seo` instead of hoisting it, and Nuxt could not resolve it. `ogImage: false`
does **not** help — the meta-package installs its sub-modules before config is read, so
the failure is resolution, not execution. Naming the four is smaller and more honest
about the dependency surface anyway.

**Version corrections** — v1's pins were carried over and two were stale against Nuxt 4:
`vue-tsc` `^2.2` → `^3.3.8` (2.x crashes on Nuxt 4's `@vue/language-core`), and
`vue-router` `^4.5.1` → `^5.2.0` (what Nuxt 4 actually installs).

**A v1 title bug, fixed.** v1 set both `title: "Hololive OCG Wiki"` and
`titleTemplate: "%s | Hololive OCG Wiki"` in `app.head`, so any page that set no title of
its own rendered **"Hololive OCG Wiki | Hololive OCG Wiki"**. Dropping the title instead
is worse (`%s` resolves empty → "| Hololive OCG Wiki"); the fix is to set the title and
let `nuxt-seo-utils` compose the suffix from `site.name`. Verified in the generated HTML.

**One known-noisy warning, deliberately filtered in the Makefile.** `nuxt typecheck`
prints a full `ERR_PACKAGE_PATH_NOT_EXPORTED` stack for
`vue-router/volar/sfc-route-blocks`, then exits 0 with no type errors: `vue-tsc` probes
for an optional plugin that vue-router 5 no longer exports, supporting `<route>` blocks in
SFCs — a feature Nuxt does not use, because it derives routing from the file system. The
`typecheck` target drops those lines so the trace cannot be mistaken for a failure at the
end of `make check`, which is the pre-commit hook. Real errors still print and a non-zero
exit still fails the target; both were verified by introducing a type error.

## Found while porting (commit 3)

The typecheck against the generated contract turned up **36 errors** in code that had been
running in production for a year. Most were drift the contract makes visible:

- **`oshi_skill.cost` rendered in two `v-if` blocks that have never fired.** ADR 0001
  found the field declared in three files and present on zero of 2,448 cards; the
  templates were reading a property that does not exist.
- **`related_card_numbers` was flat**; the contract nests it as
  `related_cards.card_number`.
- **`AppHeader` duplicated `AppInfoButton`'s entire info fetch**, including a
  `safeJsonParse` helper needed only because raw.githubusercontent.com serves JSON as
  `text/plain`. Both now share one `useAsyncData("info")` against `/api/info`.
- **The Discord link was built as `` `https://discord.gg/${url}` `` from a value that is
  already a full URL** — a doubled URL in both components.
- **Five hardcoded `lichingchester.dev` URLs in JSON-LD pointed at images that never
  existed** (`icons/icon-512x512.png`, four `how-to-use/*.png`). Structured data
  referencing 404s; dropped rather than re-pointed.
- **`plugins/seo.ts` set a *static* canonical URL on every page**, alongside a
  route-aware one in `app.vue`. The two disagreed on every page but the home page.
- **`@tanstack/vue-table` and the shadcn `ui/table` wrapper were unreachable** —
  `StatusCardTable.vue` is a hand-written `<table>`.

**Candidates 02 and 04 landed here rather than in their own commits.** Not scope creep —
the alternative was worse. The empty-filter literal appears five times in v1, each a
hand-written list of every enum member, and the typecheck rejected all five against the
contract. Hand-correcting five copies to match a generated enum is exactly the failure
mode the refactor exists to prevent, so `createEmpty()` replaced them. `useDeckCards` has
the same story: its duplicated derivation carried a type error.

**A gap in credential-free local dev, now closed.** `fixtures.sql` gives a local D1, but
nothing populated local **R2** — so `make dev` served a site whose filter dropdowns 404ed
in six of seven locales and whose about dialog was empty. `fixtures/build_local_artifacts.py`
now builds all three artifacts from the committed fixtures, reusing the pipeline's own
`filter_options()` so local and published shapes cannot diverge.

**Verified in a real browser**, since a typecheck cannot prove a template renders: all
three pages load with **zero exceptions, zero console errors and zero failed requests**,
20 cards rendering with correctly composed D9 CDN URLs
(`img.hololive-ocg-wiki.tskrlabs.com/hBP01/hBP01-001_OUR.webp`), and the status page
showing the adapted v2 shape. Driven one-off over CDP — not added to `make check`, per Q5.

## Found while unifying the stores (commit 4)

Candidate 01's *deletion* half was satisfied in commit 3; this is the unification half —
one `useCardQuery` over a `cardSource` seam, replacing a 581-line `useCardStoreAPI`.

Mapping the store's ~20 exported members to their consumers turned up more dead surface:

- **Four filter-option methods had no callers at all** — `getNameOptions`,
  `getTagOptions`, `getSetOptions`, `precomputeFilterOptions` — because `FilterAPI.vue`
  fetched `/api/filter-options` with its own `$fetch` and never used them.
- **`useCardDetail` also called `$fetch` directly**, so opening a card detail bypassed
  every cache the store maintained and refetched a card the list already had.
- **`allCards`, `loadCards`, `searchCards` and `getCacheStats` had no consumers either.**

So the store maintained caches two of its own consumers routed around. Both now go
through the interface, which also **dedupes in-flight requests** — two components mounting
in the same tick previously made the same request twice.

**The seam is real, not ceremonial.** `cardSource.ts` takes a `Transport` and touches no
Vue; production passes the `$fetch` adapter and the tests pass a recorder. That is what
lets the endpoint contract — batch chunking, `skip_count`, the filter mapping — be
asserted with no network, database or browser. Two adapters is the bar the review set for
a seam being worth having.

**One TypeScript quirk worth recording.** `$fetch` types its result by matching the URL
against Nuxt's generated route table; our paths are the *Worker's* routes, so there is
nothing to match and the inference recurses until TypeScript reports "excessive stack
depth" (TS2321) — an error about its own type-checker, not our code. The transport reaches
`$fetch` through an untyped alias to skip that inference, and casts once. One cast at the
boundary, rather than nine at the call sites.

## Found while modelling the deck (commits 6–7)

Candidates 03 and 04, and the last of the four.

**The deck rules had no home, and nothing enforced them.** v1's `addCardToDeck` pushed
unconditionally — there was no cap anywhere in the store — so a 60-card main deck was
reachable and the only feedback was a badge turning red. The limits existed solely as
numbers typed into templates (`${deck.mainCardIds.length}/50`), with the status-colour
ternary copied **six times** across `pages/deck/[code]/index.vue` and `FloatingDeck.vue`.
`deckSections.ts` owns them now, `DeckSectionBadge.vue` renders them once, and
`addToSection` refuses to exceed a limit.

**The measurements:**

| file | before | after |
|---|---|---|
| `decks-states.ts` | 488 | 254 (+ 158 `deckSections` + 103 `deckCode`, both pure) |
| `DeckDetailCompactModeCardList.vue` | 219 | 120 |
| `DeckDetailCardList.vue` | 122 | 55 |
| `FloatingDeckCardList.vue` | 137 | 108 |

**The wire format is verified frozen, not merely intended to be.** Beyond the unit tests,
a browser check seeds `localStorage` with a v1-shaped deck, reloads, and then navigates to
a **hand-built v1 deck code** — one this codebase's encoder did not produce. It renders
`1/1`, `2/50`, `1/20` with card art and zero console errors. That is the Q11 claim tested
against the real thing rather than against our own round trip.

One deliberate asymmetry: limits are enforced on *add*, but `sectionStatus` can still
report `over`. A deck imported from an old code or written by an earlier build may exceed
them, and the badge has to be able to say so.

## Consequences

- Nine endpoints. `apps/api` gains `routes/artifacts.ts`; `smoke.sh` grows from 34 checks
  to 43, including both missing-artifact branches.
- `smoke.sh` now wipes local R2 as well as local D1. It did not before, which was latent:
  the new "404 before publish" checks would have passed once and failed on every rerun.
- Two switches must flip at Phase 7 — `noindex` and analytics. If they are missed, the
  new site stays invisible.
- Phase 6 inherits a monorepo build order: `nuxt generate` in `apps/web` must precede
  `wrangler deploy` in `apps/api`.
