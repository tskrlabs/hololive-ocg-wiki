# docs/releases/

The body of each GitHub release, committed.

Written here rather than typed into the GitHub web form for the reason every other
generated artifact in this repo is committed: a release body that exists only on GitHub is
a document with no diff, no review and no local copy. `gh release create --notes-file`
reads it from here.

## House style

**No em dashes and no emoji in release copy.** Use commas, colons, semicolons or separate
sentences. This covers the files in this directory and `content/changelog.json`.

It is deliberately narrower than the rest of the repo: `docs/progress.md` and `docs/adr/`
use both heavily and are unaffected. Those are working notes for people already here.
Release copy is the first thing a stranger reads, and the maintainer wants it to read as
written by a person.

## The two audiences

Each release is written **twice**, from one set of facts:

| file | reader | register |
|---|---|---|
| `docs/releases/vX.Y.Z.md` | contributors, as the GitHub release body | what changed in the system, and why it was built that way |
| `content/changelog.json` | players, rendered at `/changelog` | what changed on the site they use |

They are deliberately not the same text. A player does not care that the card contract is
generated from pydantic; a potential contributor is not served by "now with card names on
the grid". Writing one and pasting it into both surfaces produces a document that
half-serves each.

Open gaps go in the release body only, not in `changelog.json`. The reader deciding whether
to contribute needs the caveats; the reader using the site sees them next to the entry
saying the thing was fixed, which undercuts it.

Both files are updated in the same commit as the work they describe.

## Publishing a release

The tag must point at a commit on `main` that already contains everything the notes claim,
including the `/changelog` page rendering the matching `content/changelog.json` entry.
Merge first, then tag.

```bash
# 1. verify locally, on the commit you are about to tag
make check
make check-site

# 2. tag it, annotated, so the tag carries its own message and date
git checkout main && git pull
git tag -a v2.0.0 -m "v2.0.0: the rebuild"
git push origin v2.0.0

# 3. create the release from the committed body
gh release create v2.0.0 \
  --title "v2.0.0: the rebuild" \
  --notes-file docs/releases/v2.0.0.md \
  --latest
```

To preview without publishing, add `--draft` to the last command. The release is then
visible only to maintainers until you press publish.

**Note:** `gh release create` notifies everyone watching the repository. It is the
outward-facing step, and it is worth doing deliberately rather than as part of a merge.
