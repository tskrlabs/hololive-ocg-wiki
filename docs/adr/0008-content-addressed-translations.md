# ADR 0008 — Content-addressed translations

**Status:** accepted
**Date:** 2026-07-30
**Supersedes:** [ADR 0002](0002-field-level-translation-cache.md)'s cache key
**Closes:** [#20](https://github.com/tskrlabs/hololive-ocg-wiki/issues/20),
[#21](https://github.com/tskrlabs/hololive-ocg-wiki/issues/21), and the mechanism half of
[#18](https://github.com/tskrlabs/hololive-ocg-wiki/issues/18)
**Tracked in:** [#23](https://github.com/tskrlabs/hololive-ocg-wiki/issues/23) ·
plan in [`docs/translation-rework-plan.md`](../translation-rework-plan.md)

## Context

ADR 0002 keyed a translation on `(locale, card_id, field_path)`. That was right about
*granularity* — a changed Q&A entry should not re-translate a card's name — and wrong
about *identity*. The same Japanese string printed on five cards was translated five
times, independently, and came back five different ways.

Measured over the real 2,463-card build:

| field | distinct JA strings | divergent in `en` |
|---|---:|---:|
| card name | 296 | 83 (28%) |
| art name | 926 | 362 (39%) |
| keyword name | 537 | 181 (34%) |
| skill name | 168 | 52 (31%) |
| effect prose | 1,305 | **1,055 (81%)** |

Shirakami Fubuki's 44 cards carried two different `en` names. Two cards printing
word-for-word identical rules text read differently in English.

**The prompt was the proximate cause and could not be fixed by better wording.** Every
prompt in `prompts.json` said *「所有名稱皆保留原文，不用翻譯」* — do not translate names.
The model complied 47–81% of the time, unpredictably. A year of prompt tuning had not
made that reliable, and no further tuning would: a request the model *can* ignore is a
request it will sometimes ignore.

## Decision

Twelve decisions, taken in sequence during a design interview. Each depended on the one
before it.

### D1 — Consistency is enforced in the pipeline, not the frontend

A frontend glossary could fix card names. It could not fix 926 art names, 537 keyword
names, or 1,305 effect strings — and it would leave D1's search index disagreeing with
what the page displays.

### D2 — The cache key is `(locale, kind, sha256(source))`

Content-addressed, with the **field kind** in the key. Only 15 of 3,893 distinct strings
appear under more than one kind, so the dedupe cost is negligible; what the split buys is
a prompt per kind. An art name is a title that should stay punchy; an effect is rules
text that should use the locale's established vocabulary. One prompt covering both is the
compromise v1 made.

This is the decision that makes #20 and #21 **unrepresentable rather than corrected**.
One string has one slot. There is no arrangement of the data in which two cards disagree.

### D3 — Prose is content-addressed too, not just labels

Prose was the worst-affected field and appears in neither issue. Excluding it would have
left 1,055 divergent `en` effect strings — the largest instance of exactly the defect
being fixed.

Accepted consequence: the first card to introduce a sentence wins it for every card. That
is correct for a TCG, where identical printed rules text *should* read identically, but
there is no per-card escape hatch.

### D4 — The existing cache is discarded, not migrated

Re-keying the 82,098 entries by content produces 3,942 slots in `en`, of which **2,277
(58%) hold conflicting values**. Only 271 are the easy `{source, one translation}` case;
the other 2,006 have two or more genuinely different translations and no rule picks
between them. Any picker is a coin flip enshrined as the canonical answer.

`conflict_census` is kept as code rather than as a claim in this document, because a
future refresh could change the answer.

### D5 — The translation unit is the string, not the card

Prose carries a small reference-only context block (card name, art name) instead of the
whole card. `そのホロメン` is ambiguous without knowing whose card it is; a whole card is
6× the tokens for context three lines supply.

### D6 — Q&A is excluded from the cold run

596 units, but **62% of the source corpus by character count**. It is the least read
(a detail panel), the Japanese is authoritative anyway, and re-doing it dominates the
bill. Existing translations are migrated with a winner picked by rule and marked
`source: "legacy"` — a third provenance beside `machine` and `manual`, so a later pass
can find exactly these rather than guessing which are old-prompt output.

### D7 — Names are masked out, not asked about

The mechanism the whole rework turns on:

```
白上フブキのこんこん  →  [[N0]]のこんこん  →  [[N0]]'s Konkon  →  Shirakami Fubuki's Konkon
```

The model never sees a name, so it cannot render one two ways. Three rules, each forced
by the data: **longest first** (75 pairs in the real table nest), **katakana word
boundaries** per occurrence (`トワ` is Tokoyami Towa *and* the first two syllables of
`トワイライト`), and **one pass** (a token is ASCII and so is `35P`, so a second pass could
match inside a token it just wrote).

**Failure is loud.** A dropped, mangled or invented placeholder raises, and the unit is
not cached. A half-restored string would be plausible, published, and found by a reader
months later.

### D8 — `pipeline/glossary/` is the source of truth for proper nouns

Committed and reviewable: 296 names, 35 sets, 41 tags, keyed on the source string. Three
consumers read it — `translate` masks with it, `build` labels dropdowns from it, and the
site's i18n maps are **generated** from it with `make check` guarding drift.

This is the reviewable translation surface #18 asked for.

### D9 — Dual-read during the migration

A unit missing from v2 falls back to the per-card cache, so a build is always complete
and a locale ships when it is ready rather than all six landing together.

### D10 — `LocalizedCard.original` carries the source labels

Labels only, and only where they differ. Measured: +9.3% in `en`, +11.6% in `tc`, **+0%
in `ja`**. Returning every source field would have cost +69%.

### D11 — Calibrate before spending, pilot before committing

A small run to test the prompt design, then one locale end-to-end to measure real cost
before the other five. Both gates were real: calibration disqualified `gpt-5.4-mini` and
found two design gaps, and the pilot's measurement is what made the remaining five a
decision rather than a guess.

### D12 — The glossary carries aliases, with their own translations

`おつルーナ` was rendered "OtsuLuna" in calibration because only the full name `姫森ルーナ`
was a key. Aliases fix that. They carry *their own* per-locale text because restoring
every alias to the full canonical name flattens register — an end-to-end run produced
"Mococo Abyssgard and Donut Cooking" where the Japanese reads like a nickname.

Deriving the short form mechanically does not work: `白上` and `フブキ` are both aliases of
one character and map to **different halves** of "Shirakami Fubuki".

## Results

Divergence in `cards.json` — the artifact the site is built from:

| field | distinct | en | tc | ko | es | th | id |
|---|---:|---:|---:|---:|---:|---:|---:|
| card name | 296 | **0** | **0** | **0** | **0** | **0** | **0** |
| art name | 926 | **0** | **0** | **0** | **0** | **0** | **0** |
| keyword name | 537 | **0** | **0** | **0** | **0** | **0** | **0** |
| skill name | 168 | **0** | **0** | **0** | **0** | **0** | **0** |
| effect prose | 1,305 | 12 | 14 | 11 | 11 | 15 | 13 |

The residual on prose is **D2 working as designed**: exactly 15 source strings appear
under two field kinds — the same sentence as both an art effect and a keyword effect —
and the kind is part of the key. Measured at 15 when D2 was taken, still 15.

**Cost.** 1,493,321 tokens across six locales, ~356k points, **0 failures**. 204 API
calls for a full cold run, against 14,778 under the per-card scheme — the old code sent
one card per request *per locale*.

## Consequences

- **ADR 0002's key is superseded; its reasoning is not.** Granularity, `manual`
  durability, and "only stale fields are read back" all survive at unit granularity.
- **`prompts.json` is retired** in favour of per-kind prompts in `prompts_v2.py`. The
  Chinese framing is kept deliberately: rewriting v1's prompts in English would be a
  silent change to translation quality dressed as a refactor.
- **The cache is no longer the only unbacked artifact.** `holo-data backup-cache` covers
  both caches, verified by loading the copy back.
- **Two caches exist until the last locale migrates.** All six are at 100%, so the
  fallback is now dead code kept for the next locale added.
- **Three defects were found by doing this and are open, not hidden:**
  [#27](https://github.com/tskrlabs/hololive-ocg-wiki/issues/27) (`「…」` quotes and `〈〉`
  normalisation), [#28](https://github.com/tskrlabs/hololive-ocg-wiki/issues/28) (game
  vocabulary is inconsistent inside prose — `エール` is three words in Thai), and
  [#29](https://github.com/tskrlabs/hololive-ocg-wiki/issues/29) (the card list has no
  names, so `original` costs +9.3% on responses that cannot display it).
- **#18's mechanism half is closed; its general case is not.** The glossary is a
  reviewable surface for *proper nouns*. A correction to an arbitrary effect string still
  has no committed home, because the cache remains gitignored and 24 MB.

## What this cost, and what it bought

Eight phases. ~1.54M tokens including calibration. 157 new tests (206 → 363).

What it bought is not "better translations" — it is a property. Before, consistency was
something you could measure and lose. Now two cards printing the same Japanese cannot
disagree, because there is nowhere for a second answer to live.
