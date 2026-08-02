# ADR 0010 — Set-code filtering, and the search index behind it

**Status:** accepted
**Date:** 2026-08-02
**Fixes:** [#66](https://github.com/tskrlabs/hololive-ocg-wiki/issues/66) (search 500s
above 100 matches), [#67](https://github.com/tskrlabs/hololive-ocg-wiki/issues/67) (Q&A
dominates the index)

## Context

The prompt was a user observation: people want to look up a set directly, by typing
`hBP03`. Checking what that does today turned up two live defects underneath it, so this
ADR covers three things — the two bugs, and the feature that motivated finding them.

**`hBP03` in the site's search box returned HTTP 500.** Not a poor result — a server
error, on the endpoint the search box actually calls. D1 caps a query at 100 bound
parameters, and both `buildWhere` and `cardsByIdsSql` expanded the FTS id list into
`id IN (?, ?, …)`, one placeholder per id. Every query matching more than 100 cards
failed, which is to say the popular ones: `hBP03`, `hBP01`, `ホロメン`, `エール` all 500'd
while `hSD01` (65 matches) and `白上フブキ` (73) worked. `/api/cards/search?limit=101`
failed at exactly the same boundary.

**Set code is not a dimension we have.** The `set` filter is over 35 *product names*
(`ブースターパック「エリートスパーク」`). The set code is a different taxonomy, and the two do
not line up: hBP03 is 283 cards, the "Elite Spark" product is 244, and only 229 are both —
the rest are `hY0x` cheer cards bundled into the product, while 54 hBP03-numbered cards
appear only in PR, Wafers or the Selection Cup. The [official card list][official] keys
its `?expansion=` on the code, and so does [Holoarchive][holo]. We had it only as a prefix
of `card_number`, reachable through free text.

**And free text is the wrong instrument for it.** `search_text()` folded Q&A into the same
FTS blob as names and abilities, across all 7 locales — 88% of the indexed text by volume.
`ORDER BY rank` weights every column equally, so a card whose FAQ merely *cites*
`hSD01-001` scored like the card numbered `hSD01-001`. Production returned 65 cards for
`hSD01` of which 39 were hSD01. Names diluted the same way: 29 of 73 `白上フブキ` hits were
cards that only mention her, 33 of 72 for `さくらみこ`.

[official]: https://en.hololive-official-cardgame.com/cardlist/cardsearch/?expansion=hBP03
[holo]: https://holoarchiveocg.com/

## Decisions

### The 100-parameter ceiling

**D1. An id set travels as one JSON parameter, through `json_each`.**
`id IN (SELECT value FROM json_each(?))` — the count stops mattering because there is only
ever one binding. Verified against production D1, which supports the SQLite JSON
extension.

**D2. `IN (SELECT …)`, even though [#40](https://github.com/tskrlabs/hololive-ocg-wiki/issues/40)
replaced exactly that form with `EXISTS`.** The cases invert, and the reason is what can be
indexed. A junction table has `idx_card_*_card_id`, so a correlated `EXISTS` probes it per
card and the walk stops at `LIMIT`. `json_each` has no index at all, so the same
correlation rescans the array for every card considered. Measured on production over the
283 hBP03 ids:

| form | page (LIMIT 50) | `count(*)` |
|---|---|---|
| `IN (SELECT value FROM json_each(?))` | 1,132 rows | 849 rows |
| `EXISTS (SELECT 1 FROM json_each(?) …)` | 169,940 rows | 659,306 rows |

150× and 776× worse. **The rule #40 established is "correlate against something indexed",
not "always use EXISTS"** — and that distinction is the whole content of this decision.

The accepted cost is that this form materialises and sorts, so reads scale with the id set
rather than the page: 100 ids read 300 rows, 283 read 1,132. That is #40's shape, taken
knowingly, because the alternative is a broken endpoint and a search is one query per
debounce rather than the default view.

**D3. The filter path's 500-id cap is removed rather than raised.** It existed only to
bound the parameter count. While it stood it made `total` lie — a common word matches far
more than 500 of 2,463 cards, so the count under the search box reported the cap instead
of the answer.

### The search index

**D4. Q&A gets its own FTS column, and `bm25()` ranks card text above it.**
`bm25(cards_fts, 2.0, 1.0, 0.1)` over `(card_number, text, qa)`. The ratios are the ones
the models already declare via `FullText` — a name is 3.0, a Q&A field 0.5 — an annotation
that had never been able to act, because a trigram index cannot weight fields *within* a
column. The split is what makes the declared intent executable.

**D5. Q&A stays indexed.** Dropping it would fix the ranking and lose a real use: looking
up a ruling by its wording. A separate column keeps both — rulings still match, they just
cannot outrank the card.

**D6. The LIKE fallback searches both columns, card matches first.** It is the only thing a
1–2 character query has (`そら` is 2 characters and matches 27 cards). Restricting it to
`text` would have quietly narrowed short queries while the MATCH branch still searched
everything — a regression with no symptom.

**D7. Migration 0004 creates the table; the seeder fills it.** FTS5 rejects `ALTER`
outright (`virtual tables may not be altered`, verified on D1), so a new column means DROP
+ CREATE. Refilling it *in SQL* was tried and rejected: `json_tree(payload)` produces the
text but not the *same* text — it sweeps up enum codes like `once_per_turn` that
`search_text()` excludes, and cannot reproduce the ordering. The index would then be built
by one rule in the migration and a different one on every later seed, with the difference
invisible until somebody searched for `once_per_turn` and got 2,463 hits.

So `search_text()` / `qa_text()` stay the single definition of what is searchable, and the
migration does only the part that must be SQL. This is the same split ADR 0004 makes
between generated DDL and seeder content.

**D8. The seeder refuses to run against the pre-0004 shape.** A probe before the first
write, in the shape D26's `source_hash` guard already established: a D1 *batch* is atomic
but a *run* is not, so discovering the wrong shape mid-run leaves earlier batches
committed. It matters more here than for 0003, because 0004 leaves the index **empty** —
between the migration and the reseed the site has no search at all.

### Set code as a dimension

**D9. No stored column. The filter is a `card_number` range.**
`card_number >= 'hBP03-' AND card_number < 'hBP03.'`. `idx_cards_card_number` already
exists, and this is a seek over it — measured on production, `SEARCH cards USING INDEX
idx_cards_card_number` for the page and `SEARCH … USING COVERING INDEX` for the count. A
dedicated `set_code` column produces *the same plan* while costing a migration, a reseed,
and a seventh index write on every card. Verified that all 2,463 card numbers match
`PREFIX-DIGITS`, so the derivation never has to guess.

`LIKE 'hBP03-%'` was rejected for the same query at a worse plan: SQLite degrades it to a
scan, because it cannot prove a bound parameter is prefix-shaped.

**D10. The vocabulary ships in the filter-options artifact.** The 36 codes are data, built
beside `cards.json`, so they cannot describe a different card set than the one that
shipped — the same argument ADR 0004 makes for the other three dropdowns.

**D11. The code is its own label, in all seven locales.** Deriving a product name was
tried against the data and does not work: hBP07's most common product is "[Usable Cards]
Selection Cup" rather than "Diva Fever", every `hY0x` cheer code spans 11–15 products with
no majority (top share 18–42%), and `hBD24` and `hPR` appear in no official picker at all.
A hand-maintained map would drift with every release and still have no answer for those
two. The code is also what the card prints and what the user typed.

**D12. A new filter group, above the product-set group — not merged with it.** They are
different taxonomies (D9's numbers), so one control returning two different answer shapes
would be impossible to explain. They are AND'd, because "hBP03 cards that shipped in Twin
Wafers" is a coherent question that needs both.

**D13. Single-select**, matching the official site's `?expansion=` and the `set` group it
sits above.

### The search box

**D14. A typed set code applies the facet.** Exact, case-insensitive match against the
shipped code list. `hBP03` then means "show me hBP03" rather than "find text matching
hBP03", which also matches every ruling citing an hBP03 card. Verified against the fixture
set: free-text `hSD01` returns 11 cards including `hBP03-050`, which merely cites it, while
the facet returns exactly 10.

**D15. Exact match, not a pattern.** `hBP` is a prefix of nine codes and `hBP3` of none;
both stay ordinary searches, so a half-typed query keeps behaving as it does today rather
than becoming a confident empty result. Verified that no code collides with any card name
or tag, so nothing findable by name becomes unreachable.

**D16. The box empties and the facet fills.** One constraint in one place, clearable where
every other filter is cleared. Leaving the text behind would put the same constraint in two
places, where clearing either leaves the other — the split-state bug the draft/applied
separation exists to prevent.

### The URL

**D17. `?set_code=hBP03` — and it is the only filter with a URL.** Filter state is
otherwise in-memory only. Serialising all of them is its own design (defaults, encoding,
history depth, what a bare `/` means) and is not attempted here. Set code earns the
exception because "every card in hBP03" is the highest-value link a card wiki has after a
card page, and it is a single opaque token with no encoding questions.

**D18. `replace`, not `push`.** The set code is usually reached by typing, on a 500 ms
debounce — pushing would put one history entry per pause in typing, so Back would walk the
user through their own keystrokes.

## Consequences

**A full reseed was required and has run** (2026-08-02): 52,060 rows against an estimate
of 54,522, all 340 batches, database 19.9 MB → 56.8 MB. Search was down between the
migration and the reseed, which is inherent to D7 and the reason D8's guard exists.

**The deployed Worker kept working across the migration**, because `text` still exists —
verified on production before and after. Only the ranking waits on the deploy.

**`make check` gained a mounted test, and it immediately earned its place.** Clearing the
search box in the same tick as the input event means the child input's `modelValue` goes
`"hBP03"` → `""` within one render pass, so Vue reconciles against a value the DOM never
received and skips the patch: state empty, box still showing `hBP03`. Production's debounce
hides it today and any change to that debounce would expose it. This is the third wiring
bug — after [F-019](../archive/findings.md#f-019) and D18's two — that pure-function tests
could not see, and the first one caught *before* shipping rather than after.

**One number in this ADR is smaller than it looks.** `total` is now truthful for every
query, where it previously capped at 500. Nothing reports a different number than before
for queries under that ceiling; above it, the page now says what is actually there.
