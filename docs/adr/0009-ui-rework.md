# ADR 0009 — The UI/UX rework

**Status:** accepted
**Date:** 2026-07-31
**Amends:** [ADR 0006](0006-website.md)'s D13 — deliberately, not as a correction
**Blocks:** Phase 7 (launch)
**Tracked in:** [#31](https://github.com/tskrlabs/hololive-ocg-wiki/issues/31) — the
wayfinding map, whose fifteen closed tickets hold the measurements behind every decision
here

## Context

Phase 5 rebuilt the site's *inside*. D13 fenced it to "four refactors + a framework
upgrade — no new features, no redesign", and that was the right call: the refactors were
large, the card contract had drifted, and mixing a redesign into that work would have made
both unreviewable.

The consequence is that v2's **outside is still v1's**. The theme is stock shadcn slate
(`--primary: oklch(0.208 0.042 265.755)`, near-black) with nothing identifying the game.
The grid renders art only, so [#29](https://github.com/tskrlabs/hololive-ocg-wiki/issues/29)
— the show-original toggle has nothing to act on. Filters are a screen-covering sheet on
every breakpoint. Every filter change throws a full-screen backdrop blur over the results
being refined. And **a card has no URL at all**: `CardItem` opens a `Dialog`, so for a
*wiki* there is nothing to link, nothing to index, and no back button.

That last one is why this blocks launch. Phase 7 is a one-time SEO event — v1 carries a
year of accumulated authority on the same 2,463 cards — and redirecting it onto a site
where no card is addressable, then adding 2,463 URLs afterwards, means a second crawl and a
changed sitemap. The URLs either exist when Google first sees us or the opportunity is
spent.

## Decisions

### Scope and destination

**D1. The two jobs stay: browse cards, build decks.** Set pages, a rules glossary and
editorial articles were considered and ruled **out of scope** — they are wiki *surfaces*,
each dragging in a content pipeline and an authoring story. This rework fixes the
information architecture and the craft of what already exists.

**D2. The rework blocks Phase 7.** Launch ships the reworked site.

### Identity

**D3. "Neutral but crafted", with no accent hue.** Ground
`oklch(0.975 0.002 260)` / `oklch(0.135 0.004 260)`, `--primary` **equal to
`--foreground`**, Inter with Noto TC/JP/KR/Thai, `ui-monospace` tabular numerals for card
numbers, `--radius: 0.5rem`. Card art is the only saturated thing on screen.

Chosen from four directions built against real card art and judged in a browser
([#35](https://github.com/tskrlabs/hololive-ocg-wiki/issues/35)) — deliberately *not*
hololive's own palette, which for a fan site is a trademark judgement call.

**D4. Therefore no state may be signalled by hue.** Selected chips, in-deck tiles,
uncommitted-edit markers and errors use weight, fill and border. `--destructive` is the
single semantic colour and is reserved for destructive *actions*, never for reporting a
failure. This is a constraint the palette imposes, accepted knowingly.

**D5. `--border` at 1.23:1 cannot carry state**, so a second token `--border-strong` at
≥3:1 exists for anything conveying it (WCAG 1.4.11). Text contrast passes AA in both modes
without help — `muted-foreground` measures 4.63:1 light, 6.32:1 dark.

### Card identity and SEO

**D6. A card's URL is `/{locale}/card/{set}/{stem}`** — `image_key` verbatim.
`card_number` is **not unique** (2,463 cards over 1,228 numbers; 889 numbers used by 2+
cards, one by nine) and `id` is an unstable scrape-order integer. The bare stem is *also*
insufficient: `hBP03-044_SR` and `hBP03-055_SR` exist under both `hBP03/` and `hCO01/` —
the F-006 pair, different artwork by different illustrators. The set segment is what makes
the URL unique by construction. All 2,461 stems are URL-safe unescaped.

**D7. Card pages are SPA routes with Worker-injected metadata, not prerendered.**
2,463 × 7 locales = 17,241 files against a 20,000 free-tier asset cap — it would fit today
and break within two card sets. `HTMLRewriter` injects title, description, canonical,
`og:*`, `hreflang` and JSON-LD into the shell in **0–1 ms**, measured against a 10 ms CPU
limit.

**D8. The Worker and the page emit metadata from one shared `cardMetaTags()`.** unhead
*adopts* server-injected tags on hydration (its `createDomState` walks existing `<head>`
children and keys them by `dedupeKey`), so they update in place rather than duplicating —
**provided both sides emit the same keys and values**. A mismatch is cloaking, so one
function with a golden test is the only safe construction.

**D9. The Worker must not manage the robots tag.** `noindex` is compiled into the shipped
JS by `IS_PUBLIC`, so stripping it server-side would not make a page indexable — hydration
restores it. Phase 7's build flag stays the single control.

### Layout

**D10. A persistent 280px filter rail from `lg`; the sheet stays below it.** Search and the
result count move into the rail. The Apply footer keeps Apply and Reset and **drops
Close**, which is meaningless in a panel that never closes; because seven groups are now
visible at once, pending edits are marked **per group** rather than by one global dot.

**D11. Columns derive from a ~190px target tile width, not a breakpoint ladder.** The
existing ladder is non-monotonic — 178px tiles at 1440px, **152px at 1536px** — so widening
the window shrank the cards. Deriving from a target makes tile size stable at every width
and dissolves the "12 columns, 120px tiles" problem entirely.

**D12. The shell is a flex column; the grid is `flex-1 min-h-0`.** The scroller's
`height: 100dvh` between two sticky bars hid **138px** of the list, which is the
undiagnosed cause of both the floated results summary and `pb-[65vh]`.

**D13. Mobile is 2 columns comfortable, 3 compact.** At 375px, 2 columns gives 170px tiles
where **1 of 2,463** names truncates; 3 gives 112px boxes where **130** do. But comfortable
shows only **4 cards per screen** against 9, so on mobile density stops being a preference
and the control moves to the header.

### Card tile and detail

**D14. A tile is art + name + card number**, with comfortable/compact density, both
persisted. This closes [#29](https://github.com/tskrlabs/hololive-ocg-wiki/issues/29).

The source name goes on **its own line**, not inline as `OriginalText` does in the dialog:
inline, **19%** of tiles truncate mid-comparison against **<1%** stacked — and truncating a
comparison defeats the toggle's purpose. The dialog keeps inline, where there is room. This
matters because **84–93%** of cards have a name differing from the Japanese, so it is a
real third line.

**D15. One `CardDetail`, two containers — and the dialog owns the URL.** Clicking a tile
opens the **dialog** *and* pushes the card URL; that URL opened cold renders the **page**.
Today the dialog changes no URL, so a card is unlinkable and back exits the list entirely —
on mobile, the back gesture discards scroll and filters. Without the push, `/card/…` would
be 2,463 pages no user ever reaches.

The page earns what the dialog cannot: variants **expanded** rather than behind a lazy
accordion (**86%** of cards have a sibling), Q&A (35%), and "other cards of this character"
(296 names, ~8.3 cards each) — which also gives crawlers real internal links.

### Filtering and feedback

**D16. The draft → apply flow is kept on every breakpoint.** Instant filtering was measured
and costed: at v1's traffic it lands at **265%** of the 5M/day read tier against Apply's
66%. The measurement also found ADR 0004's "~50–100 rows per filtered page" is wrong by one
to two orders of magnitude — the real median is **4,169** — because `id IN (SELECT …)`
sorts every match before `LIMIT`. Page size is irrelevant: the same filter costs 1,328 rows
at `LIMIT 20` and at `LIMIT 200`.

**D17. Nothing ever covers the results.** Skeletons at the fixed aspect ratio; refiltering
dims the previous results rather than blurring the screen. Query state becomes a
**discriminated union**, because `isLoading: boolean` + `cards: []` cannot express failure
— which is why a blocked API currently renders *"No cards found — try adjusting your
filters"*, blaming the user for a network error.

### Deck building

**D18. The deck becomes a right-anchored overlay drawer.** A permanent third column costs a
full grid column at 1512px (6 → 5), paid even while browsing; today's `FloatingDeck` sits
directly over where the rail now is. Deck-open replaces `isEditing` — **except on mobile**,
where the sheet occludes the grid, so the two decouple. The rule: *the deck surface implies
editing only where it does not occlude the grid.*

### Supporting surfaces

**D19. `/status` keeps its stat tiles and loses its tabs.** Production reports
`changed: 2463, new: 0` — the tabs hold everything or nothing. Deletes 311 of 580 lines and
three hardcoded `bg-green-500`. It moves into the header's overflow menu, reachable on
mobile for the first time.

**D20. `/how-to-use` is deleted.** Its link had been commented out, so it shipped
unreachable, and it documented a UI this rework replaces. Done in `7171e7c`.

**D21. The header keeps four controls plus an overflow menu.** Today 4 of 8 are
`hidden sm:inline-flex`, so mobile silently loses status, GitHub and Discord.

### Type, motion, testing

**D22. Two weights on CJK faces, three on Latin.** Fonts cost **1.5 MB** on a `tc` card
grid today, **87% of it Noto Sans TC**, at ~70 KB per extra CJK weight. No manual
subsetting: Google ships 105 `unicode-range` slices. CJK is **never preloaded** (correctly —
preloading 105 slices fetches the whole font), so `font-display: swap` plus a real fallback
stack is the entire strategy.

**D23. Grid updates do not animate.** `RecycleScroller` recycles DOM nodes, so a list
transition animates a node into a different card's content. The unused `list` transition is
deleted. `prefers-reduced-motion` gets one global rule.

**D24. Mount where a value crosses a boundary; no headless browser.** Every bug this map
found — F-019, #45, #49 — is a wiring bug that pure-function tests structurally cannot see.
The cloaking check needs no browser: `cardMetaTags()` is unit-tested, the Worker's output is
curl-able, and the page calls the same function, so agreement is by construction. A new
`apps/web/tests/smoke.sh` mirrors the API's, on a separate `make check-site` — `make check`
is 46s today and `nuxt generate` alone is 11s.

## Consequences

- **Phase 7 waits.** In exchange, launch ships one crawl, one sitemap, one identity.
- **Card views become billable Worker invocations.** `run_worker_first` extends to
  `/*/card/*` so a missing card returns a real 404 instead of a soft 200. This is the
  direct cost of the SEO decision; the pattern is narrow deliberately, and the rest of the
  site stays free static assets.
- **`image_key` needs a unique index**, or every card page is a 2,463-row scan. A migration,
  as `name_ja` was in Phase 4.
- **Nine bugs were found by specifying this**, all pre-existing and independently
  shippable: [#40](https://github.com/tskrlabs/hololive-ocg-wiki/issues/40),
  [#41](https://github.com/tskrlabs/hololive-ocg-wiki/issues/41),
  [#43](https://github.com/tskrlabs/hololive-ocg-wiki/issues/43),
  [#44](https://github.com/tskrlabs/hololive-ocg-wiki/issues/44),
  [#45](https://github.com/tskrlabs/hololive-ocg-wiki/issues/45),
  [#49](https://github.com/tskrlabs/hololive-ocg-wiki/issues/49),
  [#50](https://github.com/tskrlabs/hololive-ocg-wiki/issues/50),
  [#51](https://github.com/tskrlabs/hololive-ocg-wiki/issues/51),
  [#56](https://github.com/tskrlabs/hololive-ocg-wiki/issues/56).
- **D4 constrains everything downstream.** A future contributor reaching for a colour to
  mean "active" is reaching for something this palette does not have.

## Alternatives considered

**Reskin only.** Rejected: a new theme over a site where no card has a URL is v1 repainted,
and it would not have closed #29 or the SEO gap.

**Become a full wiki** — set pages, glossary, articles. Ruled out of scope: each needs a
content pipeline and an authoring story, and none is needed for launch.

**Deck builder as the headline product.** A different product thesis, not a redesign.

**Prerendering all 17,241 card pages.** Fits today's asset cap at 86% and breaks within two
card sets.

**SSR.** Reverses D2/D13 and puts every request on the metered Worker tier, where static
assets are free and unlimited.

**Instant filtering.** Measured at 265% of the read tier. See D16.

**A headless browser for end-to-end tests.** ~200 MB and a browser download, to cover what
`cardMetaTags()` covers by construction — against a working agreement that forbids GitHub
Actions and keeps verification local.
