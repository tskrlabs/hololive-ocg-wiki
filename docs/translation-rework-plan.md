# Translation rework — plan

**Status:** ✅ **complete** (2026-07-30), not yet deployed. Closed #20, #21, and the
mechanism half of #18. The decisions are recorded in
[ADR 0008](adr/0008-content-addressed-translations.md); this file is the design that
produced them, kept for the measurements it carries.

**Execution is tracked in [issue #23](https://github.com/tskrlabs/hololive-ocg-wiki/issues/23)**
— the nine-phase checklist and current state. This file is the design; #23 is where we are
in it. The two gated phases have their own issues: **#24** (prompt sign-off, before any bulk
spend) and **#25** (cost checkpoint, after the `en` pilot), with #25 natively blocked by #24.

The root cause behind #20 and #21 is one thing: **a translation is currently a property of
a `(card, field, locale)` triple, so the same Japanese string gets a different answer on
every card that carries it.** The prompt rule "don't translate names" was an attempt to
suppress the symptom, and the model obeys it 47–81% of the time — unpredictably, which is
the bug.

This plan makes a translation a property of the **source string** instead. Two cards
printing the same Japanese then cannot disagree, because there is only one slot to
disagree in.

---

## The measurements this rests on

All taken over the real 2,463-card build (`pipeline/build/cards.json`), 2026-07-30.

**Divergence today** — one JA string, ≥2 different `en` translations across cards:

| field | distinct JA | divergent in `en` |
|---|---:|---:|
| card name | 296 | 83 (28%) |
| art name | 926 | 362 (39%) |
| keyword name | 537 | 181 (34%) |
| skill name | 168 | 52 (31%) |
| effect prose | 1,305 | 1,055 (81%) |

Note prose is the worst affected and appears in neither issue.

**Dedupe available** — occurrences → distinct JA strings:

| kind | occurrences | distinct | saved |
|---|---:|---:|---:|
| tag | 5,481 | 41 | 99% |
| card name | 2,463 | 296 | 88% |
| art name | 1,991 | 926 | 53% |
| keyword name | 1,135 | 537 | 53% |
| skill name | 480 | 168 | 65% |
| **short labels** | **12,030** | **1,970** | **84%** |
| prose | 3,433 | 1,312 | 62% |
| qa_items | 1,914 | 596 | 69% |

**Corpus by cost** — 3,942 distinct units, 294 KB of JA (21% of the 1.42 MB whole-card
corpus):

| kind | units | chars | % |
|---|---:|---:|---:|
| **qa** | 596 | 177,006 | **60.2%** |
| keyword_effect | 524 | 32,345 | 11.0% |
| ability_text | 224 | 28,496 | 9.7% |
| art_effect | 405 | 20,781 | 7.1% |
| skill_effect | 167 | 11,061 | 3.8% |
| art_name | 926 | 10,879 | 3.7% |
| keyword_name | 537 | 6,189 | 2.1% |
| card_name | 296 | 2,645 | 0.9% |
| tags, skill_name, extra, timing | 267 | 4,546 | 1.6% |

**Q&A is 60% of the bill on its own** — which is why D6 excludes it from the cold run.

**Name-bearing labels** — of 1,631 distinct labels, 61 (4%) contain a full card name and
38 (2%) contain only a nickname/fragment. So the current "don't translate names inside art
names" rule is protecting ~6% of labels while freezing the other 94% that it was never
meant to touch.

---

## Decisions

| # | Decision |
|---|---|
| D1 | Consistency is enforced in the **pipeline** (content-addressed cache), with a committed glossary for overrides. Not frontend-only. |
| D2 | Cache key is **`(field_kind, sha256(ja_string))`**. Only 15 of 3,282 strings appear under >1 kind, so the dedupe cost is nil and per-kind prompts become possible. |
| D3 | Content-addressing applies to **prose as well as labels**. Prose is sent with a do-not-translate context block (D5). |
| D4 | The existing cache is **discarded and re-translated cold**, not migrated. Re-keying it produces 2,277 conflicting slots in `en` (58%), of which 2,006 have 2+ genuinely different translations and no principled winner. All 82,098 entries are `machine`; nothing hand-written is lost. |
| D5 | Translation unit is the **distinct string, not the card**. Prose units carry a small reference-only context block (card name, art name) instead of the whole card. |
| D6 | **Q&A is excluded from the cold run.** Its existing translations are migrated into the content-addressed cache with `source: "legacy"` so a later pass can find them. Keeps one key scheme; defers 60% of the bill. |
| D7 | Character names are **masked before sending and restored after** (`[[N0]]` tokens), rather than asked-not-to-translate. Applies to labels and prose alike, which also fixes the 1,228 `〈…〉` refs embedded in rules text. |
| D8 | The glossary moves to **`pipeline/glossary/`** as source of truth (names, sets, tags). `apps/web/i18n/locales/*.json`'s `names`/`sets`/`tags` maps become **generated** from it. This is the reviewable surface #18 asked for. |
| D9 | Migration is **dual-read during the transition** — the new cache falls back to the old on a miss — then collapses to new-only once every locale has landed. Lets locales ship one at a time across quota months. |
| D10 | `LocalizedCard` gains an **`original`** object carrying JA labels, emitted only where the localised value differs. +14% on a list response (~4.7 KB per 50-card page); powers the show-original toggle with no round-trip. |
| D11 | Calibrate with real API calls **before** building on the prompt design, then pilot **one locale end-to-end** before committing the rest. |
| D12 | The glossary carries **aliases** per character (`姫森ルーナ` → `ルーナ`), masked longest-first. Covers all 99 name-bearing labels instead of 61. |

### Calibration results (2026-07-30, 5 calls, ~2.7k tokens)

- **Masking round-trips cleanly.** `[[N0]]` came back intact in `en` and `tc` and restored
  from the glossary.
- **Per-kind prompts fix the untranslated-label problem.** `gpt-5.4` translated 8/8 art
  names and 4/4 keyword names with zero Japanese left behind, against today's 47–81%
  untranslated rate.
- **Independent convergence on the F-003 strings.** From a cold start the `tc` run produced
  `露娜辛苦了` for `おつルーナ` and `晚安安～` for `ぐっどないと～` — semantically the same
  answers as the four strings F-003 recovered, reached by a different path.
- **`gpt-5.4-mini` is disqualified.** It rendered `白上` as "Shirogane" (hallucinated — it
  is Shirakami) and `ユニーリア` as "Unilia". Everything uses the full model.
- **The nickname gap was found here.** `おつルーナ` → `OtsuLuna`, because `ルーナ` alone is
  not a glossary key. This is what D12 exists to fix.

---

## Phases

Each phase ends at a point where `make check` passes and the tree is shippable.

### Phase 0 — Protect what exists ✅ *done, 2026-07-30 — no API spend*

The 24 MB cache holding a year of API spend existed **only** on the maintainer's laptop:
`pipeline/locales/` is gitignored and the cache is not published to R2. Every later phase
assumes it can be restored.

`holo-data backup-cache [--remote]` now writes a dated snapshot to
`~/.holo-data/cache-backups/` — outside the repo, so `git clean -fdx` cannot take it — and
optionally a copy to `backups/` in the artifacts bucket.

Both copies are **verified by loading them back** and comparing per-locale entry counts,
not by comparing byte size: `save()` re-serialises, so a round-tripped cache is
semantically identical without being byte-identical, and a byte comparison would either
false-alarm or (worse) be skipped. A copy that fails verification is deleted rather than
left looking like a restore point.

**Verified state:** 82,098 entries across 6 locales (13,683 each), 14,784 card-locale
pairs, **0 manual** — which is what makes D4's discard-and-re-translate safe: there is no
hand-written work in the cache to lose.

**The restore was rehearsed, not assumed.** The R2 copy was downloaded to a scratch
directory, loaded through `TranslationCache.load`, and compared against the live cache:
identical on every count.

15 tests in `pipeline/tests/test_backup.py` pin the parts that fail silently — a corrupt
file must fail at backup time, an unverifiable copy must be removed, pruning must never
empty the directory, and backup names must sort chronologically (`list_r2_backups` sorts
by key and would otherwise return them in the wrong order).

### Phase 1 — The glossary becomes source of truth *(no API spend)*

1. Create `pipeline/glossary/names.json` — JA → `{en, tc, ko, es, th, id}`, seeded from the
   215 curated entries already in `apps/web/i18n/locales/*.json`, plus an `aliases` list per
   entry (D12).
2. Same for `sets.json` (25 curated of 35) and `tags.json` — noting the existing web `tags`
   map keys on `0期生` while the data carries `#0期生`, so it currently matches **0 of 41**.
   The glossary keys on `Card.tags` (the unprefixed JA identity), which is the field that
   actually exists.
3. Generate `apps/web/i18n/locales/*.json`'s `names`/`sets`/`tags` maps from the glossary at
   build time; `make check` fails if they are stale.
4. Point `filter_options`' `_best_label` at the glossary instead of the
   differs-from-ja heuristic.

**Done when:** the web app renders identically to today, from generated maps, and
`make check` catches drift. **81 name gaps and 10 set gaps remain** — filled in Phase 4.

### Phase 2 — Masking *(no API spend)*

The highest-risk code in the plan: it rewrites text destined for the model and puts it back
afterwards. It must fail loudly, never silently mangle.

1. `mask(text, glossary) -> (masked, tokens)` and `unmask(text, tokens, locale)`.
   Longest-first matching across names **and** aliases.
2. Tests for the traps found by measurement: `ルーナ` is a substring of `ルーナイト`;
   87 source strings are ≤3 characters; names overlap each other.
3. An assertion that every token emitted is returned by the model, and a hard error — not a
   fallback — when one goes missing.
4. A `--report-masks` mode listing every mask applied across the corpus, for eyeballing
   before any spend.

**Done when:** masking round-trips all 3,942 units offline with zero token loss, and the
mask report has been reviewed.

### Phase 3 — Content-addressed cache v2 *(no API spend)*

1. `cache.py` gains `version: 2` with key `(kind, sha256(ja))`, at a new path. Keep
   `Entry`'s `source` field, extended with `legacy` (D6).
2. Unit extraction: `cards.json` → 3,942 distinct units tagged by kind.
3. Dual-read (D9): a v2 miss falls back to v1, with per-locale reporting of migration
   completeness so "is this locale consistent yet?" is answerable rather than assumed.
4. Migrate Q&A only (D6): 596 units, winner picked by rule, marked `legacy`.
5. Re-apply the four `tc` strings from F-003 as `source: "manual"` — the first entries in
   the reviewable surface #18 asked for.

**Done when:** a build produced from v2+fallback is byte-identical to today's, proving the
new path is wired correctly before it changes any values.

### Phase 4 — Per-kind prompts and the unit batcher *(small API spend)*

1. Replace `prompts.json`'s six near-identical whole-card prompts with per-kind prompts.
   The calibration prompt is the starting point.
2. Replace `plan_translation` / `translate_card` / `read_field` with a unit batcher: group
   distinct units by kind, pack to a char budget, mask, send, unmask, verify, store.
3. Prose units carry the reference-only context block (D5).
4. Fill the 81 missing names and 10 missing sets — machine-translate once, then maintainer
   review. These land in the glossary as curated entries, not cache entries.
5. Extend calibration to prose and to all six locales — a few hundred units, measured
   against the known-good strings.

**Done when:** calibration output has been reviewed and the prompts are accepted.
**Checkpoint: no bulk spend until this is signed off.**

### Phase 5 — Pilot one locale *(real API spend — after 8 Aug)*

1. Run `en` end-to-end: ~3,346 units (Q&A excluded).
2. Report **measured** points consumed, so the remaining five are budgeted from data rather
   than from this document's arithmetic.
3. Verify against the issues' own numbers: 83 divergent card names → 0, 362 divergent art
   names → 0, 181 keyword names → 0.
4. Ship it. D9's dual-read means `en` can be live and consistent while the other five are
   still on v1.

**Done when:** `en` is measurably consistent on the live site and the per-locale cost is
known.

### Phase 6 — Remaining five locales *(real API spend)*

`tc`, `ko`, `es`, `th`, `id`, one at a time, each shippable on landing. Split across quota
months if the Phase 5 number says so.

**Done when:** all six report fully migrated; dual-read collapses to v2-only; v1 is
archived, not deleted.

### Phase 7 — Show the original *(no API spend)*

1. `LocalizedCard.original` (D10), in **both** implementations — Python reference and
   TypeScript port — with golden files regenerated. This is the one change touching the
   frozen card contract.
2. Frontend toggle: a button revealing the JA text, client-side, no round-trip.

**Done when:** the toggle works on list and detail views and the golden files agree across
both implementations.

### Phase 8 — Close out

1. ADR recording these twelve decisions, superseding ADR 0002's per-card key.
2. Close #20 and #21 with the measured before/after.
3. Close the mechanism half of #18 — `pipeline/glossary/` is the committed, reviewable
   translation surface; note that Q&A corrections still have no home until the `legacy`
   entries are re-translated.
4. Open a follow-up for re-translating the 596 `legacy` Q&A units when quota allows.

---

## Costs and risks

**Estimated cold run, Q&A excluded:** ~117 KB of JA source × 6 locales ≈ 700k input tokens,
~1.5M total with output. Batched at 4,000 chars/call that is ~100 calls per locale, ~600
total — against 14,778 calls for a naive per-card run today. **These are estimates; Phase 5
replaces them with a measured number before the other five locales are committed.**

**Quota:** **374,173 points available** (topped up 2026-07-30), resetting to 1,000,000 on
**8 Aug 2026** — roughly 3.7× the estimated full run, so cost is no longer the binding
constraint. Phases 0–4 spend nothing beyond calibration. Quality outranks cost by explicit
maintainer instruction, which is why `gpt-5.4-mini` was rejected on a single hallucinated
name rather than kept for the cheap kinds.

**Risks, in order of severity:**

1. **Masking corrupts text silently.** Mitigated by Phase 2's hard-error-on-missing-token
   and the mask report. This is why masking is its own phase, before any spend.
2. **A shared translation reads wrong on a specific card.** Inherent to D3: the first card
   to introduce a sentence wins it for all cards. Accepted deliberately — identical printed
   rules text *should* read identically — but there is no per-card escape hatch, only a
   glossary override for all of them.
3. **The quota does not stretch to six locales.** Mitigated by D9: locales land
   independently, so a shortfall delays locales rather than blocking the migration.
4. **`gpt-5.4` moves or changes behaviour mid-migration.** Already happened once —
   `GPT-5-Chat` began returning 500s and nothing noticed until a 2,464-card refresh. The
   per-locale completeness report makes a mid-run regression visible.
