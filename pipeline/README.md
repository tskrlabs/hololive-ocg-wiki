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
holo-data status          # what is on disk right now

holo-data publish         # -> R2      (Phase 2)
holo-data seed            # -> D1      (Phase 3)
```

The order is D10's gated flow: everything before `publish` is local and reversible, and
the steps that cost money or touch production are explicit. `translate` refuses to run
without `--confirm` and reports exactly what it would spend under `--dry-run`.

## Setup

```bash
make setup                      # from the repo root
cp pipeline/.env.example pipeline/.env
# add POE_API_KEY — only needed for `translate`
```

`scrape`, `images`, `build` and `verify` need no credentials.

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

## Working state

Everything under `pipeline/` except `corrections/` is gitignored working state,
reproducible by re-running:

```
data/default/   card ids, raw HTML, structured extraction, contract shape
locales/        translations + the field-level cache
images/png/     downloaded originals (local intermediate — never uploaded)
images/webp/    what `publish` uploads (D9)
build/          cards.json
```

Per D1 the published artifacts live in R2, not git.

## Gotchas

- **Do not tidy `scrape/extract.py`.** Its 30+ selectors are verbatim from v1 and several
  branches exist for a handful of cards each. Change it only with a card-by-card diff via
  `holo-data verify`.
- **The prompts in `translate/prompts.json` are verbatim too.** They encode which fields
  must *not* be translated (proper nouns, anything in 〈〉, rarity/set/cardType). They are
  data, not code, so they can be edited without touching Python — but edits change
  translation quality.
- **The 特攻 icon appears in `cost_icons`.** It is a bonus-damage marker, not a cost. It
  is filtered out of `cost_types` but still counted in `cost_count`, because that is what
  v1 shipped.
- **A keyword's type is its icon's `alt`,** not its `name` — `name` is the ability's own
  title.
- **The cache starts empty.** A first `translate` on a fresh clone would be a full run.
  Seed it from v1's `cards.json` instead (see ADR 0002).
