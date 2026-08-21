# content/

Editorial copy for the site. **Source, not build output** — edited by hand, reviewed as a
diff, uploaded to R2 by `holo-data publish`.

## `info.json`

The about/disclaimer panel. v1 fetched this from
`raw.githubusercontent.com/…/main/public/info.json` — a live production dependency on a
git URL, which breaks the moment a repo is renamed or made private. D11 moves it to R2:
same edit-without-redeploying property, no GitHub in the production path.

The site reads it from **`GET /api/info`**, which streams the R2 object through the
Worker (`apps/api/src/routes/artifacts.ts`). The bucket is private, so the Worker is the
only way in — which is also what keeps the 21 MB `cards.json` beside it unreachable.

**It deliberately carries no facts about the card data.** v1's copy embedded
*"Our database has 2448 cards (June 19, 2026)"* in the prose, hand-updated and therefore
permanently out of date. That sentence is gone: **the card count and last-updated date
come from `GET /api/status`**, which carries `counts.total` and `generated_at` written by
the seeder against the database itself.

> Corrected in Phase 5. This file previously said the count came from `cards.json`
> "which the site already loads" — it does not. `cards.json` is 21 MB and D8 moved all
> querying to D1; nothing in the frontend fetches it. See
> [ADR 0006](../docs/adr/0006-website.md).

Keep it that way. A number in this file is a number nobody will remember to change.

## `changelog.json`

The release notes `/changelog` renders. **Committed and imported at build time — not
published to R2**, which is the one way it differs from its neighbour above.

The reason is that a release note is tied to a *deploy*. `info.json` describes the project
in general and can meaningfully be corrected between deploys; a changelog entry describes
what a particular build changed, so publishing it independently only creates the state
where the site claims a feature the running code does not have. Importing it means the
entry and the code it describes ship together, and the page cannot be empty because a
fetch failed.

**Entries are English only**, deliberately, and the page says so — the same rule the
privacy section on `/about` follows (ADR 0009 D27). Only the page chrome is translated.
Seven translations per release is a per-release tax on writing one at all, and a
mistranslated "this is fixed" is worse than an honest English one.

`kind` is one of `added`, `changed` or `fixed`. Newest release first — the page does not
sort *releases*.

**It does group changes.** Within a release the page buckets entries by `kind` and renders
one badge per bucket, in the order **added → changed → fixed**, so the order you write them
in does not reach the reader. Write each entry to stand on its own; if a release needs a
narrative, it goes in `summary`, which is prose and is rendered where you put it. A `kind`
that is none of the three still renders — under its own literal label, which is ugly on
purpose, because the alternative is an entry that silently disappears.

**Open gaps do not go here.** They belong in the GitHub release body, whose reader is
deciding whether to contribute; on the player-facing page a list of caveats sits next to
the entry saying the thing was fixed and undercuts it. The page's `Release` type has no
field for them, so adding one to this file renders nothing rather than half-working.

Adding a release means editing this file **and** `docs/releases/`, which is the body of
the GitHub release. They are written from the same facts and for different readers.

## Publishing a change

```bash
holo-data publish --artifacts-only     # or plain `publish`, which does both
```

This uploads `info.json` only. `changelog.json` is not an artifact and `publish` does not
look at it.

No site redeploy needed — the file is read from R2 at runtime.

**One caveat worth knowing** (recorded in ADR 0006): because this file is *committed*,
editing it is already edit → commit → publish, and under Workers Builds a commit
auto-deploys anyway. The edit-without-redeploy property is thinner than when D11 was
written. R2 is kept for consistency with `status.json`, which is written by `seed` and
has no committed copy.
