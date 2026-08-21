# ADR 0009 — The UI/UX rework

**Status:** accepted
**Date:** 2026-07-31 · **D18 amended 2026-08-01** · **D25–D26 added 2026-08-02**
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

**D18. The deck panel pushes the grid from `xl`, and is a modal sheet below it.**
*Amended 2026-08-01; the original decision is kept below, because what it got right is
most of it.*

The rule is unchanged and is the reason the amendment is small: *the deck surface implies
editing only where it does not occlude the grid.*

| width | surface | occludes the grid | editing |
|---|---|---|---|
| ≥ 1280 | pushed column, 384px | no | follows the panel |
| 1024–1280 | modal sheet | yes | decoupled |
| < 1024 | modal sheet | yes | decoupled |

**What the original got wrong was not the reasoning but the primitive.** It called for "an
overlay beside a still-visible grid" and was built on `SheetContent`, which mounts a
`bg-black/80` overlay and reka-ui's focus-trapping `DialogContent`. So at *every* width the
grid was blacked out and inert while the deck was open — and the deck-open ⇒ `isEditing`
coupling, whose whole premise is that you can click a tile while the deck is up, was
coupling editing to a surface you could not use. The design was never actually built. A
non-modal drawer would have fixed the modality and left the rightmost columns permanently
covered, so the panel **pushes** instead: `<main>` shrinks and the grid re-derives its
columns from the width it has left.

**Pushing costs columns, not tile size** — which is D11/#43 paying off. `columnsForWidth`
re-derives from the new width, so the cards you can still see are the size they were:

| viewport | browsing | building | tile |
|---|---|---|---|
| 1280 | 5 @200px | **3** | 205px |
| 1512 | 6 @205px | **4** | 212px |
| 1920 | 8 @205px | **6** | 209px |

**Why `xl` and not `lg`.** The rail is 280px and the panel 384px, so a pushed grid is
`width - 664`. Measured over every width: the hard floor is **1145px**, below which the
grid falls under three columns or outside the 150–240px band, in one contiguous run from
1024. `xl` sits 135px above that floor — 1145 is not a breakpoint any stylesheet has, and
its 160px tile is 10px off `MIN_TILE`, one padding change from breaking. So the threshold
is the nearest real breakpoint that clears the floor with room. The consequence is
accepted knowingly: **between 1024 and 1280 the deck is still a sheet you open and close**,
because the alternative there is a two-column grid.

**One `DeckPanel`, two containers** — D15's pattern, for D15's reason: the containers
differ in how they present the surface, not in what it is. Above `xl` a plain `<aside>`
flex sibling; below, a `Sheet`. The panel cannot be one component that changes mode,
because reka-ui portals dialog content to `<body>` and a portalled element cannot be a
flex sibling of the thing it is meant to push.

**The panel's own grid is 3 columns, fixed.** It was `grid-cols-4 md:grid-cols-10`, and
`md:` reads the *viewport* while the grid lives in a 384px panel — so on any desktop it
packed ten columns into ~326px and rendered **30px tiles under 32px control buttons**. The
panel's width is a constant, so a responsive prefix there can only ever be wrong. Three
columns is what 326px affords: 102×142px.

**Opening the panel must not lose the reader's place.** The column count is in
`RecycleScroller`'s key, so a reflow remounts it at offset 0 — the same loss as #59 from a
different cause. #59's pixel offset cannot be reused: the reflow leaves `itemCount` (its
guard) untouched while changing what a pixel means, so a pixel restore passes every check
and lands ~20 cards away — at 1512px, 3,000px is item ~54 at 6 columns and ~32 at 4. What
survives a reflow is *which card*, so the panel path remembers a first-visible **index**
and restores it through `scrollToItem`. The card path keeps pixels.

**Choosing a deck opens the panel and starts editing, at every width.** Creating a deck,
clicking its name, and clicking the pencil are one statement of intent, and all three used
to do only `setCurrentDeck` — so the panel stayed shut, editing stayed off, and the next
click on a card did nothing, because the add controls only render while editing. `openFor`
does all three. It deliberately does **not** defer to `setOpen`: that applies the rule
above, which is right for *toggling a surface* and wrong for *choosing a deck*, since
below `xl` it would leave editing off and the user closing the sheet to reach the cards
would find they still could not add any. The rule survives, because it governs what
opening the panel implies, not what every path to an open panel implies.

That exposed a latent bug in the #57 delete guard, which routed through `setOpen(false)`
and therefore left `isEditing` true whenever the panel occluded the grid — unreachable
before, because nothing turned editing on at those widths; one click away after. The guard
now clears editing directly: with no deck there is nothing editing could refer to.

**The mobile sheet gets a full-width Close button.** `SheetContent`'s built-in close is a
bare 16px `X` in the top-right — under WCAG 2.5.8's 24px minimum, and in the hardest corner
of a phone to reach one-handed. The new one is pinned below the scroll region, so it is
reachable without scrolling past 71 cards. Sheet only: where the panel is pushed there is
nothing to close out of, and the footer's Deck button is the toggle.

**And the capture and the restore key on different events**, which is not a detail. The
reflow is asynchronous: `<main>` narrows, *then* a `ResizeObserver` reports it, *then* the
column count changes, *then* the scroller remounts. A restore scheduled at the toggle finds
a working scroller with the **old** geometry, succeeds against it, and consumes the memory
— and the remount that follows lands at the top with nothing left to put it back. The
position is lost in a way indistinguishable from never having tried. So the index is
captured on the panel (before the reflow, while the old numbers are true) and restored on
`gridColCount` (after it, once the remount is certain) — the same signal the scroller's
`:key` is built from, so the two cannot disagree about whether a remount happened.

<details>
<summary>The original D18, superseded</summary>

**The deck becomes a right-anchored overlay drawer.** A permanent third column costs a
full grid column at 1512px (6 → 5), paid even while browsing; today's `FloatingDeck` sits
directly over where the rail now is. Deck-open replaces `isEditing` — **except on mobile**,
where the sheet occludes the grid, so the two decouple. The rule: *the deck surface implies
editing only where it does not occlude the grid.*

Its objection to a permanent column stands and is *why the panel is not permanent*: the
column is paid only while the deck is open, and closed is the default on every load.

</details>

**D25. Scrollbars are themed globally, and the thumb is `--border-strong`.**
*Added 2026-08-02.*

The site had **two** scrollbar systems and styled only one. Five surfaces use reka-ui's
`ScrollArea`, which draws its own thumb; every other scroll region — the card grid, the
filter rail, the deck panel, the card page, `/status` — is a plain `overflow-y-auto` and
rendered the browser default. In a palette whose whole premise is that nothing on screen
competes with card art (D3), a 15px OS-grey trough was the last piece of unthemed chrome.

`--border-strong`, not `--border`, because **D5 already decided this**: a scrollbar reports
position within 2,463 cards, which makes it a UI component conveying state, and WCAG 1.4.11
wants 3:1. `--border` measures 1.23:1. `ScrollBar.vue`'s scaffold default was `bg-border`
and moves onto the same token, so the two systems agree.

The track occupies layout width rather than overlaying, which makes a CSS choice an input
to D11's column rule — `ResizeObserver`'s `contentRect` excludes a classic
`::-webkit-scrollbar`. Swept over 320–3840px in every rail/panel combination: the 10px
shifts *where* thresholds land (260 widths above `xl` drop one column) but **cannot push a
tile outside the 150–240px band** — 300 out-of-band widths with and without it, all from
the `MIN_COLUMNS` clamp in combinations the app never renders. Pinned in `grid.test.ts`.

Two mechanisms, because they are not one feature: `::-webkit-scrollbar` for Chrome and
Safari, `scrollbar-width`/`scrollbar-color` for Firefox, whose `thin` is ~11px and not
settable. The two are near-identical rather than pixel-identical; the alternative is a
JS-drawn scrollbar on every region, which is what `ScrollArea` already is.

**D26. `/status` gains a source-side diff, and the re-seed number is told rather than
hidden.** *Added 2026-08-02.*

D19 deleted the per-card lists on the strength of one observation: production reports
`changed: 2463, new: 0`, so a list of "changed" cards is a list of every card, and nobody
can act on it. That reasoning was correct and **is not reversed here**. What it missed is
that `changed` was measuring the wrong thing to begin with.

`content_hash` covers the card's columns and its *translated* payload — all seven locales.
So the translation rework, which rewrote every locale's text, marks all 2,463 cards
changed while the official card list did nothing at all. The number is real; the story it
tells a reader is false. Two different events were sharing one word.

They separate cleanly, because the pipeline already holds both baselines. `translations['ja']`
inside `cards.json` **is** the JP source — `transform` writes it and `apply_translations`
only ever adds other locales beside it — so a hash over the JP text plus the
language-independent columns measures *the official site changed this card*, independently
of anything we did to it downstream. That is **`source_hash`**, a third column beside
`content_hash` and `qa_hash`.

Its scope mirrors `content_hash`'s own split exactly: **JP text and columns, minus Q&A**.
The schema went out of its way to separate `qa_hash` so that a new FAQ does not rewrite a
card's rules text, and that split is worth just as much in a report — "the official site
added FAQs to eleven cards" is a different sentence from "the official site errata'd
eleven cards". Columns are in scope, not only prose: `card_sets` is a column, and the
Selection Cup update moved it on ~660 cards, which is exactly the kind of official change
that must not go quiet.

**The write plan does not change.** `SeedPlan`'s `new`/`changed`/`qa_updated` are an
`elif` chain — mutually exclusive, priority-ordered — and that is correct for deciding
what to write, because a changed card rewrites both payloads anyway. It is wrong for
*reporting*: a card with both a text edit and a new FAQ lands in `changed` alone, so
`qa_updated` reads 0 even when the source added FAQs. The fix is not to rework a measured
write path. Three **report-only sets** — `source_added`, `source_changed`, `faq_changed` —
are computed independently, each by its own predicate with no priority between them, and
`build_status` reads those. Writes stay byte-identical to today's.

**A missing baseline means *unknown*, not *changed*.** The first seed after this ships
finds `source_hash` NULL on every row; a naive comparison would report 2,463 source
changes, which is the precise false alarm the whole decision exists to remove. NULL is
therefore treated as source-unchanged and silently backfilled. It follows that the report
is truthful only from the *second* run — so this ships **before the pending translation
reseed**, letting that one D1 write pass do both jobs. The first `/status` a reader sees
then says "2,463 cards rebuilt, nothing changed at the source", which is both true and the
whole point.

**The lists come back for source changes only.** `source_added` and `faq_changed` are
usually 0–100 entries, specific, and every row links to a card the reader can open. The
re-seed list stays a single number with a sentence — that is D19's 2,463, and restoring it
would restore the pagination and view modes D19 deleted. Lists are capped at 100 with the
true count retained, so a large set release cannot regress into that.

The cap applies to the **artifact**, not just the page. `status.json` is 329 KB and 99.9%
of it is the unrendered 2,463-entry `changed` list; the about dialog downloads all of it
to read two fields. Capped, the artifact is ~15 KB — the core report is 353 bytes and a
card entry is 98. Nothing read the full lists: the page dropped them at D19 and the
maintainer has the seeder's own stdout.

**The explanatory sentence is derived, never authored.** The seeder can see *that* 2,463
rows were rewritten with no source change; it cannot know *why* — a re-translation, a
schema fix and a plain re-run look identical from there. So the page picks its copy from
the shape of the data (`source_changed == 0 && changed > 0` → "we rebuilt every card's
data; the cards themselves did not change at the source"), which translates through the
existing seven-locale sweep and cannot go stale. A hand-written note in `info.json` was
rejected for being v1's bug wearing a new hat: v1 embedded "Our database has 2448 cards
(June 19, 2026)" in editorial prose, permanently wrong the day after it was written, and
`/api/status` exists to kill exactly that.

**The seed refuses on an unmigrated database.** `0003` must be applied before any seed
writes the column, or every batch fails on an unknown column name — mid-run, after
earlier batches have committed. `check_gates` already refuses with a written reason and a
command to run; this is one more `Refusal`, probing for the column before anything is
written.

Two things this deliberately does not do. **There is no history**: `status.json` stays
overwritten per run, so the page says "the latest update" and means it — a seed run for an
unrelated reason overwrites the interesting report, and that is accepted rather than
solved with a changelog nobody has asked for yet. And **there is no release date**, because
`Card` carries none; "cards added since our last seed" is answerable and "cards released
this month" is not. Note that `counts.new` was *already* the honest answer to the first —
a card id appears only when the official list publishes it — so that number needed
rendering, not machinery.

### Supporting surfaces

**D19. `/status` keeps its stat tiles and loses its tabs.** Production reports
`changed: 2463, new: 0` — the tabs hold everything or nothing. Deletes 311 of 580 lines and
three hardcoded `bg-green-500`. It moves into the header's overflow menu, reachable on
mobile for the first time.

*Extended by D26, which does not restore the tabs.*

**D20. `/how-to-use` is deleted.** Its link had been commented out, so it shipped
unreachable, and it documented a UI this rework replaces. Done in `7171e7c`.

**D21. The header keeps four controls plus an overflow menu.** Today 4 of 8 are
`hidden sm:inline-flex`, so mobile silently loses status, GitHub and Discord.

*Amended by D28, which puts two destinations back in the header from `lg` up.*

**D28. GitHub and Discord leave the overflow menu from `lg`; the menu stays at every
width.** D21 fixed a *reachability* bug — `hidden sm:inline-flex` meant a phone lost status,
GitHub and Discord entirely, with nothing indicating anything was missing — and the fix
made the header identical at 390px and 1440px (`5d6e394`). This makes it width-conditional
again, which needs saying out loud.

It is not the same defect inverted. Below `lg` the overflow menu still holds all six
destinations, so nothing is unreachable at any width; an item is on the shelf at one width
and in the drawer at another. The two are removed from the menu at `lg` (`lg:hidden`)
because a dropdown repeating an item visible an inch to its left reads as a menu that
forgot to update, and the reader cannot tell the two entries are one link.

**Only two, because only two fit.** At `lg` the row has ~880px free — both slot children
are `lg:hidden` on the home page and search has moved to the rail. Six inline icon+label
destinations cost ~960px in `es` (`Unirse al servidor de Discord` alone is ~174px of text),
and `ja` and `th` are comparable, so "no three-dots menu on desktop" is not available at
`lg` in seven languages. GitHub and Discord are the two whose brand mark identifies them
without a label, so they are the two that can go icon-only; the other four need their words
and keep the menu alive. At `xl` all six would fit, at the cost of leaving 1024–1279px —
iPad landscape — on the old layout.

The count is not the criterion and never was; D21's real line is a *kind* test, view
controls used repeatedly while browsing against destinations used once. The menu used to
draw that line by being a separate surface. Inline, a divider draws it.

Two consequences worth stating. The Discord link is conditional on `/api/info`, so in the
header it would pop in mid-load and shift every control left of it — it reserves an inert
`size-9` slot instead, which the menu does not need because a shut dropdown has no visible
shift. And the six header strings were absent from `contract.test.ts`'s sweep, present in
all seven locales by luck rather than by test; promoting two of them to the accessible name
of an icon-only button raises what a miss costs, so all six are now swept.

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
- **Nine bugs were found by specifying this**, all pre-existing. Six are shippable fixes;
  three were ruled `wontfix` by the maintainer on 2026-07-31 — [#50](https://github.com/tskrlabs/hololive-ocg-wiki/issues/50)
  (a wiki is not a legality validator), [#41](https://github.com/tskrlabs/hololive-ocg-wiki/issues/41)
  (Worker-first on every navigation costs invocations; card URLs are covered by D7 alone),
  and [#56](https://github.com/tskrlabs/hololive-ocg-wiki/issues/56) (the disclaimer quotes
  an English-language policy). The full list: [#40](https://github.com/tskrlabs/hololive-ocg-wiki/issues/40),
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
- **D18's amendment found two bugs that had shipped inside the rework itself**, both
  invisible to `make check` and both of the same kind — a value crossing a boundary that
  no pure test could see (D24). The deck drawer was modal at every width, so the decision
  it implemented was never the decision that ran; and the panel's card grid was keyed on
  the viewport while living in a fixed-width panel, so it rendered 30px tiles under 32px
  buttons. Two mounted tests now cover them, and the second is verified to fail against
  the original markup.

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

**A committed JP fingerprint file, or dated raw-scrape snapshots in R2** (D26). Both were
real options for the source baseline. The file is the artifact that can desynchronise from
the database — which is the argument `schema.sql` already makes for keeping the hashes in
a column — and it makes every scrape a commit. The R2 snapshot is 8.5 MB per run and buys
field-level attribution ("the ability text changed") that nothing on the page would show.
A column rides the read-back the seeder already performs.

**Independent buckets in `SeedPlan` itself** (D26), rather than separate report sets. Fewer
concepts, but it changes the meaning of `counts.changed` and `counts.qa_updated` that have
already shipped, and `to_write` would have to dedupe or write a card twice.

**A maintainer-written update note** (D26). It could say "re-translated through a
content-addressed cache" in words no derivation will produce. Rejected as v1's stale-prose
bug: it is correct only until the next seed nobody remembers to annotate.
