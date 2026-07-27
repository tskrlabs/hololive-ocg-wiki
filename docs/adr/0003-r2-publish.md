# ADR 0003 — R2 layout, and what `publish` refuses to do

**Status:** accepted · **Phase:** 2 · **Date:** 2026-07-26

Decided in a grilling session before implementation, as with Phases 0 and 1.

## Context

D1 puts card images and generated artifacts in R2 rather than git. D9 stores an
`image_key` and composes URLs at render time. Phase 2 turns those decisions into
resources and a `holo-data publish` that is idempotent.

Four questions were open going in: whether `publish` diffs against R2 or re-uploads
blindly, whether `info.json` is written by the pipeline or by hand, whether the bucket
gets a custom domain now or at launch, and whether `publish` needs a `--confirm` gate.

## Decisions

### Two buckets, not one

`hololive-ocg-wiki-images` is public behind `img.hololive-ocg-wiki.tskrlabs.com`.
`hololive-ocg-wiki-artifacts` is private — the Phase 3 seeder reads it over the S3 API,
the Phase 4 Worker over a binding.

The images bucket's security model is "everything in it is world-readable forever."
Artifacts have a different lifecycle: replaced per run, and not something we want
hot-linked. Splitting them means we never have to reason about whether a given key is
safe to expose. A second bucket costs nothing — the free tier is per account.

### The local image tree is set-scoped — a Phase 1 amendment

`images/png/{set}/{stem}.png` and `images/webp/{set}/{stem}.webp`, mirroring
`Card.image_key` exactly. `publish` walks the WebP tree and uses each relative path as
the object key, with no lookup against `cards.json`.

Phase 1 wrote both trees flat, which was a latent bug rather than a style choice. v1's
`download_image()` skips any filename already on disk, and **F-006** turns out to be two
cards that share a filename across sets while being *different artwork*: `hBP03-044_SR`
exists under both `hBP03` and `hCO01` with different illustrators. All four images were
fetched and hashed during the grilling to confirm it. A flat tree physically cannot hold
both, so v1 has been serving one card's art for both members of each pair.

`CardCollection`'s duplicate-key guard catches the *key* collision but not the *file*
collision — two keys can still point at one flat file. The set-scoped tree is what makes
the guard meaningful.

Changed during Phase 2 rather than deferred because `pipeline/images/` was empty in this
repo: the migration cost was zero before the first full scrape and a 1 GB re-download
after it.

### `publish` diffs by listing R2

One paginated `ListObjectsV2` (~3 Class A ops for the full set) against a 1M/month
allowance, comparing size first and MD5/ETag only for survivors.

The alternative — a local `published.json` manifest — is faster but remembers rather than
observes. R2 is authoritative about R2, which matters precisely because the CLI may be
agent-driven (D4) and a stale manifest is the kind of silent wrongness that is hard to
notice. `--force` re-uploads everything; `--dry-run` reports without acting.

`publish` never deletes. An object in the bucket that no local file matches is left
alone.

### No `--confirm`; two real gates instead

D10 gates steps that cost money or are irreversible. `publish` is neither: image keys are
immutable by construction, the diff makes a re-run a no-op, and ~3,000 uploads is 0.3% of
the monthly allowance.

A `--confirm` here would also not protect against the failure that actually happens. An
agent will pass `--confirm` as readily as a human, and a human who mistypes a command
believes their build is current. So the gates are facts rather than ceremony:

1. **Staleness** — `cards.json` must be newer than `cards_i18n.json` and the translation
   cache. Publishing a stale artifact is the realistic mistake.
2. **Coverage** — every card's `image_key` must resolve to a local WebP, or the run
   fails with the list. A card without an image is a broken tile.

The artifact is also re-validated against `CardCollection` before upload, which is where
the duplicate-key check fires.

### Custom domain now, `r2.dev` disabled

`r2.dev` URLs are rate-limited, documented as development-only, and get **no Cloudflare
cache** — every image view would be a Class B op against the bucket. A custom domain puts
the CDN in front, which is what keeps reads near zero.

Enabling a custom domain does not disable `r2.dev`; that is a separate step and it is in
the runbook. Leaving both on would mean an uncached, rate-limited path into the same
objects that we could never retract once something hot-linked it.

Doing it now rather than at launch also avoids changing every configured `base_url` at
the worst possible moment.

### Cache headers set explicitly at upload

Images get `public, max-age=31536000, immutable`; artifacts get `no-cache`. Content types
are set explicitly too, rather than left to R2's inference.

Relying on Cloudflare's default cached-extension list would make our cache behaviour a
property of a provider default — invisible in review, changeable without notice. An
explicit header is in `publish` and shows up in a diff.

The immutable year is safe because keys encode set and print. The trade-off is that
replacing an image in place would leave clients on old bytes; if a whole-set re-encode
ever happens, it should use a version prefix rather than overwrite.

### `boto3`, as an optional extra

R2 speaks S3. Hand-rolling SigV4 to save 27 MB is a bad trade — the failure mode is a
signature mismatch against a service that cannot be debugged locally. Shelling out to
`wrangler r2 object put` is worse: it uploads one object per process invocation, so ~3,000
Node startups.

It is an extra (`uv sync --extra publish`) because only the maintainer can publish (D14),
and a contributor who only scrapes and builds should not pay 27 MB for it. Missing
`boto3` produces the install command, not an `ImportError`.

Multipart is disabled below 512 MB so ETags stay plain MD5s — a multipart ETag is a
composite hash and would break the diff for the ~22 MB `cards.json`.

### `info.json` is committed editorial copy

It lives at `content/info.json`, is uploaded by `publish`, and **carries no facts about
the card data**. v1's copy embedded *"Our database has 2448 cards (June 19, 2026)"* in
its prose, hand-updated and permanently stale. That sentence is gone; the count and date
render from `cards.json`'s `generated_at` instead.

Committed rather than dashboard-managed because the disclaimer is a legal statement about
Cover Corp's derivative-works guidelines, and that specifically should have review and
history. D11's "edit without redeploying" property survives: the file goes to R2, so
changing copy still needs no site deploy.

*Creates a Phase 5 dependency:* the site reads the card count from the artifact, not from
`info.json`.

### `verify-images`, split by cost

Coverage is a set difference — free, and a hard gate on every `publish`. Provenance
re-fetches every `source_image_url` and compares bytes — ~2,450 requests, so it is
opt-in via `--remote` and never implicit.

Provenance exists because coverage would not have caught F-006: both cards *had* an
image. Only comparing bytes against the source tells you it is the wrong one. Run once
after the migration to prove the set, then only when something looks wrong.

### `migrate-images` copies rather than re-scrapes

v1's ~2,450 flat PNGs are copied into the set tree using the `imageUrl` recorded per
card. Re-scraping would be correct too, but it means ~2,450 requests to a small
operator's site for files already on disk, and the scraper's whole posture is to stay a
good citizen.

Files whose name is claimed by two cards are **re-fetched, never copied**: the flat file
is one of the two prints and which one is not recoverable, so copying it to both keys
would assign one card's art to the other — the exact bug being fixed.

It copies rather than moves. The source directory is the only complete set of these
images.

## Consequences

- `publish` is idempotent: a second run uploads nothing and says so.
- Two cards that shared an image in v1 now have separate artwork all the way to the CDN.
- A contributor without Cloudflare credentials can still run everything up to `build`.
- The infra config is in git for the first time — partially, since `wrangler.jsonc` can
  only declare bindings. The imperative steps are in `docs/infra.md`.
- `apps/api/wrangler.jsonc` exists but cannot deploy until Phase 4 adds `main`.
