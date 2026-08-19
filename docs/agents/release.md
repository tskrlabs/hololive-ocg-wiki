# Releasing: two modes, one of which is not a release

The skill is `.claude/skills/release/`. This file is why it is shaped the way it is; the
skill itself is the procedure.

## The distinction it encodes

**A card-set update is not a release.** That is the decision everything else follows from,
and it is not obvious, so it is worth stating the reasoning rather than the rule.

The API reads D1 and R2 directly. When `seed` and `publish` finish, cards, images and card
pages are live — no deploy, no version, nothing to publish. `/status` and `/about` fetch
`status.json` from R2 **at runtime**, so the card count and the seed date are already
current on the site before anyone has merged anything. D26 built that surface precisely so
the site could report what the official card list did, and it works.

So version-bumping for card data would duplicate a live surface with a stale one.
`content/changelog.json` is imported at **build time**, so a card count written there is
wrong the moment the next seed runs. The freshness question already has a better answer than
a changelog entry can give.

What a card update *does* need a deploy for is the **sitemap**, and only that.
`packages/schema/data/card-urls.json` is committed because the site's build has no D1 and no
credentials, so `nuxt generate` has no other way to learn which cards exist. New card URLs
are therefore uncrawlable until a merge to `main`. Worth knowing when planning: the data
goes live immediately, the crawlable surface waits.

## Why one skill with two modes

The two jobs differ completely at the head — a card run starts with a cache backup and hours
of scraping, a site release starts with writing release notes — but they share the tail, and
the tail is where the mistakes live: merging via PR because `main` will not fast-forward,
the post-deploy verification sweep, and the judgement about whether to tag. Two skills would
duplicate that and drift apart. One skill with two modes keeps the shared part shared.

## The judgement calls, and why they went that way

**One approval checkpoint, not three.** The pipeline has three gated steps — translation
spend, R2 publish, D1 writes. D10 made each explicit on purpose, and a skill that types
`--confirm` unattended defeats the design. But stopping three times is friction that
encourages approving unread, which is the failure D10 was actually guarding against. So
everything free runs unattended, and the three numbers are presented together, once.

**Resume by inspection, not by state file.** Every pipeline step already reports whether it
has work to do, so the skill asks the pipeline where it is rather than remembering. A state
file would be a second source of truth that can disagree with the filesystem — the exact
problem ADR 0004 avoided by making D1 its own diff baseline.

**A tight allowlist for "data-only", not a path heuristic.** Detecting whether code rode
along with a card run cannot be done by directory: `packages/schema/data/card-urls.json` is
data and `pipeline/src/holo_data/cli.py` is code, and both sit under directories a heuristic
would call one or the other. The allowlist is two paths, and anything else stops the run.
A new file appearing in a data run is exactly the case worth flagging, and an allowlist
flags it by default where a heuristic would absorb it silently.

**The skill drafts the Discord post; the maintainer posts it.** Posting is outward-facing
and effectively irreversible — a deletion does not unsend it. The numbers should come from
`seed`'s own diff rather than from recollection, which is the part worth automating.

**Verification never rolls back.** The failure mode after a deploy is "live but wrong", and
unwinding that unattended can compound it. Stop and report.

## Two traps, both learned the hard way

**Do not pipe a long pipeline step to `tail`.** Python block-buffers into a pipe, so an hour
passes with no output and a working run is indistinguishable from a hung one. `scrape` also
holds all raw HTML in memory and writes it only at the very end, so killing it on a wrong
guess loses the entire fetch. Run it with `nohup` to a log file and poll.

**Check nothing is already running before starting one.** `pgrep -f` patterns miss these
processes easily, because `uv run` execs a child under the venv path. Getting it wrong means
two scrapes hitting a small operator's site concurrently, which happened once during the
2,559 update and is the reason the check is written into the skill.

**`noindex` cannot be grepped naively.** The string appears in an inert `robotsDisabledValue`
config blob in the bundle, so a healthy page matches it. Check for a real
`<meta name="robots">` tag and the `X-Robots-Tag` header instead.

## The three version numbers

Only `content/changelog.json` is a release version. `APP_VERSION` in
`apps/web/app/constants/app.ts` is a **frozen** deck-persistence format version (ADR 0006
Q11) that lives in `localStorage` and in shared deck-code URLs — bumping it with a release
would strand decks already in the wild. `apps/web/package.json`'s version is inert.

They are *supposed* to disagree. Do not reconcile them.
