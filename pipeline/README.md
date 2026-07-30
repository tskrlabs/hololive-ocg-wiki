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
