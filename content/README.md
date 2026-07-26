# content/

Editorial copy for the site. **Source, not build output** — edited by hand, reviewed as a
diff, uploaded to R2 by `holo-data publish`.

## `info.json`

The about/disclaimer panel. v1 fetched this from
`raw.githubusercontent.com/…/main/public/info.json` — a live production dependency on a
git URL, which breaks the moment a repo is renamed or made private. D11 moves it to R2:
same edit-without-redeploying property, no GitHub in the production path.

**It deliberately carries no facts about the card data.** v1's copy embedded
*"Our database has 2448 cards (June 19, 2026)"* in the prose, hand-updated and therefore
permanently out of date. That sentence is gone: the card count and last-updated date come
from `cards.json`'s own `generated_at` and card count, which the site already loads.

Keep it that way. A number in this file is a number nobody will remember to change.

## Publishing a change

```bash
holo-data publish --artifacts-only     # or plain `publish`, which does both
```

No site redeploy needed — the file is read from R2 at runtime.
