# Findings — closed archive

Data anomalies turned up while building v2, phases 0–6. **This file is closed.** Nothing
is added to it.

Seventeen entries are **settled** — the question has an answer, including where the answer
was "deliberately do nothing". Seven moved to the issue tracker and are stubs here.

**Where new findings go now:**

| what turned up | where it goes |
|---|---|
| needs a maintainer judgement | a GitHub issue, `needs-triage` |
| broke while fixing something else | a GitHub issue, `ready-for-agent` |
| something now *understood* | the code comment, test docstring, or ADR it explains |

Nothing appends here. That rule is what kept this file growing every time an entry was
closed: five of its ten open items were born from resolving others.

**Why it is kept.** Eighty code comments cite these IDs — `# F-006` in `paths.py` means
"the set-scoped image tree exists for a reason, and it is written down here". A settled
finding is the reasoning behind a line of code, not a task.

Open questions are tracked as issues; see [`progress.md`](../progress.md) § Open questions.

| ID | Status | Area | Summary |
|---|---|---|---|
| [F-001](#f-001) | ✅ settled | pipeline | `サポート・スタッフ` had no mapping, so 2 cards shipped as `unknown` |
| [F-002](#f-002) | ✅ settled | data | `cost_count` counted the 特攻 icon; the field had no readers and is dropped |
| [F-003](#f-003) | ✅ settled | data | A stray `value` field on 4 arts; no producer, no reader, dropped |
| [F-004](#f-004) | ✅ settled | data | 2 cards had base arts but no `en` translated arts — the cache filled them in |
| [F-005](#f-005) | ✅ settled | data | `hBP02-065`'s image filename does not match its card number — the site's typo |
| [F-006](#f-006) | ✅ settled | data | `hCO01` reprints reuse the original set's image filename |
| [F-007](#f-007) | ✅ settled | data | Two encodings for dual-colour cards — the cards are printed identically |
| [F-008](#f-008) | ✅ settled | pipeline | `サポート・ロケーション` maps to a code the contract rejects — kept, and pinned |
| [F-009](#f-009) | ✅ settled | data | ~127 oshi skills have no `timing` text — nothing reads it; the site renders `timing_code` |
| [F-010](#f-010) | ✅ settled | data | `batonTouchTypes` is always `["null"]` — noted for the day a coloured one appears |
| [F-011](#f-011) | ✅ settled | data | v1's `card_images/en/` — 1,112 dead files from an abandoned EN scrape |
| [F-012](#f-012) | ✅ settled | data | The official site re-uploads card images; 12 local copies were stale |
| [F-013](#f-013) | ✅ settled | site | Searching a partial CJK name returns nothing on the live site |
| [F-014](#f-014) | ✅ settled | infra | v1 exceeded the D1 free read tier — v1 is archived at Phase 7 |
| [F-015](#f-015) | → [#20](https://github.com/tskrlabs/hololive-ocg-wiki/issues/20) | data | 41% of characters are named inconsistently across their own cards |
| [F-016](#f-016) | ✅ settled | site | v1's colour filter misses fused dual-colour cards |
| [F-017](#f-017) | → [#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17) | infra | Cloudflare's managed `robots.txt` inverts our `Disallow` |
| [F-018](#f-018) | → [#18](https://github.com/tskrlabs/hololive-ocg-wiki/issues/18) | process | A translation fix has no reviewable surface — the cache is not in git |
| [F-019](#f-019) | ✅ settled | site | Infinite scroll never fired; the homepage showed 200 of 2,448 cards |
| [F-020](#f-020) | ✅ settled | data | The card list is not all cards — a rules notice is not a `Card` |
| [F-021](#f-021) | → [#21](https://github.com/tskrlabs/hololive-ocg-wiki/issues/21) | data | Art names are 47–81% untranslated, and inconsistently so |
| [F-022](#f-022) | → [#16](https://github.com/tskrlabs/hololive-ocg-wiki/issues/16) | pipeline | `holo-data build` is broken — the pipeline cannot produce a build |
| [F-023](#f-023) | → [#22](https://github.com/tskrlabs/hololive-ocg-wiki/issues/22) | site | The `blue_red` colour icon is 88×108 where every sibling is 330×410 |
| [F-024](#f-024) | → [#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19) | pipeline | `card_type_code` is the one enum that absorbs an unrecognised value silently |

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

## F-002 — `cost_count` counted the 特攻 icon ✅ fixed

**Found:** Phase 1 · **Fixed:** Phase 6 (field removed from the contract) · **Affected:**
482 arts

The site's arts block renders cost icons and the 特攻 (bonus damage) icon as sibling
`<img>` tags, so v1's extractor collects all of them. `cost_count` was the length of that
list, which means on any art with a 特攻 marker it was **one higher than the number of
actual costs** — and disagreed with `cost_types`, which correctly has only the costs.

Example — `hBP03-011`, art 0: `cost_count: 3`, `cost_types: ["white", "null"]`.

Phase 1 reproduced this deliberately (data equivalence, [ADR 0002](../adr/0002-field-level-translation-cache.md)).
The open question was whether anything computed with the number.

**The answer: nothing read it at all.** A census over the whole codebase found zero
references to `cost_count` in `apps/web`, `apps/api`, or any filter — the card detail
view renders `art.cost_types` and never the count. It was not a D1 column or an index
either; it rode inside the JSON payload.

**Fix:** the field is **removed from the contract** rather than corrected. `cost_types`
already carries the same fact — its length *is* the cost count — so keeping a second,
derivable number only preserved something that could drift from it. A future cost filter
would have reached for the obvious-sounding `cost_count` and got an off-by-one on exactly
the 482 flashiest cards.

Measured over the full build before removal, the two agreed everywhere else: of 1,991
arts, 1,509 had `cost_count == len(cost_types)` and 482 were higher by exactly one — and
all 482 were precisely the arts carrying `special_targets`. The inflation was the 特攻
icon, every time, with no other cause.

**Deliberately not reseeded.** The Worker does no payload validation (`db/cards.ts` is a
bare `JSON.parse`) and `localize()` picks fields explicitly, so a stale `cost_count` still
sitting in a D1 payload is inert — it is dropped on the way out and never reaches a
client. A full reseed is ~47,300 writes against the free tier F-014 already flags, which
is a bad trade for deleting a field nobody reads. Production payloads keep the key until
the next natural reseed; **that transient skew is expected, not a bug.**

**Zero costs vs unknown costs:** `transform.py` only sets `cost_types` when it is
non-empty, so an art with no costs omits it and `localize()` coerces to `[]`. That
conflates "zero costs" with "costs unknown" — but so did the source HTML, where both
produce no cost `<img>` tags. `cost_count` never really encoded that distinction either.

---

## F-003 — arts carried a stray `value` field ✅ fixed

**Found:** Phase 0 · **Fixed:** 2026-07-29 (field removed from the contract) ·
**Affected:** 4 arts on 2 cards, `tc` only

Two cards carried a `tc` art translation with a `value` key beside `name`:

```json
{"name": "おつルーナ", "value": "辛苦啦露娜～"}
```

The finding's original title was wrong, and worth correcting because it pointed at the
wrong layer. These arts have **no `effect` at all**, in any locale — nothing was lost
*into* `value` from `effect`. `value` sat alongside a `name` that was still Japanese.

**It is not a scraping bug.** Every prompt in `translate/prompts.json` says
*「只翻譯 value」* ("translate only `value`"). On four arts the model took that literally
and emitted a sibling `value` key holding its translation instead of replacing `name`.
It is LLM output-shape noise, so the original "is this a scraping bug or is the card
really like that?" framing had no answer — neither.

**v2 cannot produce it.** `transform._arts()` writes `name`/`effect` only, and
`translate.cache.field_keys()` yields `arts[i].name` / `arts[i].effect` — there is no
path that writes `value`. A full build over 2,463 cards produces **zero**, and the
81,124-entry translation cache holds **zero** `.value` keys. The field survived only in
`fixtures/cards.json`, which is still selected from *v1's* data through `v1_adapter.py`,
which passes unknown keys through.

**Fix:** removed from `TranslatedArt`, as F-002 removed `cost_count` — a field with no
producer and no reader. `localize()` never emitted it, which the golden files confirm:
they are **byte-identical before and after**, so nothing the API serves changes.

**The four strings are real, and they are recorded here rather than applied.**
`hBP03-011` has three prints, and id 691 was translated independently — its
`arts[1].name` is `晚安～`, byte-identical to what id 2164 has stranded in `value`:

| card | id | `arts[0]` | `arts[1]` |
|---|---|---|---|
| hBP03-011 | 2164 | `value: 辛苦啦露娜～` | `value: 晚安～` |
| hSD01-005 | 2181 | `value: 來ぬんぬん吧` | `value: 你的心情是……陰轉晴！` |

They are **not** written into the translation cache. The cache is gitignored, so a
correction to it has no reviewable surface and would not survive a clone — that is
[F-018](#f-018), and applying four strings into an ungitted file would have quietly
depended on the very gap F-018 records. Recorded verbatim above so the strings survive
the cache being deleted; they can be applied when F-018 is closed.

**Not reseeded**, for F-002's reason: `localize()` picks fields explicitly, so a stale
`value` still sitting in a D1 payload is dropped on the way out and never reaches a
client. It clears at the next natural reseed.

**What it exposed:** art names are untranslated far more widely than these 4 arts — see
[F-021](#f-021). These two cards are simply the only ones carrying evidence of what the
translation should have been.

---

## F-004 — arts present but no `en` translation ✅ resolved

**Found:** Phase 0 · **Resolved:** 2026-07-29, confirmed against a fresh build ·
**Affected:** `hSD03-009`, `hSD04-009`

Both cards had 2 entries in `Card.arts` but 0 in their `en` translation, while every
other locale had 2. The arts pair by index, so `localize()` emitted the art with its
costs and damage but no name or effect.

**Resolved exactly as this finding predicted** — *"the field-level cache will re-request
them next run, which may resolve this by itself"*. It did. In a build from the current
cache both cards have 2 `en` arts:

| card | id | `en` arts |
|---|---|---|
| hSD03-009 | 446 | `MOGMOG`, `おかゆ～` |
| hSD04-009 | 447 | `33… 22… 11…`, `あくとっ` |

So the answer to the open question is *never produced*, not *genuinely absent* — v1 had
`"arts": null` for `en` on both, and the cache filled them in.

The names come back as Japanese, which is not this finding — see [F-021](#f-021).

⚠️ **The fixture corpus still shows the old shape.** `fixtures/cards.json` is selected
from v1's data, so cards 446/447 still carry `en arts: null` there, and the short-list
zip in `localize()` is still pinned by them. That is load-bearing: merge rule 2 (arts
pair by index, tolerating a short list) is exercised in **both** the Python and the
TypeScript implementation only because these fixtures have that shape. When the fixture
generator is repointed at `holo-data build` output (see [F-022](#f-022)), the corpus
stops covering that path and needs a replacement fixture — otherwise a rule that runs in
production goes untested.

---

## F-005 — image filename does not match card number ✅ resolved

**Found:** Phase 0 · **Resolved:** 2026-07-29, by reading the number printed on the card ·
**Affects:** id 1373, `hBP02-065` (1 card)

Card number `hBP02-065`, image `hBP05/hBP02-085_HR.png`. Every other card's image filename
starts with its card number — a census over the full 2,463-card build found **exactly one**
mismatch, this one. (Notice 2459 has no card number at all, which is [F-020](#f-020), not
this.)

The open question was whether the site has a typo or the number was misparsed. **Neither
required the physical card.** The image is already on disk, and a card prints its own
number in the bottom-right corner:

```
Illust: 南条まや    HR    hBP02-065
```

The scraped HTML says `カードナンバー：hBP02-065`. The printed card says `hBP02-065`. **The
extractor is correct and the card number is correct** — the only wrong thing is a filename
on someone else's server, which is the branch this finding called "nothing to do".

**The site serves both names.** Not in the finding, and worth recording:

| URL under `/cardlist/hBP05/` | status | bytes | last-modified | etag |
|---|---|---:|---|---|
| `hBP02-065_HR.png` | 200 | 111,126 | 2025-09-12 | `7d8a68c4…` |
| `hBP02-085_HR.png` | 200 | 111,126 | 2026-03-27 | `7d8a68c4…` |

Byte-identical, same etag, and a bogus filename in the same folder returns **403** — so
this is not a catch-all soft-404. Both files genuinely exist, and the correctly-named one
is the *older* of the two. That fits [F-012](#f-012)'s pattern exactly: the site re-uploads
its own images, and this re-upload typo'd the name, after which the card page's `<img>`
followed the typo.

**Nothing is repointed.** `image_key` is `hBP05/hBP02-085_HR`, which only ever reaches
`useCardImage()` for URL composition — no code parses a card number back out of a
filename, and `card_number` is its own indexed column. So the finding's "the card would
sort and search oddly" worry does not hold: sorting and search read the column, which is
right. Switching the key to the correctly-named file would cost an R2 rename and a D1 write
to fetch a byte-identical image, which buys nothing.

**Left as-is deliberately**, then, with the mismatch on record so it reads as a known
upstream quirk rather than an unnoticed bug.

### The local image tree answers "check the physical card"

This finding was closed by looking at our own PNG. That is worth generalising: `pipeline/images/png/{set}/`
holds every card at the resolution the site publishes, and anything *printed* on a card —
number, colour symbols, timing markers — can be read off it directly. It is not a substitute
for the physical card on questions about the *game* (what a rule means, whether a card is
legal), but it settles questions about what the card *says*.

[F-007](#f-007) deferred on exactly that and was resolved in the same pass. Still open on
this basis: [F-009](#f-009) (does the card print a timing marker?) and [F-015](#f-015)
(which is partly a question about printed names).

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

## F-007 — two encodings for dual-colour cards ✅ resolved

**Found:** Phase 0 · **Resolved:** 2026-07-29, against the card images ([F-005](#f-005)) ·
**Affects:** 10 cards

The data contains two encodings for what is printed on a dual-colour card:

| encoding | cards | character |
|---|---:|---|
| `["blue_red"]` | 5 | FUWAMOCO |
| `["white_green"]` | 2 | SorAZ |
| `["red","blue"]` | 3 | miComet |

**The count in this finding was wrong** — it said 8 cards and listed only FUWAMOCO and
miComet, omitting SorAZ's 2 `white_green` cards. It is 10.

**The premise was also wrong.** This finding asserted that `blue_red` is "a **single fused
symbol**" while miComet bears "**two separate symbols**", and asked for confirmation that
the physical cards really differ.

**They do not differ.** All three cards print the *same* form — two separate circular
badges on a gold ribbon:

| card | id | printed colour symbol |
|---|---|---|
| hBP03-050 FUWAMOCO | 614 | two badges — blue, then red |
| hBP05-040 miComet | 1218 | two badges — red, then blue |
| hSD01-013 SorAZ | 13 | two badges — white, then green |

**The split is an artifact of the source HTML, not of the game.** The scraped markup shows
where it comes from:

```html
<!-- id 614, FUWAMOCO -->  <img alt="青赤" src="/texticon/type_blue_red.png">
<!-- id 13,  SorAZ     -->  <img alt="白緑" src="/texticon/type_white_green.png">
<!-- id 1218, miComet  -->  <img alt="赤"   src="/texticon/type_red.png">
                            <img alt="青"   src="/texticon/type_blue.png">
```

One card gets a single pre-composited image of *both* badges; the other gets the two badges
as separate files. `type_blue_red.png` **is itself a picture of two badges** — it is not a
fused emblem, it is the pair supplied as one file.

**The 4.2 KB figure was misread.** This finding, and the comment in `enums.py`, cited the
asset's small size as evidence of a simpler fused symbol. It is a *resolution* difference:

| asset | dimensions | size |
|---|---|---:|
| `type_blue_red.webp` | **88 × 108** | 4.2 KB |
| `type_white_green.webp` | 330 × 410 | 20.4 KB |
| every single-colour icon | 330 × 410 | ~17–21 KB |

`white_green` is a fused code too and is full-size, so size never distinguished fused from
single — it distinguishes one badly-exported asset from the rest. That gap has its own
consequence: see [F-023](#f-023).

**Normalising is now defensible — and is deliberately not done here.** This finding said
that if the cards match, "the filter logic in Phase 4 gets simpler and one enum member goes
away". That is now the case: `blue_red` → `["blue","red"]` and `white_green` →
`["white","green"]` would make the data say what the cards show. The original objection —
that normalising "would render two icons and a comma where the card shows one" — does not
survive, because the card *does* show two.

It would touch the contract (`ColorCode`, `FUSED_COLORS`), the pipeline, a populated D1
column, the Worker's query-time expansion and its pinning test
(`test_fused_colours_are_stored_as_printed`), and [F-016](#f-016)'s fix, which exists
purely to make a `blue` filter match `blue_red`. Normalisation would delete the need for
that machinery rather than change it.

**Not attempted in this pass**, which was a documentation pass over [F-005](#f-005). A
schema change across four packages on the strength of one session's finding deserves its
own design pass. What is settled is the *fact*: the two encodings describe identically
printed cards, and the decision this finding was waiting on has its answer.

---

## F-008 — a mapping the contract rejects ✅ resolved

**Found:** Phase 1 · **Resolved:** 2026-07-29 · **Affects:** 0 cards, no behaviour change

`mappings.CARD_TYPE` can emit a code that `CardTypeCode` does not accept, so a card
carrying it fails `build` rather than validating. The finding asked whether to drop the
mapping entry (such a card becomes `unknown` and ships) or keep the hard failure.

**Half of it resolved itself.** The finding named two entries. Bare `サポート → support`
is no longer one of them: the 2,464-card refresh turned up id 2459 (デッキ構築ルール) and
[F-020](#f-020) remapped it to `rulesNotice`, which *is* a member of the enum. Only
`サポート・ロケーション → supportLocation` (`mappings.py:25`) still diverges.

**The surviving entry is kept.** Both branches were checked against the real contract:

| | outcome |
|---|---|
| keep the mapping | `literal_error` on `card_type_code` — `build` blocks |
| drop the mapping | falls through to `unknown` — validates, ships, undeckbuildable |

The entry is inherited verbatim from v1's port (`6be38ff`), and a census of all 2,464
scraped cards finds fourteen distinct `カードタイプ` values — `サポート・ロケーション` is
not among them and never has been. So it is a guess at a string the site has never
printed, which is the case *against* keeping it.

What settles it is that bare `サポート` was the same kind of guess, and it is what caught
F-020 — the first and only time the guard has ever fired, on exactly the thing it was
written for. The costs are also asymmetric: a blocked build is recoverable in minutes and
has `--allow-unknown-enums` as an escape hatch, whereas an `unknown` card ships to D1
announced by nothing (`unknown` appears in no build report, no `status.json`, no
`verify` census) and is silently excluded from every deck section. That is
[F-001](#f-001) again, which sat in v1's live data from the day those cards shipped.

**Pinned by a test.** `TestCardType::test_mapping_may_exceed_the_contract_deliberately`
asserts both halves — that the mapping emits a value outside `CARD_TYPE_VALUES`, and that
a card carrying it fails validation. Deleting the mapping entry and widening the enum are
each individually plausible tidy-ups, and either one alone would turn the loud failure
silent with `make check` still green.

**The `unknown` channel this exposed is [F-024](#f-024)**, logged separately.

---

## F-009 — oshi skills with no `timing` text ✅ settled

**Found:** Phase 0 · **Settled:** 2026-07-29, against the site's own code ·
**Affects:** ~127 oshi skills, ~127 SP oshi skills

`timing_code` is present on every skill (`once_per_turn` / `once_per_game`), but the
human-readable `timing` string ("Once per turn") is missing on ~7% of them, in **all**
locales including `ja`.

This finding asked for a decision: render from `timing_code`, or chase a regex variant in
the extractor?

**The decision was already made, in code.** `CardDataDetailBlocks.vue` renders
`item.oshi_skill.timing_code` and `item.sp_oshi_skill.timing_code`, gated on those same
codes. A census over `apps/web` and `packages/schema/dist` finds **zero readers of the
`timing` string** — nothing on the site has ever displayed it.

So the missing string reaches no user, and the branch this finding worried about
("Phase 5 should render from `timing_code`") is what Phase 5 did. Whether the extractor's
`[ターンに1回]` regex misses a variant spelling is now a question with no consequence: the
field it would populate is dead weight in the payload.

Left in the contract rather than removed — unlike `cost_count` ([F-002](#f-002)) and
`value` ([F-003](#f-003)), this field is genuinely produced by the source and is simply
unused, so dropping it would be a scope choice rather than a correction.

---

## F-010 — `batonTouchTypes` is always `["null"]` ✅ settled

**Found:** Phase 0 · **Settled:** 2026-07-29 · **Affects:** all 2,219 cards that have one

Every baton touch cost in the entire dataset is the colourless `◇`. No card has ever had
a coloured baton touch cost.

Modelled as `list[ColorCode]` anyway — hardcoding `Literal["null"]` would break on the
first coloured one.

**Nothing to decide.** The modelling is already correct for both worlds, and this
finding's own text said "probably nothing". It is kept as a note rather than a question:
if a coloured baton touch ever ships and something downstream assumed colourless, the
assumption is on record here with the date it was true.

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

---

## F-013 — partial CJK search returns nothing ✅ fixed

**Found:** Phase 3 · **Fixed:** Phase 3 (`tokenize='trigram'`) · **Affected:** every
CJK search on the live site

Probing v1's live API while designing the Phase 3 FTS index:

| query | results |
|---|---|
| `白上フブキ` | 62 |
| `フブキ` | **0** |
| `ときのそら` | 29 |
| `のそら` | **0** |
| `宝鐘マリン` | 32 |
| `宝鐘` | **0** |

Only a card's *complete* name matches. FTS5's default `unicode61` tokenizer splits on
Unicode whitespace and punctuation, and an unbroken run of kana or kanji contains
neither — so `白上フブキ` is indexed as one token and no substring of it can be found.

This matters more than it looks: the site's default locale is `tc` and its source locale
is `ja`, so the majority of card names are affected. Typing a character's name and
expecting their cards is the single most obvious thing to do with a card database.

**Fix:** `tokenize='trigram'` on the Phase 3 FTS table, which indexes every 3-character
window. Verified against the real 2,448-card set: `フブキ` returns 73 hits and
`宝鐘マリン` 45.

**Carried into Phase 4.** Trigram cannot match a query shorter than 3 characters, and
returns *no rows* rather than an error — the same silent-nothing shape as the original
bug. Two-character queries are common in Japanese (`宝鐘`, `運用`), so the worker falls
back to `LIKE` below the threshold. A test pins both halves.

---

## F-014 — v1 exceeded the D1 free read tier ✅ settled

**Found:** Phase 3 · **Settled:** 2026-07-29 — it ends when v1 does ·
**Affects:** the live v1 site only · **Not fixed in v1, and will not be**

D1 analytics for the 30 days to 2026-07-27:

| metric | value |
|---|---|
| read queries/day (avg) | ~1,200 |
| **rows scanned per query** | **882** |
| rows read/day — median | 722,426 (14% of quota) |
| rows read/day — p90 | 1,641,541 (33%) |
| rows read/day — **max** | **5,582,892** |
| days above 20% of quota | 10 of 31 |

The free tier is 5,000,000 rows read per day. **On 2026-07-12 the site went over it**,
at which point D1 returns errors until 00:00 UTC. Whether anyone noticed is unknown —
there is no alerting, and the site degrades to a failed fetch rather than an error page.

882 rows scanned per query on a 2,448-row table is a full table scan. Two causes, both
fixed by the Phase 3 schema:

1. **`enrichCardDataBatch`** issues five follow-up queries per page of results against
   child tables holding 13k–17k rows, and the `LEFT JOIN card_translations` fans every
   result row out by 7.
2. **JSON-array filters cannot use an index.** `color_codes LIKE '%"blue"%"'` reports
   `SCAN cards` in `EXPLAIN QUERY PLAN` despite `idx_cards_color_codes` existing.

**Why this is settled rather than tracked.** v1 stays live until cutover and nothing here
changes that; the fix ships with v2's schema, which measured at ~50–100 rows per
filtered page against v1's 882. The live site has a standing failure mode until Phase 7 —
if traffic spikes before cutover, this is what breaks, and the only lever available on v1
is reducing traffic. **That is not a task, because the remedy is "launch v2", which is
already the plan**, and v1 is archived at Phase 7 along with the failure mode. No issue
was opened; one would sit open until it became moot.

**Worth knowing for v2:** rows-read scales with traffic while writes do not. It is the
number to watch after launch, and the reason the schema optimises for it over the row
count D8 originally targeted. See [ADR 0004](../adr/0004-d1-schema-and-seeder.md).

---

## F-015 — 41% of characters are named inconsistently across their own cards → [#20](https://github.com/tskrlabs/hololive-ocg-wiki/issues/20)

**Found:** Phase 4 · **Moved to the tracker:** 2026-07-29

The API half is fixed and stays fixed: the `name` filter keys on an indexed `name_ja`
column, so one query returns every card for a character regardless of how each card spells
it, and `/api/filter-options` pairs that key with a display label.

What remains is a question about the *source data* — 271 of 296 characters have no
romanised `en` name on any card, and the 6-of-44 Fubuki pattern suggests the official site
translates a name only sometimes rather than never. Full evidence and the measurements are
in [#20](https://github.com/tskrlabs/hololive-ocg-wiki/issues/20).

---

## F-016 — v1's colour filter misses fused dual-colour cards ✅ fixed

**Found:** Phase 4 · **Fixed:** Phase 4 (query-time expansion) · **Affected:** 7 cards
on the live site

Dual-colour cards print **one fused icon**, not two colours, and the data stores them as
printed: `blue_red` and `white_green` are their own colour codes (F-007 covers the
encoding). Across the real set:

| code | cards |
|---|---|
| `blue_red` | 5 |
| `white_green` | 2 |

v1 filtered colours with `color_codes LIKE '%"blue"%'`, which does not match
`"blue_red"`, and exposed `blue_red` / `white_green` as their own filter checkboxes.
So on the live site **filtering by blue silently omits the 5 blue/red cards** — they are
blue cards, and a player filtering for blue wants them.

**The fix is in the query layer, not storage.** Expanding on write would render two
icons and a comma where the card shows one, so the seeder keeps the printed encoding
(pinned by `test_fused_colours_are_stored_as_printed`) and the Worker expands the
*filter* instead: a request for `blue` queries `('blue', 'blue_red')`.

Verified on the fixture set — `blue` alone matches 4 cards, `blue` plus `blue_red`
matches 6, and the API returns 6.

**Note this changes behaviour rather than restoring it**, so Phase 5's filter UI should
drop the separate `blue_red` / `white_green` checkboxes: those cards now appear under
both of their constituent colours, which is what a player expects. Left for Phase 5
because it is a UI decision, not an API one.

---

## F-017 — Cloudflare's managed `robots.txt` inverts our `Disallow` → [#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17)

**Found:** Phase 5 · **Accepted:** 2026-07-27 · **Moved to the tracker:** 2026-07-29

A zone-level Cloudflare setting prepends `User-agent: * / Allow: /` above our
`Disallow: /`, so `robots.txt` on the custom domain most likely reads as crawlable. The
maintainer accepted the risk rather than change a zone setting mid-phase, so **`noindex`
is the sole indexing guard until Phase 7**, when the conflict resolves itself.

Tracked at [#17](https://github.com/tskrlabs/hololive-ocg-wiki/issues/17) — labelled
`phase-7` — because the revisit is a launch step, not an open question. The one-click
override, if it is ever needed sooner, is in the issue.

The general lesson is worth keeping here: **a zone-level Cloudflare feature can change
what a Worker appears to serve.** `curl` against `workers.dev` and against the custom
domain returned different bytes for the same path, which is the only reason this was
caught.

---

## F-018 — a translation fix has no reviewable surface → [#18](https://github.com/tskrlabs/hololive-ocg-wiki/issues/18)

**Found:** Phase 6 · **Moved to the tracker:** 2026-07-29

D14 promised that fixing a bad translation would be a reviewable PR. ADR 0002 replaced the
overlay mechanism with cache entries — strictly better for *durability* — but the cache
lives in gitignored `pipeline/locales/`, so the file a contributor would edit does not
exist in a clone, and the `pipeline/corrections/` carve-out is empty and unread by any
code. A fix can only be reported, then applied by the maintainer.

Three candidate mechanisms, none chosen, are in
[#18](https://github.com/tskrlabs/hololive-ocg-wiki/issues/18). The four `tc` art strings
[F-003](#f-003) recovered are waiting on it — they are recorded verbatim in F-003 rather
than written into the cache, precisely because doing so would have depended on the gap
this records.

---

## F-019 — infinite scroll never fired ✅ fixed

**Found:** after Phase 6, by the maintainer looking at the live site ·
**Fixed:** same pass · **Affects:** the card list — i.e. the homepage

Scrolling the homepage stopped after the first page. The live site served **200 of 2,448
cards** and there was no way to reach the rest; the deck builder could only use whichever
cards happened to fall in that first page. It had been that way since Phase 5 deployed.

Nothing was wrong with the data or the API. `/api/cards/filter?page=1&limit=200` returns
`total: 2448`, and page 13 returns the final 48 cards. The site simply never asked for
page 2.

`CardListViewAPI.vue` renders a `RecycleScroller` and listens for `@scroll-end` to call
`loadMore`. In `vue-virtual-scroller@2.0.1` that emit is gated:

```js
a.emitUpdate && (s?.onUpdate)?.call(s, P, A, ge, ze)
// onUpdate: (…, we) => { …; we >= t.items.length - 1 && s("scrollEnd") }
```

`emitUpdate` defaults to `false` and the component never passed it. The handler, the
debounce, the `hasMore` guard and `useCardQuery.loadMore` were all correct and all
unreachable. The fix is one prop: `:emit-update="true"`.

**Three things kept it hidden**, and each is worth more than the bug:

- **The results summary was commented out** (`CardListViewAPI.vue`, "Showing X of Y
  cards"). It would have read *"Showing 200 of 2448"* on every page load. It is restored,
  but repositioned — in flow it sat below a `height: 100dvh` scroller, so it was never on
  screen, which is the likeliest reason it was disabled instead of fixed.
- **`make dev` cannot reproduce it.** The fixtures are 34 cards and the page size is 200,
  so `hasMore` is false locally and there is never a page 2. Local QA of the card list is
  structurally incapable of exercising pagination. Verifying this fix needed the dev
  server pointed at the deployed Worker.
- **No test could see it.** All 44 web tests targeted pure functions; not one mounted a
  component. A prop that was never passed exists only in a template, so `make check`
  passed a homepage showing 8% of the database. `apps/web/tests/component.test.ts` now
  mounts the card list — both fixes here were confirmed to fail it before they were
  applied.

**A second bug rode along.** Filtering while scrolled down left the scroller's offset
where it was, so a new result set began mid-list. It was invisible while page 1 was all
that ever loaded, and would have become visible the moment this fix landed. Fixed in the
same pass.

**Also removed:** seven components referenced by nothing —
`CardListViewAPIBasic`, `CardListViewAPIVirtualScroller`, `StatusCardGrid`, `FilterView`,
`FilterButton`, `IconGlobe`, `IconGitlab`. The first two are of a piece with this
finding: they are v1-era copies of the card list that ADR 0006 records as collapsed, and
they carry their own drifted pagination logic — one calls `loadMore` without passing
`pageSize`, so it would have paged in 50s while claiming 200. Two files named
`CardListViewAPI*` sitting beside the real one is a working trap for whoever next goes to
fix "the card list".

**The open question this leaves** is Phase 5's verification, not this component. The site
was checked by looking at it, and a homepage that renders 200 cards beautifully looks
exactly like one that renders 2,448 until you scroll to the bottom and count. The
component test closes this specific hole; whether the rest of the site has similar
never-fires wiring has been surveyed once — `@scroll-end` was the only event binding of
its kind — but not proven.

## F-020 — the card list is not all cards ✅ resolved

**Found:** 2026-07-28, testing the pipeline against the source's 2,448 → 2,464 update ·
**Resolved:** same pass · **Affects:** the contract, the pipeline, the API

The refresh added 16 ids. Fifteen are ordinary `hPR` promo reprints. The sixteenth,
id **2459 「デッキ構築ルール」**, is not a card:

```
card_number:     "null"      the literal string, from <span>null</span>
card_type_code:  サポート     the bare type — every real support card has a subtype
rarity_code:     absent
image:           sele08/sele08_teaching.png
```

It is a **Selection Cup format-legality notice**. Its body states which products are
legal for the event and how card-number matching works across reprints — the rule that
decides whether a given deck may be registered.

`build` refused it, with two validation errors, and that refusal was correct:
`mappings.py` maps the bare `サポート` to a code the contract's enum does not accept,
specifically so a genuinely new type fails loudly. It was the first time that guard ever
fired, and it fired on the first thing it was written for.

**It is not noise, and excluding it would have lost real information.** The same update
added a 35th `card_sets` value — 「【使用可能カード】セレクションカップ」 — to **~660
existing cards**. That value is a format-legality marker, and notice 2459 is the only
place the site explains what it means. A planned deck simulator needs exactly this
record to answer "is this deck legal for this format?".

### Why it is not a `Card`

Modelling it as a card was tried and reverted. `card_number` and `rarity_code` are
`NOT NULL` in the D1 schema, so admitting a notice means dropping both constraints — and
SQLite has no `ALTER COLUMN`, so that is a full rebuild of a populated 2,448-row
production table (copy, drop, rename, recreate 7 indexes and the FTS triggers). Verified
against a production-shaped table rather than assumed:

```
INSERT … card_number=NULL, rarity_code=NULL
→ NOT NULL constraint failed: cards.card_number
```

Paying a live-database rebuild to weaken an invariant that correctly protects all 2,463
real cards is the wrong trade. A scraper regression that stopped parsing rarity would
then validate silently — the exact failure ADR 0001's strict contract exists to catch.

### What was built instead

A separate `Notice` model, published as an **R2 artifact** and served by `/api/notices`.
This is ADR 0004's `filter-options` reasoning applied again: a handful of records, the
same answer for every user until the next pipeline run, nothing that needs an index. The
generated DDL is **byte-identical** to what is live — no migration, nothing touching the
populated database.

Notices ride the *same* scrape, extract, transform and translate path as cards; the
split happens at build time. Their prose is `ability_text`, already a translatable
scalar, so the notice is translated into all 7 locales through the existing field-level
cache with no new machinery.

Three properties are pinned by tests (`pipeline/tests/test_notices.py`, 13 cases):

- `Card` **rejects** a non-card type outright, so the split cannot be bypassed into a
  card row with a fabricated number and rarity
- `card_number` and `rarity_code` stay **strictly required** for every real card
- no deck section can hold a notice — structural, via `NON_CARD_TYPES`, rather than a
  consumer-side filter every caller must remember (Phase 5's F-019 lesson)

`/api/notices` returns an **empty collection** rather than 404 when the artifact is
absent: "none published" and "none exist" are the same answer to a caller, and a site
rendering a notices section should not have to treat a 404 as success.

### Still open

**Nothing renders notices yet.** The data is modelled, translated, published and served;
no page reads `/api/notices`. That is deliberate — this pass was a pipeline test, and
adding a site surface was not in it — but until a page exists, the notice is reachable
only by calling the endpoint directly.

**The classification is an inference.** A bare `サポート` type is taken to mean "notice".
It is safe because the contract checks the other half — a `rulesNotice` carrying a
`card_number` is rejected — so a genuinely new bare-`サポート` *card* still fails `build`
loudly. But if the site ever publishes a notice *with* a number, this needs revisiting.

---

## F-021 — art names are largely untranslated, inconsistently → [#21](https://github.com/tskrlabs/hololive-ocg-wiki/issues/21)

**Found:** 2026-07-29, while resolving [F-003](#f-003) · **Moved to the tracker:**
2026-07-29

Art names are 47–81% identical to the `ja` name depending on locale. Much of that is
correct by policy — every prompt says not to translate character names inside art names —
but the data contradicts itself: `hBP03-011`'s three prints of the same art give three
different answers in the same locale.

The question is whether art names should be translated at all, which is a call about the
audience. Full per-locale measurements and the contradiction table are in
[#21](https://github.com/tskrlabs/hololive-ocg-wiki/issues/21).

---

## F-022 — `holo-data build` is broken → [#16](https://github.com/tskrlabs/hololive-ocg-wiki/issues/16)

**Found:** 2026-07-29, while fixing [F-003](#f-003) · **Moved to the tracker:** 2026-07-29

[F-002](#f-002) removed `cost_count` from the contract, correctly — but `Card` is
`extra="forbid"` and both inputs on disk still carry the field, so `holo-data build` fails
on 1,991 arts and `make fixtures` on 1,715 cards. **The pipeline cannot produce a build.**
The site is unaffected: D1 was seeded before the contract changed.

Not a data problem — re-transforming from `cards_structured.json` produces clean output.
The *derived* files on disk are stale, and `make check` runs neither generator, so a
generated file and its generator can disagree indefinitely.

The repair is scoped and measured in
[#16](https://github.com/tskrlabs/hololive-ocg-wiki/issues/16), including
[F-004](#f-004)'s warning: repointing the fixture generator removes the only test coverage
of `localize()`'s short-list rule, in both Python and TypeScript.

**This was the one urgent item in this file** — it is the reason a "the site works, so
none of this matters" reading of the findings log is not quite safe.

---

## F-023 — the `blue_red` colour icon is a quarter the size of its siblings → [#22](https://github.com/tskrlabs/hololive-ocg-wiki/issues/22)

**Found:** 2026-07-29, while resolving [F-007](#f-007) · **Moved to the tracker:**
2026-07-29

`type_blue_red.webp` is 88 × 108 where all eight siblings are 330 × 410, so on the 5
FUWAMOCO cards the colour symbol renders visibly soft. **Upstream has no better copy** —
the official asset is the same size, the only one of nine that is wrong there.

Two ways out, both in [#22](https://github.com/tskrlabs/hololive-ocg-wiki/issues/22):
redraw the asset (which means shipping our own art in place of official art), or take
[F-007](#f-007)'s normalisation, which retires the asset entirely and fixes the blur as a
side effect.

**Worth keeping here:** this asset's small file size was cited by [F-007](#f-007) and by
`enums.py` as *evidence* that `blue_red` is a fused single symbol. It was not — it was an
export mistake, and that misreading shaped the contract's comment for two phases.

---

## F-024 — `card_type_code` absorbs an unrecognised value; the others report it → [#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19)

**Found:** 2026-07-29, while resolving [F-008](#f-008) · **Moved to the tracker:**
2026-07-29 · **Affects:** 0 cards today

`transform.py` writes `"unknown"` as the fallback at eight sites across four enums, and
only `card_type_code` accepts it. So the same event — the site printing a value we have no
mapping for — stops the build in three fields and ships silently in the fourth.

The absorption is deliberate ([F-001](#f-001)'s safety valve, and `deckSections.ts` routes
`unknown` to no section). **What is missing is the census:** nothing counts, prints, or
alerts on it, so the channel is not merely unmonitored but silent, with no baseline anyone
would notice moving.

Three candidate answers — census in the build report, block like the other three, or a
threshold — are in [#19](https://github.com/tskrlabs/hololive-ocg-wiki/issues/19). Note
that blocking would interact with [F-008](#f-008)'s pinning test.
