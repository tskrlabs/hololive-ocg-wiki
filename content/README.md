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

## Publishing a change

```bash
holo-data publish --artifacts-only     # or plain `publish`, which does both
```

No site redeploy needed — the file is read from R2 at runtime.

**One caveat worth knowing** (recorded in ADR 0006): because this file is *committed*,
editing it is already edit → commit → publish, and under Workers Builds a commit
auto-deploys anyway. The edit-without-redeploy property is thinner than when D11 was
written. R2 is kept for consistency with `status.json`, which is written by `seed` and
has no committed copy.
