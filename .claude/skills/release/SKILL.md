---
name: release
description: "Ship this repo, in one of two modes. Use when the user wants to update the card set from the official site, or cut a versioned site release. Examples: \"the official cards are at 2,559, run the pipeline\", \"update the card data\", \"cut a release\", \"tag v2.1.0 and publish it\", \"deploy the site\""
---

# Releasing hololive-ocg-wiki

Two modes. Pick by what changed, and say which you picked before starting.

| mode | what changed | tag? | invoke |
|---|---|---|---|
| **`cards`** | the official card list published new or edited cards | **no** | `/release cards` |
| **`site`** | code, copy or UI that a visitor can see | **yes**, semver | `/release site` |

If the user's intent is ambiguous, ask. Running `cards` when they meant `site` skips the
release notes; running `site` when they meant `cards` tags data as if it were a feature.

## The model this rests on

**Card data is not a release.** The API reads D1 and R2 directly, so cards, images and card
pages go live the moment `seed` and `publish` finish, with no deploy. `/status` and `/about`
report the card count and seed date from R2 **at runtime**. That is the freshness surface,
and it is already correct without anyone editing a file.

**A deploy is only needed for the sitemap.** `packages/schema/data/card-urls.json` is
committed and baked into the static build, so new card URLs stay uncrawlable until a merge
to `main`. That is the one thing a card run must deploy.

**`/changelog` is site-only and build-time.** It imports `content/changelog.json` at build
time (`#content` alias, `nuxt.config.ts`). Do not add card-set updates to it: it would go
stale on the next seed, and it would duplicate `/status` in a worse place. A version number
in a past changelog entry is a historical record, not a live count. Leave old counts alone.

Three version numbers exist and only one is a release version:

- `content/changelog.json` — the real one, shown at `/changelog`
- `apps/web/app/constants/app.ts` `APP_VERSION` — a **frozen** deck-persistence format
  version (ADR 0006 Q11). It versions a wire format living in `localStorage` and in shared
  deck-code URLs. **Never bump it with a release**; that would strand decks in the wild.
- `apps/web/package.json` — inert, nothing imports it

---

# Mode: `cards`

Full pipeline, then deploy the sitemap. Budget hours, mostly in `scrape`.

## Resume by inspection, never from a state file

The run may already be partly done — a previous attempt, or a step the user ran by hand. Do
**not** keep a progress file. Every step reports whether it has work, so **ask the pipeline
where it is** and start from the first step with work to do:

```bash
uv run holo-data status                 # what is on disk
uv run holo-data translate-units --dry-run
uv run holo-data publish --dry-run
uv run holo-data seed --dry
```

A state file is a second source of truth that can disagree with the filesystem. D1 is its
own diff baseline for exactly this reason (ADR 0004); follow that.

## Long steps: how to run them without losing the work

`scrape` holds all raw HTML in memory and writes `cards_raw_html.json` **only at the very
end**. Killing it loses the whole fetch. Downloaded images survive, since those are written
per file.

**Never pipe a long step to `tail` or `head`.** Python block-buffers into a pipe, so you see
nothing for an hour and cannot distinguish working from hung.

```bash
nohup uv run holo-data scrape > /tmp/holo-scrape.log 2>&1 &
# poll; \r is the progress separator
tr '\r' '\n' < /tmp/holo-scrape.log | tail -3
```

**Check nothing is already running before you start a long step.** `pgrep -f` patterns miss
these processes easily — `uv run` execs a child, so match on the venv path too:

```bash
pgrep -fl "holo-data|holo_data" | grep -v claude
```

Getting this wrong means two scrapes hammering a small operator's site at once. If a scrape
died and the card ids are already fetched, resume with `scrape --skip-ids`.

## The sequence

```bash
# 1. back up the cache FIRST — it is the one file that cannot be rebuilt
uv run holo-data backup-cache --remote

# 2. scrape (long; see above)
uv run holo-data scrape

# 3. images
uv run holo-data images

# 4. build — EXPECTED TO FAIL on a new set, see below
uv run holo-data build

# 5. translation plan (spends nothing)
uv run holo-data translate-units --dry-run

# --- CHECKPOINT: one approval, see below ---

# 6. translate, then build for real
uv run holo-data translate-units --confirm
uv run holo-data build

# 7. publish and seed
uv run holo-data verify-images
uv run holo-data publish
uv run holo-data seed --dry
uv run holo-data seed --confirm

# 8. verify, commit, deploy
make check
```

**Step 4 failing is normal and is not a problem to route around.** New cards have no
translations, so `build` refuses to write. Read the coverage lines it prints, confirm the
failures are all `Field required` on the new cards, and continue to step 5. If it fails for
any *other* reason, stop.

`translate-units` reads the **scrape** (`transform.load_i18n()`), not `cards.json`. It has
to: `build` refuses to write a new set, so the built artifact is the *previous* set, the one
place the new strings are provably absent. Guarded by a test; do not "fix" it back.

## The one checkpoint

Everything through step 5 is free, local and reversible. Steps 6 and 7 spend money and write
to production. Present **one** combined checkpoint and wait for approval:

- **Translation spend** — calls, units and locales from `translate-units --dry-run`. For
  scale: the full cold run was 204 calls / 1,493,321 tokens; a ~96-card set was 48 calls /
  ~87k tokens.
- **Publish** — object count and MB from `publish --dry-run`.
- **D1 writes** — the estimate from `seed --dry`, against the 100k/day free tier.

Never type `--confirm` on the user's behalf without that approval. D10 made these gates
explicit on purpose, and a skill that auto-confirms defeats the design.

## Things that are normal, and things that are not

| observation | verdict |
|---|---|
| `build` fails before translation, `Field required` on new cards | **normal** — that is step 4 |
| a few units rejected: "the model invented N placeholder(s)" | **normal** — the mask guard working. They stay stale; re-run `translate-units --locale <loc> --confirm` to retry just those |
| `verify-images` reports orphan WebP | **normal** if a card left the official list; `publish` only uploads referenced keys |
| `notices.json` empty / 0 notices | **normal** — the official list may carry no rules notice. `publish` and `/api/notices` both handle it |
| PNG count one higher than the card count | **normal** — a long-standing off-by-one in the image tree, not new |
| `transform` or `build` naming an **unmapped enum value** | **STOP.** The official site printed something new. Add the mapping to `mappings.py`; do not reach for `--allow-unknown-enums`, which ships a short artifact `publish` and `seed` will refuse |
| `seed` writes wildly over its estimate | **STOP** and report |

## Committing and deploying

Two commits, separately:

1. any code fix the run required (with a test)
2. `packages/schema/data/card-urls.json` — regenerated by `build`, committed because the
   site's build has no D1 and no credentials

Then update `docs/progress.md` with the run's numbers, so the next update has a baseline.

**Do not tag.** Data is not a release.

**Check whether code rode along.** Diff the merge range and compare against this allowlist:

```
packages/schema/data/card-urls.json
docs/progress.md
```

Anything else in the range means a non-data change is shipping with the cards. **Stop and
say so**, naming the files, and let the user decide whether it warrants a `site` release
afterwards. Do not silently tag it and do not silently skip it. (The allowlist is
deliberately tight: a new file appearing is exactly the case worth flagging.)

Deploy via PR — `main` will not fast-forward, the repo releases through merge commits:

```bash
gh pr create --base main --head develop --title "..." --body "..."
gh pr merge <n> --merge
```

Workers Builds deploys ~90 seconds after the merge. Then run the **verification sweep**
below, polling the sitemap until the new cards appear.

## The Discord post

After verification, **write the post and hand it to the user. Do not post it.** They post
by hand every time.

Source the numbers from `seed`'s own diff, not from memory: added, edited, the new total,
the set code. House style applies — **no em dashes, no emoji** — since it is release copy.
Keep it player-facing: how many new cards, which set, that they are searchable now. Card
counts and set codes, not row counts or token spend.

---

# Mode: `site`

## 1. Release notes come first

`docs/releases/README.md` is the authority. Each release is written **twice**, from one set
of facts:

| file | reader | register |
|---|---|---|
| `docs/releases/vX.Y.Z.md` | contributors, as the GitHub release body | what changed in the system, and why |
| `content/changelog.json` | players, rendered at `/changelog` | what changed on the site they use |

They are deliberately different text. Known gaps go in the **release body only** — a player
reading a caveat beside the fix has the fix undercut.

**House style, enforced: no em dashes and no emoji** in either file. Use commas, colons,
semicolons or separate sentences. This is narrower than the rest of the repo; `docs/adr/`
and `docs/progress.md` use both freely and are unaffected.

If the notes do not exist yet, **draft both files** from the commit range
(`git log --oneline <last-tag>..HEAD`), show the user the diff, and **wait**. They must edit
and commit them before anything is tagged. Do not tag notes the user has not read.

Pick the version by what changed: patch for fixes only, minor for anything added.

## 2. Verify, merge, tag, publish

```bash
make check
make check-site          # site-specific; cards mode does not need it

gh pr create --base main --head develop --title "..." --body "..."
gh pr merge <n> --merge

git checkout main && git pull
git tag -a vX.Y.Z -m "vX.Y.Z: <title>"
git push origin vX.Y.Z

gh release create vX.Y.Z \
  --title "vX.Y.Z: <title>" \
  --notes-file docs/releases/vX.Y.Z.md \
  --latest
```

Merge **before** tagging: the tag must point at a commit on `main` that already contains
everything the notes claim, including `/changelog` rendering the matching entry.

`gh release create` notifies everyone watching the repo. It is the outward-facing step —
confirm with the user before running it. Add `--draft` to stage it invisibly first.

Then run the verification sweep, and offer to draft a Discord post as in `cards` mode.

---

# The verification sweep

Run after every deploy, in both modes. Poll until the deploy lands (~90s), then check all of
it. **On failure, stop and report. Never roll back automatically** — the failure mode is
"deployed but wrong", and unwinding that unattended can make it worse.

```bash
API=https://hololive-ocg-wiki.tskrlabs.com

curl -s "$API/api/health"                                    # {"ok":true}
curl -s "$API/api/status"  | jq '.counts.total'              # the new card count
curl -s "$API/api/info"    | jq '.contents | length'         # 3
curl -s "$API/api/cards/search?q=フブキ" | jq '.cards|length' # grows with the set
curl -s "$API/api/filter-options?locale=en" | jq '.names|length'
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/cards/search?q=a%20AND"   # 200, not 500

curl -s -o /dev/null -w '%{http_code}\n' "$API/en/"                          # 200
curl -s -o /dev/null -w '%{http_code}\n' "$API/en/card/<set>/<stem>"         # 200
curl -s -o /dev/null -w '%{http_code}\n' "$API/en/card/<set>/NOPE"           # 404
curl -s "$API/en/card/<set>/<stem>" | grep -o 'og:title[^>]*'                # injected

curl -s "$API/__sitemap__/en-US.xml" | grep -c '<url>'       # grew
curl -s "$API/robots.txt" | head -3                          # Allow: /
```

**Check `noindex` correctly.** A naive `grep -c noindex` returns 1 on every healthy page:
the string appears inside an inert `robotsDisabledValue` config blob in the bundle. Check
the real directives instead — both should be empty:

```bash
curl -s  "$API/en/card/<set>/<stem>" | grep -oE '<meta[^>]*name="robots"[^>]*>'
curl -sI "$API/en/card/<set>/<stem>" | grep -i 'x-robots-tag'
```

## Optional, and never automatic

`verify-images --remote` is the only check that catches **wrong** artwork — it re-fetches
every image from the official site and compares bytes. It once found 12 stale images the
coverage check called fine (F-012). It is also ~2,560 requests to a small operator's site.

After a set that added images, **mention it and let the user decide.** Do not run it by
default, and never in a loop.

---

# Reference

- `docs/releases/README.md` — the release convention and house style
- `docs/progress.md` — the working log; every run's numbers go here
- `pipeline/README.md` — the pipeline's own gotchas
- `docs/agents/release.md` — why this skill is shaped the way it is
- **Never add GitHub Actions.** Verification is local (`make check`); the maintainer has had
  an account banned over Actions usage. Workers Builds is unaffected: it runs on Cloudflare
  and GitHub only sends a webhook.
