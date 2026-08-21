# ADR 0013 — Dual colours are a pair, not a fused code

**Status:** accepted
**Date:** 2026-08-21
**Amends:** [ADR 0001](0001-card-contract-generation.md)'s `ColorCode`, and retires the
query-layer expansion F-016 added
**Closes:** [#22](https://github.com/tskrlabs/hololive-ocg-wiki/issues/22)

## Context

The official site spells a dual-colour card two different ways. FUWAMOCO and SorAZ get one
`<img alt="青赤">` of a pre-composited pair; miComet gets two separate `<img>` tags. v2
carried both spellings through: `blue_red` and `white_green` were their own `ColorCode`
values, while `["red", "blue"]` was an array.

**F-007 established that the split is not a fact about the game.** All three forms were
checked against the card images, and every one prints the same thing — two separate badges
on a gold ribbon. The difference is in the source HTML, nowhere else.

Keeping the two spellings cost three pieces of machinery:

- **A query-layer expansion.** A `blue` filter had to be widened to also match `blue_red`,
  or those cards silently vanished from their own colour (F-016). v1 had no expansion at
  all and its blue filter was quietly incomplete for a year.
- **A filter-UI exclusion list.** `FILTERABLE_COLORS` existed to keep the fused codes from
  getting checkboxes of their own, which would have been a second, worse way to find them.
- **A low-resolution icon.** `type_blue_red.webp` is **88×108** where all eight siblings
  are **330×410**, so it was scaled up into the same slot and rendered visibly softer
  (#22). The official site's own PNG is the same 88×108 — we faithfully carried a bad
  upstream export.

**A file size was mistaken for evidence.** F-007 and `enums.py` both once cited that 4.2 KB
against ~20 KB as proof that `blue_red` was a *fused single symbol*. It is not:
`white_green` is equally "fused" and is full-size, and the 88px asset is itself a picture
of two badges. An upstream export mistake shaped the contract's reading of the domain for
two phases.

## Decision

`transform` normalises `青赤` → `["blue", "red"]` and `白緑` → `["white", "green"]` at
extraction, and the two codes leave the contract. `mappings.COLOR` maps a source token to a
*tuple*, which is the one place the source's two spellings are reconciled.

### D1 — normalise at extraction, not at query time

Extraction is where the spelling difference exists, so it is where it should end. Every
layer downstream — D1, the Worker, the site — then sees one representation and needs no
rule about the other. This deletes the expansion rather than moving it.

### D2 — the stored order is the printed order

`["blue", "red"]` for FUWAMOCO, `["red", "blue"]` for miComet. Not sorted: the icons render
from this array, so sorting would silently reorder the badges on one of the two. Pinned by
tests in both languages and in the fixtures.

### D3 — the pair keeps its name

`青赤` is a colour identity the game names, so a card bearing it reads **"Blue-Red"**, not
"Blue, Red". `COLOR_PAIRS` maps the joined codes to that name, for display only, and the
`colors.blue_red` i18n keys survive in all seven locales although the codes do not.

Both orders map to one name — the pair is the same identity whichever way it is printed —
while the *stored* order stays as printed, because the two answer different questions.

This is the one deliberate visual change. A card that read "Blue-Red" beside one blurry
icon now reads "Blue-Red" beside two sharp ones.

### D4 — a dual-colour token in a single-badge slot is refused

`mappings.COLOR` also feeds cost icons, baton-touch and 特攻 targets, which hold exactly one
badge. `_one_colour` reports a two-code token there as unmapped rather than taking its first
half, because a silent half-answer in a cost list is worse than a loud unmapped report. No
such token occurs today; this is about what happens if the source changes.

### D5 — the icons are deleted, not redrawn

#22's Option A was compositing a 330×410 replacement. Rejected: it means shipping our own
redraw in place of official art, and the badges overlap at an offset a naive paste would
not reproduce. Normalising makes the asset unnecessary instead, so the question does not
have to be answered. `type_blue_red.webp` and `type_white_green.webp` are removed.

## Consequences

**The blur is unrepresentable rather than fixed.** There is no composite asset to be
low-resolution. A regression would have to reintroduce the file, which
`tests/color-pair.test.ts` asserts against directly.

**The colour filter is more correct with less code.** Verified against a real Worker and
local D1: all three `blue_red` cards return under both `blue` and `red`, SorAZ under both
`white` and `green`, `purple` matches none of them. `expandColors` is gone.

**Eight pinning tests were inverted.** Every one asserted a fused code stays fused, across
four packages and both languages. That is the expected shape of this change — the tests
guarded the behaviour being replaced — but it is also exactly where a rewrite can hide a
regression, so the replacements assert the *new* property against the real card images and
the real fixtures rather than restating the implementation.

**Two fixtures are now pinned that were previously coincidental.** Cards 1 and 2 were
selected by the greedy pass, and card 2 only because it covered `color=green` — which
SorAZ took over once it normalised to white+green. Card 1 is named directly by a dozen
smoke assertions and card 2 is the second `oshiCharacter`/`OSR`, without which the group-AND
check matches one row and stops distinguishing AND from OR. Depending on a coincidence for
fixtures that many tests name was the real defect there.

**This needs a reseed.** `color_code` is a populated D1 column; the build and artifacts are
regenerated but production still holds `blue_red` rows until `publish` and `seed` run. Data
goes live before the deploy, per the card-set runbook.
