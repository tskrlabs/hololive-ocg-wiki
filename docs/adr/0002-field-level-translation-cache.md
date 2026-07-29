# ADR 0002 — Field-level translation caching

**Status:** accepted
**Date:** 2026-07-26
**Phase:** 1
**Amends:** D14 (corrections overlay), D11 (`status.json` ownership)

## Context

v1's translator computed one SHA-256 of the **entire** JP card into `_source_hash`, and
sent the entire card to the Poe API in one prompt. Any change to any part of a card
invalidated the whole thing, re-translating its name, tags, every art, every skill and
every Q&A entry.

Measured across v1's three dated snapshots (2026-04-26 → 2026-05-28 → latest), over the
2,131 cards common to all three:

| What changed | Cards affected |
|---|---|
| JP `qa_items` | 37–39 |
| JP `arts` | 2 |
| JP `name` | 2 |
| JP `keyword` / `tags` / `oshiSkill` | 0–1 each |
| `cardSets` (base field, never translated) | 766 |

**A card's printed text does not change once published. Q&A is the only real churn.**
So v1 re-translated roughly 50× more than necessary, and the maintainer had been
carrying that cost for a year without a mechanism to avoid it.

Separately, D14 proposed a `corrections/` overlay so a bad translation could be fixed by
PR. v1's `7-manual-translate.py` / `8-replace-manual-to-card.py` groped toward this, but
**the maintainer never used them** — they handled only three vocabularies (`names`,
`tags`, `sets`) and were considered a bad implementation.

## Decision

### Hash per translatable unit, not per card

The cache keys each translatable field independently:

```
{card_id}.name              → sha256(JP source) → translated value
{card_id}.arts[0].effect    → …
{card_id}.qa_items[2]       → …
```

A changed Q&A entry invalidates that entry alone. Q&A entries hash as a whole
(title + question + answer together) because they are one unit of prose; splitting them
would let a title fix desync from its answer.

### The prompt is unchanged; only stale fields are read back

The whole card still goes into the prompt — the prompts in `prompts.json` are verbatim
from v1 and encode a year of tuning about what must *not* be translated. Context matters
for pronouns and terminology, so translating a lone `arts[0].effect` risks quality.

The whole card still comes back, too. **Only stale fields are extracted from the
response; everything else is discarded.**

That last part is what makes corrections work, and it is stronger than asking the model
for a subset would be. When a card is re-sent because its Q&A changed, the model also
returns a `name` — and we throw it away, because `name` is fresh in the cache. **The
cache, not the model, decides each field's value.**

### Corrections are cache entries, not an overlay

A manual fix is an entry with `source: "manual"`. As long as the JP source hash still
matches, the field is never stale, so nothing overwrites it — there is no merge step to
get wrong and no ordering to remember.

This **supersedes D14's `corrections/` overlay** and drops scripts 7/8 entirely. The
terminology problem those scripts addressed largely dissolves too: proper nouns live in
`name` and `tags`, which stop being re-translated once corrected.

## Consequences

**Measured on the real dataset** (2,448 cards, cache seeded from v1's translations):

- 2,228 of 2,448 cards need no translation at all
- invalidating one Q&A entry queued exactly one additional card
- the residual 336 cards are fields v1 never translated (`timing` on ~127 skills, some
  tags) — not churn

**Costs and limits**

- Cache format changes need a version bump; `TranslationCache.load` refuses an unknown
  version rather than silently re-translating everything.
- Field keys are positional (`qa_items[2]`). If the official site ever *inserts* a Q&A
  entry rather than appending, every subsequent entry looks stale and gets re-translated
  once. Entries are dated and appended in practice, so this has not occurred.
- No output-token saving on cards that do change. The saving is entirely from skipping
  unchanged cards, which is where the waste was.

## Other Phase 1 decisions

### Parsing moves verbatim, plumbing is rewritten

The BeautifulSoup selectors in `scrape/extract.py` and the HTTP/retry logic in
`scrape/fetch.py` are character-for-character from v1. That code encodes a year of the
official site's quirks, is untestable except against live HTML, and fails *plausibly*
when wrong. Everything around it — path handling, config, CLI, logging — was rewritten.

This was validated: all 2,448 cards parse, transform and validate against the contract,
and `holo-data verify` reports **zero base-field differences** against v1's published
data.

Three bugs were caught this way during the port, all in the rewritten layer:

1. The 特攻 (bonus damage) icon appears in `cost_icons` as well as `tokkou`, so mapping it
   as a colour produced `unknown` on 482 cards.
2. A keyword's *type* is its icon's `alt` text; `name` is the ability's own title.
   Reading `name` dropped the keyword from all 1,124 cards that have one.
3. The 特攻 alt text is `紫+50`, not `紫`, so the colour lookup needed splitting — without
   it, every special art silently lost its `special_targets`.

### `cost_count` keeps v1's arguably-wrong value

v1 counted every icon including 特攻, so `cost_count` can exceed `len(cost_types)` by one.
A bonus-damage marker is not a cost, so this looks like a v1 bug — but it is the number
the live site has shipped for a year, and Phase 1's criterion is data equivalence, not
correction. Flagged for a separate decision.

> **Decided in Phase 6 — the field was dropped, not corrected.** A census found no reader
> anywhere in the codebase, and `len(cost_types)` already carries the same fact. See
> [F-002](../archive/findings.md#f-002). This paragraph records what Phase 1 decided and stands as
> written.

### WebP conversion is its own command

Nothing in v1 produced WebP; the pipeline downloaded PNGs and the WebP files in the v1
repo came from some step outside it. D9 requires WebP-only uploads, so `holo-data images`
is new.

Kept separate from `scrape` and `publish` because all three are independently
re-runnable, and because `publish` reading only `images/webp/` makes "PNG stays a local
intermediate" structural rather than a rule to remember.

Quality **90**, chosen by the maintainer. Measured over 25 real cards:

| | avg/card | full 2,500 | R2 free tier |
|---|---|---|---|
| PNG source | 318 KB | 776 MB | — |
| q80 | 114 KB | 278 MB | 2.8% |
| **q90** | **174 KB** | **425 MB** | **4.3%** |
| q100 | 303 KB | 739 MB | 7.4% |

Conversion goes via RGBA: several card PNGs are palette-mode with transparency, and a
direct `convert("RGB")` would put black behind transparent regions.

### `verify` is permanent

It diffs a build against v1's `cards.json`, normalising the expected differences
(snake_case keys, stripped `_source_hash`, `image_key` for `image_path`, and absent-vs-
empty) so it reports real drift only.

Kept rather than deleted once green: it is the only tool that answers "did a site change
break my scraper?" against a known-good 2,448-card baseline. The baseline is passed with
`--baseline` rather than committed — 22 MB of superseded data does not belong in git, and
an outside contributor cannot run `scrape` anyway (D14).

## Amendments to the v2 plan

- **D14** — the `corrections/` overlay is superseded by field-level caching. Same goal
  (a bad translation is fixable and survives the next run), no separate merge layer.
- **D11** — `status.json` moves from `publish` to the seeder (**Phase 3**). It is
  currently written by `cloudflare/migrate.js`, not the pipeline, and describes a
  *database diff* (`mode: "diff"`, `source: {total, valid}`) — knowledge `publish`
  cannot have.
- **Phase 1 done-when** — "reproduces today's `cards.json` shape" → reproduces today's
  card **data**. Already recorded in ADR 0001; restated here because this is the phase it
  applies to.

## Notes for later phases

- **Phase 2** — `publish` uploads `images/webp/` and `build/cards.json`. Adopt the
  `{set}/{filename}` image key scheme; `CardCollection` already enforces its uniqueness.
- **Phase 3** — `seed` writes `status.json`. Note v1's version uses a camelCase shape
  (`cardNumber`, `imagePath`) that predates the contract; decide whether to model it or
  keep it as a distinct read model.
- **First real run** — the cache starts empty, so a fresh `translate` would be a full
  one. Seed it from v1's `cards.json` first; the import is ~20 lines and recovers a
  year's worth of translations (81,124 field entries when tested).
