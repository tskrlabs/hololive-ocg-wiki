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
| [F-013](#f-013) | ✅ fixed | site | Searching a partial CJK name returns nothing on the live site |
| [F-014](#f-014) | 🔍 open | infra | v1 exceeded the D1 free read tier on 2026-07-12 |
| [F-015](#f-015) | 🔍 open | data | 41% of characters are named inconsistently across their own cards |
| [F-016](#f-016) | ✅ fixed | site | v1's colour filter misses fused dual-colour cards |
| [F-017](#f-017) | 🔍 open | infra | Cloudflare's managed `robots.txt` inverts our `Disallow` |
| [F-018](#f-018) | 🔍 open | process | A translation fix has no reviewable surface — the cache is not in git |

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

## F-014 — v1 exceeded the D1 free read tier 🔍

**Found:** Phase 3 · **Affects:** the live v1 site · **Not fixed in v1**

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

**Why this is `open` and not `fixed`.** v1 stays live until cutover and nothing here
changes that; the fix ships with v2's schema, which measured at ~50–100 rows per
filtered page against v1's 882. Left open so the maintainer knows the live site has a
standing failure mode until Phase 7 — if traffic spikes before cutover, this is what
breaks, and the only lever available on v1 is reducing traffic.

**Worth knowing for v2:** rows-read scales with traffic while writes do not. It is the
number to watch after launch, and the reason the schema optimises for it over the row
count D8 originally targeted. See [ADR 0004](adr/0004-d1-schema-and-seeder.md).

---

## F-015 — 41% of characters are named inconsistently across their own cards 🔍

**Found:** Phase 4 · **Affected:** the `name` filter, in every locale

The `name` filter answers "show me every Fubuki card". v1 implemented it as
`WHERE ct.name = ?` against the *requested locale's* translation. Measured over the real
2,448-card set, that question does not have one answer:

| | |
|---|---|
| Characters (distinct `ja` names) | **296** |
| Characters spelled inconsistently in ≥1 locale | **122 (41%)** |
| Distinct `en` names | **381** — 85 more than there are characters |

Shirakami Fubuki is the clearest case. Across their 44 cards the `en` translation is:

| spelling | cards |
|---|---|
| `白上フブキ` | 38 |
| `Shirakami Fubuki` | 6 |

So v1's dropdown had *two* Fubuki entries in English, one returning 38 cards and one
returning 6, and neither returning the character. The same split affects `ときのそら` /
`Tokino Sora`, `宝鐘マリン` / `Houshou Marine`, and 119 others.

**What Phase 4 did.** The filter keys on the **source-locale name** — a new indexed
`name_ja` column — so one query returns every card for a character regardless of how
each card spells it. `/api/filter-options` pairs that key with a display label, so the
dropdown still reads in the user's language:

```json
{ "value": "白上フブキ", "label": "Shirakami Fubuki" }
```

Picking that label needed its own rule. Because most cards leave the name untranslated,
the *majority* spelling is usually the Japanese one — taking it would show `白上フブキ`
to an English reader while `Shirakami Fubuki` sat unused in the data. A spelling that
differs from the `ja` name wins instead, which recovers a readable label for 103 of 296
characters in `en` and 65 in `ko`.

**Why this is `open` and not `fixed`.** The API no longer splits a character, and that
part is fixed. What is *not* resolved is the underlying data: 271 of 296 characters have
no romanised `en` name on any card, and the 6-of-44 pattern suggests the official site
translates a name only sometimes rather than never. That is a question about the source
data — is the JP text deliberate on those 38 cards, or did the translation pass skip
them? — and it is the kind of judgement about the *game* that belongs with the
maintainer. Worth checking against `pipeline/corrections/` (ADR 0002 makes a correction
a cache entry), because a handful of manual entries would give every character a proper
label in every locale.

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

## F-017 — Cloudflare's managed `robots.txt` inverts our `Disallow` 🔍 accepted, deferred

**Found:** Phase 5, on attaching the custom domain · **Affects:** indexing policy while
v1 is still live

Attaching `hololive-ocg-wiki.tskrlabs.com` surfaced a zone-level setting that rewrites
what the site serves. Cloudflare's **managed `robots.txt`** (Security → Bots) prepends its
own block to whatever the origin returns, producing this:

```
# BEGIN Cloudflare Managed content
User-agent: *
Content-Signal: search=yes,ai-train=no,use=reference
Allow: /                       ← Cloudflare's
...Disallow rules for GPTBot, ClaudeBot, CCBot, etc...
# END Cloudflare Managed Content

# START nuxt-robots (indexing disabled)
User-agent: *
Disallow: /                    ← ours
```

**Two `User-agent: *` groups with opposite directives.** Google merges rules from
duplicate groups and resolves an `Allow`/`Disallow` conflict on the same path in favour of
the *least restrictive*, so on this domain `robots.txt` most likely reads as **crawlable**
— the opposite of what ADR 0006 Q10 decided. The `workers.dev` origin is unaffected and
still serves our rule alone; only the zone rewrites it.

**What still holds:** the `noindex, nofollow` meta tag, which is present in the static
HTML a non-JS crawler sees (added in Phase 5 commit 8 precisely because `@nuxtjs/robots`
could not emit it under `ssr: false`). That is the stronger signal — `robots.txt` governs
*crawling*, `noindex` governs *indexing*. But Q10 wanted two independent guards while v1
stays indexed on the same 2,448 cards, and one of them is now inverted.

**Decision (2026-07-27): left as-is for now.** The maintainer accepted the risk rather
than change a zone setting mid-phase, so **`noindex` is the sole indexing guard until
Phase 7.**

That is a deliberate narrowing of ADR 0006 Q10, which wanted two independent guards. It is
defensible: `noindex` is the signal that governs *indexing*, it is in the static HTML a
non-JS crawler sees, and the domain is un-announced. The exposure is a crawler that obeys
`robots.txt` but never parses the HTML — it would crawl the site, though it should still
not index it.

**Revisit at Phase 7**, when this resolves itself: our own rule flips to `Allow`, the two
groups agree, and the AI-crawler `Disallow` rules become genuinely useful. If the site
needs to be hard-blocked before then, the one-click fix is:

> Dashboard → Security → Bots → **Configure Bot Fight Mode** → toggle off
> *"Instruct bot traffic with robots.txt"*.
> (Also at Security Settings → filter **Bot traffic**.) It is a **zone** setting, so it
> also covers `img.hololive-ocg-wiki.tskrlabs.com`.

**Not a bug in our code, and worth knowing generally:** a zone-level Cloudflare feature can
change what a Worker appears to serve. `curl` against `workers.dev` and against the custom
domain returned different bytes for the same path, which is the only reason this was
caught.

---

## F-018 — a translation fix has no reviewable surface 🔍 open

**Found:** Phase 6, writing `CONTRIBUTING.md` · **Affects:** outside contribution

D14's reasoning is explicit about what an outside contributor actually wants to do:
*"the contribution people actually want to make is fixing a bad translation, which is
currently impossible: fixes get overwritten on the next pipeline run. An overlay makes it
a reviewable PR."* The mechanism it named was a committed `corrections/` directory applied
after translation.

**ADR 0002 replaced the mechanism and, without meaning to, the property.** Field-level
caching made a correction durable in a better way — an entry marked `source: "manual"` is
never overwritten, because a field's value comes from the cache rather than from the
model, so there is nothing to overwrite it with. That is strictly better than an overlay
for *durability*.

But the cache lives in `pipeline/locales/`, which is **gitignored** (D1: generated data
lives in R2, not git). So the file a contributor would edit does not exist in a clone, and
`pipeline/corrections/` — which `.gitignore` explicitly carves out as "deliberately NOT
ignored… reviewing them as a PR diff is the point" — is empty and unread by any code.

The result: a translation fix can only be reported, then applied by the maintainer. That
works, and `CONTRIBUTING.md` now says so plainly rather than implying a PR path that does
not exist. But it is a narrowing of D14, and it was silent until someone tried to write
the contributor docs.

**Not fixed in Phase 6, deliberately.** Closing it is pipeline work — deciding what a
committed correction file looks like, how `translate` merges it into the cache, and how a
correction is verified without a Poe key — which deserves its own design pass. The repo is
also private until Phase 7, so there is no contributor being turned away today.

**Options when it is picked up**, none chosen yet:

- A committed `pipeline/corrections/{locale}.json` that `translate` folds into the cache
  as `source: "manual"` entries. Closest to D14's intent; the directory already exists.
- Commit the manual entries only — a filtered projection of the cache, which is small
  (most fields are machine-translated) and diffs cleanly.
- Leave it as issue-driven and delete the empty `corrections/` carve-out, which currently
  documents a mechanism that does not exist.
