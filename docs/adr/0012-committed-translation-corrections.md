# ADR 0012 — Committed translation corrections

**Status:** accepted
**Date:** 2026-08-21
**Restores:** D14's reviewable overlay, on top of
[ADR 0002](0002-field-level-translation-cache.md)'s durability and
[ADR 0008](0008-content-addressed-translations.md)'s key
**Closes:** [#18](https://github.com/tskrlabs/hololive-ocg-wiki/issues/18)

## Context

D14 promised outside contributors a reviewable path for the fix people actually want to
make: *"the contribution people actually want to make is fixing a bad translation, which
is currently impossible: fixes get overwritten on the next pipeline run. An overlay makes
it a reviewable PR."* The mechanism it named was a committed `corrections/` directory
applied after translation.

ADR 0002 replaced that mechanism and, without meaning to, the property. Field-level
caching made a correction durable in a *better* way — an entry marked `source: "manual"`
is never overwritten, because a field's value comes from the cache rather than from the
model, so there is nothing to overwrite it with.

But the cache lives in `pipeline/locales/`, which is gitignored per D1 and is 8.7 MB. The
file a contributor would edit does not exist in a clone. So for a year the honest answer
in `CONTRIBUTING.md` was *"this has to go through an issue, not a pull request"*, and
three artefacts documented a mechanism that did not exist: an empty `pipeline/corrections/`
directory, a `.gitignore` carve-out explaining why it was not ignored, and a
`corrections_file()` helper in `paths.py` called by nothing.

ADR 0008 closed the **proper-noun half** — `glossary/` is committed, diffable, and is
where a character's romanisation is fixed. What stayed open is a correction to an
arbitrary *field*: a badly worded effect, a wrong Q&A answer.

**Two things changed that make this cheap now.** ADR 0008 re-keyed the cache on the source
string, so a correction is addressable without a card path. And
[#78](https://github.com/tskrlabs/hololive-ocg-wiki/issues/78) produced the real report the
2026-08-02 triage was waiting for — a wrong-source translation on `hBP02-095`, which is
exactly the arbitrary-field case with no committed home.

## Decision

`pipeline/corrections/{locale}.json` holds hand-written translations, committed. The cache
folds them in on load and **holds them back on save**, so a correction lives in exactly one
place.

```json
{
  "locale": "tc",
  "corrections": [
    {"kind": "art_name", "source": "おつルーナ", "value": "辛苦啦露娜～", "note": "F-003"}
  ]
}
```

### D1 — the key is derived, never written

An entry names its `kind` and the Japanese `source`; the cache key
(`art_name:b8ad10fc…`) is computed by the same `unit_key` the pipeline uses.

A contributor must not have to run sha256 to send a one-line PR — that alone would make
this as unusable as the gitignored cache it replaces. A stored key is also a second place
for one fact to live, and #78 is precisely what that costs: a value keyed to one source
while holding another is invisible until a reader finds it.

The check that replaces a stored key is stronger and needs no API key. `holo-data
corrections` looks up every `(kind, source)` in the current build and reports any that no
card prints, so a typo in the Japanese is a loud *"no card prints this string"* rather than
an entry that quietly matches nothing. That also catches a correction stranded by the
official site rewording a card — the same key-moved-underneath-us shape as #78, but
reported instead of silent.

### D2 — a list, not a hash-keyed object

Nothing in this file should require a tool to write. An object keyed by content address
would be marginally cheaper to load and would put a 64-character hash in front of every
contributor.

### D3 — corrections are held back from the cache blob

`save` excludes entries that came from `corrections/`. Round-tripping them would leave a
copy that no diff shows, and deleting a correction from the committed file would not
remove it — the fix would be un-revertable, which is a worse failure than the one this
closes.

### D4 — pre-existing `manual` entries are tracked, not inferred

`from_corrections` records which keys were folded in, rather than dropping everything
marked `manual` on save. The two sets are not the same during the one run that matters: a
cache written before this mechanism existed holds `manual` entries of its own, and
silently dropping those would delete hand-written translations that have no committed home
yet. `holo-data corrections --extract` moves them across; until it runs, they stay, and
they are reported as orphans so they get moved rather than discovered years later.

### D5 — reading a named file describes that file

Corrections are folded in for the *working* cache, not for an arbitrary path.
`backup.stats_for` verifies a snapshot by loading it and counting `manual` entries; folding
the repo's corrections into that read would report a count including entries the snapshot
does not contain, breaking the one check that proves a backup is restorable.

## Consequences

**A translation fix is a PR.** `CONTRIBUTING.md` documents the file, the field kinds, and
the exact-match rule on `source`. No Python toolchain, no Poe key, and no card data are
needed to write one.

**The three stale artefacts now describe something real.** The directory has contents, the
`.gitignore` carve-out is accurate, and `corrections_file()` has a caller.

**One fix covers every printing.** Content addressing means correcting `おつルーナ` corrects
all three cards that print it — the leverage D14 could not have offered under a per-card
overlay.

**The four F-003 strings are committed at last.** Recovered in Phase 0 from a stray `value`
key, applied to the cache in Phase 3, and deliberately left out of git until there was a
reviewable place to put them. `pipeline/corrections/tc.json` is that place, and they are
its first entries.

**Verification is offline.** Folding a file into a dict is testable without spending money,
which was the third of the three worries that kept #18 open.

**What this does not do.** It does not detect that a translation is wrong — it is the place
to record the fix once a human knows. #78's underlying question, how a fallback hit counts
as fresh, is untouched and stays open.
