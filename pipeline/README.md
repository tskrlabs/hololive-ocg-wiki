# `holo-data` — the data pipeline

Scrapes the official Hololive card game site, translates the cards, and produces the
canonical `cards.json` that Phase 2 publishes to R2 and Phase 3 seeds into D1.

Python, per decision D3 — the scrapers encode a year of knowledge about the official
site's HTML and a rewrite's best case is "works exactly as before". See
[ADR 0002](../docs/adr/0002-field-level-translation-cache.md) for the Phase 1 decisions.

## Commands

```bash
holo-data scrape          # official site -> raw HTML + images   (local, free)
holo-data images          # PNG -> WebP q90                      (local, free)
holo-data translate       # Poe API                              ($$ — needs --confirm)
holo-data build           # merge + validate -> cards.json       (local, free)
holo-data verify          # diff against v1's data               (local, free)
holo-data verify-images   # coverage; --remote re-checks bytes   (local / ~2.4k reqs)
holo-data status          # what is on disk right now
holo-data glossary        # proper-noun coverage, per locale     (local, free)
holo-data report-masks    # rehearse masking over every string   (local, free)
holo-data backup-cache    # snapshot the translation cache       (--remote adds R2)

holo-data publish         # images + artifacts -> R2   (needs CF credentials)
holo-data seed            # -> D1      (Phase 3)

holo-data migrate-images  # one-time: v1's flat images -> the set-scoped tree
```

The order is D10's gated flow: everything before `publish` is local and reversible, and
the steps that cost money or touch production are explicit. `translate` refuses to run
without `--confirm` and reports exactly what it would spend under `--dry-run`.

**`publish` takes no `--confirm`** — uploading is cheap and idempotent, so a confirmation
flag would only teach the habit of typing it unread before `seed` asks for it. What it
checks instead are facts: that `cards.json` is newer than its inputs, and that every card
has an image. See [ADR 0003](../docs/adr/0003-r2-publish.md).

## Setup

```bash
make setup                      # from the repo root
cp pipeline/.env.example pipeline/.env
# add POE_API_KEY — only needed for `translate`

uv sync --extra publish         # adds boto3 — only needed for `publish`
```

`scrape`, `images`, `build`, `verify` and `verify-images` need no credentials.
`publish` needs R2 credentials and `boto3`; see [`docs/infra.md`](../docs/infra.md).

## Translation is incremental

The translation cache hashes **each field separately**, so a changed Q&A entry
re-translates that entry and nothing else. On real data, 2,228 of 2,448 cards need no
work on a typical update — v1 re-translated all of them.

```
holo-data translate --dry-run
  en: 220 cards to send (254 stale fields), 2228 already current
```

**Fixing a bad translation** — edit the value in `locales/translation-cache.json` and
mark it manual:

```json
"2314": {
  "name": {"hash": "abc…", "value": "IRyS", "source": "manual"}
}
```

Nothing overwrites it. As long as the JP source has not changed, that field is never
stale, so `translate` skips it even when the rest of the card is re-sent. This is what
replaces D14's corrections overlay.

## `glossary/` is source, and it is committed

`pipeline/glossary/{names,sets,tags}.json` holds the curated translations of proper nouns
— 296 card names, 35 sets, 41 tags — keyed on the **source-language string**.

Everything else the pipeline translates is prose, and prose can be machine-translated per
string. Proper nouns cannot: `一伊那尓栖` is "Ninomae Ina'nis", and no model produces that
reliably. They also have to be *identical everywhere they appear*, which is the defect
[#20](https://github.com/tskrlabs/hololive-ocg-wiki/issues/20) and
[#21](https://github.com/tskrlabs/hololive-ocg-wiki/issues/21) record.

Three consumers read this one file, which is why it is one file:

- **`translate`** masks these strings out before text goes to the model and restores them
  after, so the model never sees a character name and cannot spell it two ways.
- **`build`** labels the filter dropdowns from it.
- **The site** displays from it — `apps/web/i18n/locales/*.json`'s `names`, `sets` and
  `tags` maps are **generated** by `make generate` and `make check` fails if they drift.
  Edit the glossary, not the locale files.

```bash
holo-data glossary              # coverage per locale
holo-data glossary --missing    # which keys still have no decision
```

**Identity is the source string; display is per-locale.** The same rule `Card.tags` and
`name_ja` already follow. Tag entries key on `Card.tags` (`"0期生"`), not the prefixed
display text (`"#0期生"`) — keying on the prefix is what made the tag filter match nothing
([#26](https://github.com/tskrlabs/hololive-ocg-wiki/issues/26)).

**Aliases** cover the short forms characters are referred to by — `おつルーナ`, `おつムーナ`.
They are masked longest-first, and an alias claimed by two characters is rejected outright
rather than silently resolving to whichever was matched first.

## Masking: names are removed, not asked about

`translate` does not ask the model to leave names alone — it takes them out first:

```
白上フブキのこんこん  ->  [[N0]]のこんこん  ->  [[N0]]'s Konkon  ->  Shirakami Fubuki's Konkon
```

The name comes back from the glossary, so every occurrence on every card gets the same
spelling **by construction**. The old prompt asked politely and was obeyed 47–81% of the
time, which is what #20 and #21 measure.

Three rules, each forced by the real data:

- **Longest first.** 75 pairs in the table nest — `森カリオペ` inside `森カリオペの鎌`,
  `Promise` inside `時の支配者 -Promise-`. Masking the short one strands a fragment.
- **Katakana word boundaries.** `トワ` is Tokoyami Towa *and* the first two syllables of
  `トワイライト`. Adjacency decides, per occurrence: `トワとトワイライト` masks the first
  only.
- **One pass.** A token like `[[N0]]` is ASCII and so is a name like `35P`, so a second
  pass could match inside a token it just wrote. The masker never re-reads its own output.

**Failure is loud.** If the model drops, mangles or invents a placeholder, `unmask` raises
and the unit is not cached. A half-restored string would be plausible, published, and
found by a reader months later.

```bash
holo-data report-masks     # every string masked and restored, offline
```

Verified over the full corpus: **21,205 strings, 7,023 (33%) carrying a name, zero
round-trip failures.** `make check` runs the same sweep.

## The cache is the one thing you cannot re-run

`locales/translation-cache.json` is **not** reproducible working state, despite living
among files that are. It is the accumulated output of a year of paid Poe calls — 82,098
entries across 6 locales — and re-creating it means paying for it again. It is also
gitignored, and `publish` does not upload it.

So back it up before anything touches it:

```bash
holo-data backup-cache --remote
```

That writes a dated snapshot to `~/.holo-data/cache-backups/` (outside the repo, so
`git clean -fdx` cannot take it) and a copy to `backups/` in the artifacts bucket. Both
are verified by loading the copy back and comparing entry counts per locale — a truncated
write fails at backup time rather than at the restore nobody rehearsed.

To restore, put a snapshot back at `locales/translation-cache.json`. `holo-data status`
will then report the entry counts, which is the check that it worked.

## Working state

Everything else under `pipeline/` except `corrections/` is gitignored working state,
genuinely reproducible by re-running:

```
data/default/         card ids, raw HTML, structured extraction, contract shape
locales/              translations + the field-level cache (⚠ see above — back this up)
images/png/{set}/     downloaded originals (local intermediate — never uploaded)
images/webp/{set}/    what `publish` uploads (D9)
build/                cards.json
```

Per D1 the published artifacts live in R2, not git.

**The `{set}` folder is not decoration.** A WebP's path relative to `images/webp/` *is*
its R2 object key, which is what lets `publish` sync without consulting `cards.json`. It
is also load-bearing for correctness: `hBP03-044_SR.png` exists under both `hBP03` and
`hCO01` as **different artwork**, and a flat directory can only hold one of them — see
[F-006](../docs/archive/findings.md#f-006), which is exactly how v1 shipped one card's art for
two cards.

## Gotchas

- **Do not tidy `scrape/extract.py`.** Its 30+ selectors are verbatim from v1 and several
  branches exist for a handful of cards each. Change it only with a card-by-card diff via
  `holo-data verify`.
- **The prompts in `translate/prompts.json` are verbatim too.** They encode which fields
  must *not* be translated (proper nouns, anything in 〈〉, rarity/set/cardType). They are
  data, not code, so they can be edited without touching Python — but edits change
  translation quality.
- **The 特攻 icon appears in `cost_icons`.** It is a bonus-damage marker, not a cost, so
  it is filtered out of `cost_types` by its `tokkou_` filename. v1 also emitted a
  `cost_count` taken from the *unfiltered* list, so it read one high on the 482 arts with
  a 特攻 icon; v2 does not emit that field at all — `len(cost_types)` is the count
  (F-002).
- **A keyword's type is its icon's `alt`,** not its `name` — `name` is the ability's own
  title.
- **The cache starts empty.** A first `translate` on a fresh clone would be a full run.
  Seed it from v1's `cards.json` instead (see ADR 0002).
- **`download_image` skips by *key*, not filename.** Skipping by filename is what caused
  F-006. If you touch that logic, keep the set folder in the comparison.
- **`verify-images --remote` is the only check that catches wrong artwork.** Coverage
  says an image exists; only re-fetching the source says it is the *right* image. Run it
  after any migration, and never in a loop — it is ~2,450 requests to a small site.
