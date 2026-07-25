# Architecture Review — v1 frontend, candidates for v2

**Date:** 2026-07-24
**Status:** 📋 Carried over from the v1 repo. Scheduled for **Phase 5** of [`v2-plan.md`](./v2-plan.md).
**Visual version:** [`architecture-review-v1.html`](./architecture-review-v1.html) (open in a browser — before/after diagrams per candidate)

> **Provenance.** This reviews the **v1** codebase at
> `/Users/chingli/lichingchester/projects/hololive-ocg-wiki`. All file paths below are
> relative to *that* repo. In v2 the frontend lives at `apps/web/`.
> Per decision D13, the v2 website scope is exactly these four candidates plus the
> dead-code purge — no new features, no redesign.

Surfaced via the `improve-codebase-architecture` skill. Framing/vocabulary from the
`codebase-design` skill: **module · interface · depth · seam · adapter · leverage · locality**.
A *deep* module = a small interface over a lot of behaviour; a *shallow* module = an interface
nearly as wide as its implementation. The goal of every candidate below is to collapse shallow,
duplicated modules into deep ones — for testability and locality.

No `CONTEXT.md` or ADRs exist yet, so nothing here re-litigates a recorded decision.

---

## Context: two half-finished migrations

The friction in this codebase traces to **two schema/store migrations that were left half-done**:

1. **Card store:** a legacy client-side JSON store (`useCardStore`, Fuse.js over `cards_i18n.json`)
   was superseded by an API store (`useCardStoreAPI`, hitting the Cloudflare Worker at `/api/*`).
   The legacy half is now **dead but still runs at boot**.
2. **Card schema:** an old camelCase + `translations`-map `Card` shape was replaced by the current
   flat snake_case `Card` (`types/card.ts`). The old shape survives only in dead code and commented-out types.

Everything below is downstream of these two forks.

---

## Candidate summary

| # | Candidate | Strength | Dependency category |
|---|-----------|----------|---------------------|
| 01 | Unify the two card-query stores behind one interface | **Strong** | ports & adapters |
| 02 | Deepen the Filter module — one home for the filter shape | **Strong** | in-process |
| 03 | Model the Deck as sections, not three parallel arrays | **Strong** | in-process |
| 04 | One `useDeckCards` view-model for the deck lists | Worth exploring | in-process |

**Tackle first: Candidate 01** — it's the root the other duplication grows from.

---

## Candidate 01 — Unify the two card-query stores behind one interface

**Strength:** Strong · **Category:** ports & adapters (remote-but-owned Cloudflare API)

**Files**
- `composables/useCardStore.ts` (13.3 KB, client JSON + Fuse) — **dead**
- `composables/useCardStoreAPI.ts` (19.9 KB, HTTP) — **live**
- `plugins/cards.ts` — boots the dead store at startup
- Forked view pairs:
  - `components/filter/Filter.vue` (dead) ↔ `FilterAPI.vue` (live)
  - `components/filter/SearchInput.vue` (dead) ↔ `SearchInputAPI.vue` (live)
  - `components/card-list/CardListView{,Basic,VirtualScroller}.vue` (dead) ↔ `CardListViewAPI{,Basic,VirtualScroller}.vue` (live)

**Problem.** "Card query" has two interfaces, so nearly every consuming view exists twice. The
legacy copies have already gone dead — but the dead store still costs on every load.

**Solution.** One `useCardQuery` interface (`getFilteredCards`, `getCardById`, `search`,
`filterOptions`). The data source becomes an internal adapter — an HTTP adapter in production and
an in-memory adapter in tests (two adapters justify a real seam). Delete the dead legacy store and
its unreferenced views.

**Wins**
- leverage: one interface, ~14 call sites
- locality: query logic in one module
- two adapters justify the seam (prod HTTP + test in-memory)
- delete ~6 unreferenced view files
- stop importing 8 MB (`cards_i18n.json`) at every boot
- the interface becomes the test surface

**Evidence (deletion test says "delete")**
- Live page renders only API variants: `pages/index.vue:37` (`FilterAPI`), `:40` (`SearchInputAPI`), `:45` (`CardListViewAPI`).
- The four legacy views + `Filter.vue` are **unreferenced** (no template mounts them).
- `plugins/cards.ts:3,7` calls `useCardStore().loadCards()` and `provide`s `$cardStore` — **nothing reads `$cardStore`**.
- `useCardStore.ts:134` dynamic-imports `@/data/cards_i18n.json` (~8 MB) at boot; result unused by the UI.
- Live store: `useCardStoreAPI()` used in 9 files (`CardListViewAPI*`, `SearchInputAPI`, `DeckDetail*`, `FloatingDeckCardList`, `CardDataQnaBlocks`, `CardDataSameNumberBlock`).

**Note.** Within `useCardStoreAPI.ts` the filter→params mapping is itself duplicated:
`getFilteredCards` (`:218`) and `loadMoreCards` (`:609`) each rebuild the full
colors/cardTypes/rarity/bloomLevel extraction. That duplication is retired by Candidate 02's `toApiParams`.

---

## Candidate 02 — Deepen the Filter module (one home for the filter shape)

**Strength:** Strong · **Category:** in-process (pure)

**Files:** `composables/filter-states.ts` · `types/filter.ts` · `constants/card-data.ts` · `composables/useCardStoreAPI.ts`

**Problem.** The filter's shape (colors / cardTypes / rarity / bloomLevel) is written out in **three
incompatible forms**, and the empty-filter literal appears **five times**. `filter-states.ts`
exposes ~25 methods over a thin body — a shallow module. Adding one rarity means editing ~6 places.

**Solution.** Derive the shape from a single source of truth (the domain enums). One
`createEmpty()`, one `toApiParams(filter)`, one `isActive(filter)`; collapse the per-field resets
into `clear(section?)`. Keep the genuinely-useful draft ↔ applied distinction.

**Wins**
- locality: the shape lives in one place
- interface shrinks — ~14 reset methods → one `clear`
- kills the bloom-level naming mismatch (see below)
- one `toApiParams`, not three copies
- pure module, tested directly
- drop the legacy `resetName/Tag/...` aliases

**Evidence**
- Shape in 3 forms: `types/filter.ts` (object-of-booleans) · `constants/card-data.ts`
  (`COLORS`/`CARD_TYPES`/`CARD_RARITIES`/`CARD_BLOOM_LEVELS` arrays) · inline `{white:false, …}` literals.
- Empty-filter literal duplicated **5×**: `filter-states.ts:7-58` (`filterState`), `:64-115`
  (`draftFilterState`), `:132-183` (`reset`), `:196-247` (`resetDraftAll`); plus `useCardStoreAPI.ts:116-167` (`loadCards` default).
- Shallow interface: `filter-states.ts` returns ~25 members incl. 7 `resetDraftX` + 7 legacy `resetX` aliases.
- **Latent bug:** `constants/card-data.ts:60` says `CARD_BLOOM_LEVELS = ["debut","1st","2nd","spot"]`
  but the type/filter use `debut/first/second/spot`. The two spellings only coexist because the enum is written twice.
- No `.vue` component hand-rolls the filter shape (both `Filter.vue` and `FilterAPI.vue` iterate composable state) — so the fix is composable-local.

---

## Candidate 03 — Model the Deck as sections, not three parallel arrays

**Strength:** Strong · **Category:** in-process

**Files:** `composables/decks-states.ts` · `types/deck.ts` · `pages/deck/[code]/index.vue` · `components/parials/FloatingDeck.vue`

**Problem.** A deck is three arrays (`oshiCardIds` / `mainCardIds` / `yellCardIds`), so `add` /
`remove` / `removeAll` / `count` each fork three ways. Worse, the **size rules (1 oshi · 50 main ·
20 yell) have no home** — they're magic numbers hardcoded in templates, with the status-colour
ternary copied 6× across two files.

**Solution.** A deep `Deck` module keyed by section. Callers pass a card (or `cardTypeCode`); the
module routes it to the right section and enforces the limits behind the interface. Expose
`add(card)`, `remove(card)`, `count(card)`, `status(section)`.

**Wins**
- locality: bucket + limit rules in one module
- each op written once, not three times
- limits stop leaking into templates
- leverage: `status()` reused by both deck views
- validation testable through the interface
- adding a section becomes a one-line change

**Evidence**
- Triplicated bucket branching in `decks-states.ts`: `addCardToDeck` (`:120/127/134`),
  `removeCardFromDeck` (`:169/192/215`), `removeAllCardFromDeck` (`:256/261/266`), `getCardCount` (`:291/298/304`).
- Deck modelled as three arrays: `types/deck.ts`.
- **No validation in the store** — `decks-states.ts` never caps additions.
- Size limits + status colour hardcoded and duplicated:
  `pages/deck/[code]/index.vue:128-137` (`/1`), `:155-164` (`/50`), `:182-191` (`/20`)
  and near-verbatim in `components/parials/FloatingDeck.vue:103-112`, `:129-138`, `:155-164`.
- Three-array split leaks structurally into views: `FloatingDeck.vue:32-41`,
  `DeckDetailCompactModeCardList.vue:5-7`, `pages/deck/[code]/index.vue:113-196`.

---

## Candidate 04 — One `useDeckCards` view-model for the deck lists

**Strength:** Worth exploring · **Category:** in-process

**Files:** `components/parials/FloatingDeckCardList.vue` · `components/detail-page/DeckDetailCardList.vue` · `components/detail-page/DeckDetailCompactModeCardList.vue`

**Problem.** Three deck-list components each re-derive the same pipeline — count duplicate ids →
dedupe → fetch cards → join → resolve `image_path` — two of them verbatim, the third as a
hand-rolled `Map` variant applied three times over.

**Solution.** A deep `useDeckCards(cardIds)` that returns `{ card, count }[]` plus `loading`. The
three components render it and stop deriving.

**Wins**
- leverage: one module, three views
- count + join written once
- `getImagePath` stops being copied
- fetch/watch boilerplate absorbed
- locality: derivation bugs land in one place
- the join is tested through the interface

**Evidence**
- `uniqueCardIds` (count → `{id,count}[]`) verbatim in `FloatingDeckCardList.vue:18-25` and
  `DeckDetailCardList.vue:14-21`; `Map` variant in `DeckDetailCompactModeCardList.vue:18-50`.
- `uniqueCards` (join counts with fetched cards, filter nulls): `DeckDetailCardList.vue:24-39` ↔ `DeckDetailCompactModeCardList.vue:18-50`.
- `getImagePath(cardId)` verbatim in `FloatingDeckCardList.vue:72-78`, `DeckDetailCardList.vue:64-70`, `DeckDetailCompactModeCardList.vue:110`.
- Fetch/watch boilerplate duplicated: `FloatingDeckCardList.vue:27-49` ↔ `DeckDetailCardList.vue:41-61`.

---

## Other notes for v2 (not full candidates)

- **Two card schemas coexist.** Snake_case flat `Card` is live for cards/decks; the **status feature
  uses a separate camelCase shape** (`cardNumber`/`imagePath`) — `components/status/*`, `pages/status.vue`.
  Worth deciding whether status should share the `Card` type or stay a distinct read model.
- **Dead types.** The commented-out `Translations`/`Translation` types (`types/card.ts:79-93`) are unused — delete on v2.
- **Repo data weight.** `data/` holds four large JSON snapshots (`cards.json` 22 MB, `cards_i18n.json`
  8 MB, two dated 18 MB snapshots). Only `cards_i18n.json` is imported (by the dead store). Clarify
  which are build inputs vs shippable and whether they belong in git.
- **Deck-code serialization** (`getDeckCode`/`checkForDeckCode`/`compress`/`expand`/`btoa`/`atob` in
  `decks-states.ts`) is a self-contained pure transform welded into the state composable. Extracting a
  pure `deckCode.encode/decode` module would make the round-trip testable without `window`/`localStorage`/`useI18n`.
  (Dropped from the top-4 in favour of 04, but a good small win.)
- **Asset convention** `/icons/type_${key}.png` is repeated in `FilterAPI.vue:403`, `Filter.vue:352`, `CardDataRowsBlock.vue:86`.

---

## How to resume

These candidates are **Phase 5** of [`v2-plan.md`](./v2-plan.md) — tackle them when porting the
frontend into `apps/web/`, after the schema, pipeline, and API have settled. Several notes below
are already resolved by v2 decisions:

- *"Repo data weight"* → resolved by **D1**: data moves to R2, out of git entirely.
- *"Two card schemas coexist"* → resolved by **D5**: `packages/schema/` becomes the single contract.
- The `image_path` / `getImagePath` duplication → resolved by **D9**: one `cardImage(key)` helper.

Start with Candidate 01 — it's the root the other duplication grows from.
