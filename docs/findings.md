# Findings

Data anomalies and suspicious behaviour turned up while building v2, recorded here
rather than fixed on the spot.

**The rule:** anything unambiguously wrong with an obvious fix gets fixed in the phase
that found it, and logged here as `fixed`. Anything that needs a judgement call about the
*game* — is this a scraping bug or is the card really like that? — is logged as `open`
and left alone. The maintainer reviews the open ones against the real cards once the v2
base is complete.

Nothing here blocks a phase. If something did, it would be an issue, not a finding.

| ID | Status | Area | Summary |
|---|---|---|---|
| [F-001](#f-001) | ✅ fixed | pipeline | `サポート・スタッフ` had no mapping, so 2 cards shipped as `unknown` |
| [F-002](#f-002) | 🔍 open | data | `cost_count` counts the 特攻 icon, so it can exceed `cost_types` by one |
| [F-003](#f-003) | 🔍 open | data | 2 cards have arts translated into a `value` field instead of `effect` |
| [F-004](#f-004) | 🔍 open | data | 2 cards have base arts but no `en` translated arts |
| [F-005](#f-005) | 🔍 open | data | `hBP02-065`'s image filename does not match its card number |
| [F-006](#f-006) | ✅ fixed | data | `hCO01` reprints reuse the original set's image filename |
| [F-007](#f-007) | 🔍 open | data | Two encodings for dual-colour cards |
| [F-008](#f-008) | 🔍 open | pipeline | `サポート` and `サポート・ロケーション` map to codes the contract rejects |
| [F-009](#f-009) | 🔍 open | data | ~127 oshi skills have no `timing` text in any locale |
| [F-010](#f-010) | 🔍 open | data | `batonTouchTypes` is always `["null"]` |
| [F-011](#f-011) | ✅ closed | data | v1's `card_images/en/` — 1,112 dead files from an abandoned EN scrape |
| [F-012](#f-012) | ✅ fixed | data | The official site re-uploads card images; 12 local copies were stale |

---

## F-001 — `サポート・スタッフ` had no mapping ✅ fixed

**Found:** Phase 1 · **Fixed:** Phase 1 (`supportStaff` added to the enum and mapping)

Two cards — both `hBP07-091`, ライブスタッフ ("Live Staff"), ids `1877` and `2003` — carry
card type `サポート・スタッフ`. v1's mapping table had `サポート・スタッフ・LIMITED` but not
the bare form, so both fell through to the `unknown` placeholder and have been sitting in
the live database as `unknown` ever since the card shipped.

ADR 0001 described `unknown` as "the scraper degrading gracefully". That was half right:
the degradation worked, but the cause was a missing table entry, not an unparseable card.

**Fix:** added `supportStaff` to `CardTypeCode` and `サポート・スタッフ → supportStaff` to
the pipeline mapping. **No card now classifies as `unknown`.** The code stays in the enum
as a safety valve for the next genuinely unrecognised type.

`v1_adapter.py` corrects these two ids when reading v1's data, so the fixtures (which are
selected from v1's `cards.json`) match what the pipeline now produces.

**Worth checking at review:** whether `supportStaff` belongs in `MAIN_CARD_TYPES` for
deck-building. It is there now, on the assumption it behaves like other support cards —
but that is a game rule, not something the data states.

---

## F-002 — `cost_count` counts the 特攻 icon 🔍

**Found:** Phase 1 · **Affects:** 482 arts

The site's arts block renders cost icons and the 特攻 (bonus damage) icon as sibling
`<img>` tags, so v1's extractor collects all of them. `cost_count` is the length of that
list, which means on any art with a 特攻 marker it is **one higher than the number of
actual costs** — and disagrees with `cost_types`, which correctly has only the costs.

Example — `hBP03-011`, art 0: `cost_count: 3`, `cost_types: ["white", "null"]`.

The pipeline reproduces this deliberately: Phase 1's criterion was data equivalence, and
this is the number the live site has shipped for a year.

**Needs a decision:** is `cost_count` used for anything but display? If the deck builder
or a filter ever computes with it, the off-by-one matters. The fix is one line
(`len(real_costs)` instead of `len(cost_icons)`) but it changes published data.

---

## F-003 — arts translated into `value` instead of `effect` 🔍

**Found:** Phase 0 · **Affects:** 4 arts on 2 cards, `tc` only

`hBP03-011` and `hSD01-005` have arts whose `tc` translation carries a `value` key
holding what looks like a translation of the art's *name*:

```json
{"name": "おつルーナ", "value": "辛苦啦露娜～"}
```

Every other art in every other locale uses `name` + `effect`. No other locale has `value`
on these cards.

`Card` models the field so those cards validate, and `localize()` ignores it — so the
translations are effectively invisible to the site today.

**Needs a decision:** is `辛苦啦露娜～` the intended `tc` name for that art (in which case
these are lost translations that should move into `name`), or leftover junk from a
one-off translation run? Only someone reading the cards can say.

---

## F-004 — arts present but no `en` translation 🔍

**Found:** Phase 0 · **Affects:** `hSD03-009`, `hSD04-009`

Both cards have 2 entries in `Card.arts` but 0 in their `en` translation, while every
other locale has 2. The arts pair by index, so `localize()` emits the art with its costs
and damage but no name or effect.

Both are golden-file fixtures, so the behaviour is pinned by test.

**Needs a decision:** whether the `en` translation was simply never produced (in which
case re-running `translate` for those two cards fixes it) or the site genuinely has no
English text for them. The field-level cache will re-request them next run, which may
resolve this by itself — worth re-checking after the first real `translate`.

---

## F-005 — image filename does not match card number 🔍

**Found:** Phase 0 · **Affects:** `hBP02-065` (1 card)

Card number `hBP02-065`, image `hBP02-085_HR.png`. Every other card's image filename
starts with its card number.

Either the official site has a typo in the image path, or the card number was misparsed.
Since the image is fetched from the URL the site gives, the file being served is
presumably correct — but the card would sort and search oddly.

**Needs a decision:** check the physical card. If the site's filename is wrong there is
nothing to do; if the card number is misparsed, the extractor needs a look.

---

## F-006 — reprints reuse the original set's image filename ✅ fixed

**Found:** Phase 0 · **Resolved:** Phase 2 grilling — the two prints are **different
artwork** · **Affects:** 2 pairs (4 cards)

`hBP03-044_SR.png` and `hBP03-055_SR.png` are each served under **two** set folders,
`/cardlist/hBP03/` and `/cardlist/hCO01/`, as genuinely different cards (ids 726/2138 and
735/2139).

**Verified against the official site.** All four URLs were fetched and hashed:

| card number | ids | `/hBP03/` | `/hCO01/` | |
|---|---|---:|---:|---|
| hBP03-044 (星街すいせい) | 726 / 2138 | 551,400 B | 623,513 B | different |
| hBP03-055 (常闇トワ)   | 735 / 2139 | 411,502 B | 501,764 B | different |

Not merely different encodings of one illustration — **different illustrations**. The
hBP03 print of hBP03-044 is credited `Illust: A.I.__D`, the hCO01 print `Illust: Miho
Ikuzo`; the art is unmistakably distinct (stage backdrop vs. abstract colour burst). Card
text, HP, skills, and bloom level are identical between the two — only the set and the
illustration differ.

So this is not a scraping artefact and not duplicated storage. These are two genuinely
distinct cards that share a card number *and* a filename, separable only by the set folder
in the source URL.

**What v1 shipped:** `download_image()` skips any filename already on disk, so within each
pair only the **first-scraped** image was ever downloaded, and both cards' `image_path`
pointed at it. v1 has been serving one card's artwork for both members of each pair for as
long as the hCO01 set has existed.

**Fixed:** the image key is `{set}/{filename}` (`transform.image_key_from_url`), so the
pairs get distinct keys; `CardCollection` rejects duplicate keys outright. Phase 2 also
makes the *local* image tree set-scoped (`images/png/{set}/…`), which is what stops the
on-disk overwrite — the key alone does not, since two keys pointing at one file would
still upload the same bytes twice.

**No decision outstanding.** Recorded as a worked example: a "duplicate" in this dataset
is not safe to deduplicate on filename.

---

## F-007 — two encodings for dual-colour cards 🔍

**Found:** Phase 0 · **Affects:** 8 cards

The data contains both:

- `["blue_red"]` — 5 FUWAMOCO cards, a **single fused symbol** with its own icon asset
  (`type_blue_red.webp`, 4.2 KB against ~20 KB for single-colour icons)
- `["red","blue"]` — 3 miComet cards, **two separate symbols**

These were nearly normalised into one form during Phase 0. They are not the same thing:
normalising would render two icons and a comma where the card shows one.

Modelled as-is, both encodings first-class.

**Needs a decision — the one most worth checking:** confirm against the physical cards
that FUWAMOCO and miComet really are printed differently. If they are the same and one is
a scraping artefact, the filter logic in Phase 4 gets simpler and one enum member goes
away. If they differ, the current model is right and Phase 4 needs `FUSED_COLORS`
expansion so a "red" filter matches `blue_red`.

---

## F-008 — mappings that the contract rejects 🔍

**Found:** Phase 1 · **Affects:** 0 cards today

`mappings.CARD_TYPE` can emit `support` (from bare `サポート`) and `supportLocation` (from
`サポート・ロケーション`), but neither is a member of `CardTypeCode`. No card has ever used
either, so this is invisible — until the site ships one, at which point `build` fails.

That failure is arguably correct: a Location card would be a new mechanic, and shipping it
as a silently-accepted enum value is worse than stopping. But the *reason* it fails would
be confusing — the mapping says the type is known while the contract says it is not.

**Needs a decision:** either drop the two entries from the mapping (so such a card becomes
`unknown` and passes), or keep them and treat the hard failure as intended. Currently the
second, documented in `mappings.py`.

---

## F-009 — oshi skills with no `timing` text 🔍

**Found:** Phase 0 · **Affects:** ~127 oshi skills, ~127 SP oshi skills

`timing_code` is present on every skill (`once_per_turn` / `once_per_game`), but the
human-readable `timing` string ("Once per turn") is missing on ~7% of them, in **all**
locales including `ja`.

Since `timing_code` is reliable, the UI can render the timing from i18n rather than the
stored string — so this may not matter at all.

**Needs a decision:** whether the site omits the marker on those cards (nothing to fix,
and Phase 5 should render from `timing_code`) or the extractor's `[ターンに1回]` regex
misses a variant spelling.

---

## F-010 — `batonTouchTypes` is always `["null"]` 🔍

**Found:** Phase 0 · **Affects:** all 2,219 cards that have one

Every baton touch cost in the entire dataset is the colourless `◇`. No card has ever had
a coloured baton touch cost.

Modelled as `list[ColorCode]` anyway — hardcoding `Literal["null"]` would break on the
first coloured one.

**Probably nothing.** Recorded so that if a coloured baton touch ever appears and
something downstream assumed colourless, the assumption is on record. Worth a glance at
whether the game rules even allow it.

---

## F-011 — v1's `card_images/en/` is dead ✅ closed

**Found:** Phase 2 grilling · **Resolved:** same session — confirmed dead by the maintainer

v1's repo carries `public/card_images/en/` — **1,112 files** named `EN_hBP02-004_OSR.png`
and similar, produced by an English-language scrape (`data/en/` exists in the v1 pipeline
alongside `data/default/`).

Nothing references them. No card in `cards.json` has an `imagePath` outside
`card_images/default/` (all 2,448 point at `default`), and no component, composable, or
script in the v1 repo mentions the `en/` directory.

**Confirmed dead — will not be carried to v2.** They are not migrated by
`holo-data migrate-images` and never reach R2. English card art is out of scope; the
site's English support is translation of the JP cards, not EN-printed card images.

Recorded so the directory's absence in v2 reads as a decision rather than an oversight —
and so a future "where did the EN images go?" has an answer.

---

## F-012 — the official site silently re-uploads card images ✅ fixed

**Found:** Phase 2 · **Fixed:** Phase 2 (12 images re-fetched) · **Affects:** 12 cards

The first `verify-images --remote` run over the migrated set reported **2,436 of 2,448
matching** and 12 differing from source. None was a wrong-card error. The official site
had replaced its own files since the images were last scraped, in two flavours:

| | cards | change |
|---|---|---|
| upscaled | 7 | 400×559 → 744×1040 or 992×1386 |
| re-compressed | 5 | same dimensions, ~60–80% smaller, visually identical |

`hBP07-002_SEC` went 139,980 → 2,100,814 bytes at 400×559 → 992×1386; `hSD02-014_C`
went 292,817 → 62,514 bytes at unchanged dimensions, and the two render identically.

**Why nothing noticed.** `download_image()` skips any file already on disk — correctly,
since re-downloading 2,448 images per run would be rude. But that also means a *replaced*
upstream file is never picked up. The scraper has no notion of an image being stale, only
of it being absent, so the site's re-uploads were invisible.

**Fixed:** the 12 were re-fetched and reconverted. The set is now byte-identical to source
across all 2,448 cards.

**The general point.** This is not a one-off — the site evidently does this from time to
time, and there is currently no mechanism that detects it. `verify-images --remote` is the
detector, but it is opt-in and expensive (~2,450 requests), so it will not run on a normal
update. Worth doing after each new set ships, or occasionally as a spot check.

Not worth automating into `scrape`: a conditional GET per image would make every run
2,450 requests against a small operator's site to catch a handful of changes a year.
The manual check is the better trade.
