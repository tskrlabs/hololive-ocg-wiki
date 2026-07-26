# Infrastructure runbook

The Cloudflare resources this project runs on, and the commands that produced them.

`apps/api/wrangler.jsonc` declares *bindings* — which bucket a name refers to. It does
not create anything. Bucket creation, custom domains, and API tokens are imperative
one-time actions that live only in the Cloudflare dashboard, which is exactly how v1 lost
track of its own infrastructure: `wrangler.toml`, `wrangler.service.toml`, `migrations/`,
and `migration.sql` were all gitignored, so the only record of what existed was one
laptop and the dashboard UI.

This file is that record. **Update it when you change a resource.**

## Current state

| Resource | Name | Public? | Phase |
|---|---|---|---|
| R2 bucket | `hololive-ocg-wiki-images` | yes — `img.hololive-ocg-wiki.tskrlabs.com` | 2 |
| R2 bucket | `hololive-ocg-wiki-artifacts` | **no** | 2 |
| D1 database | *not yet* | — | 3 |
| Worker | *not yet* | — | 4 |

Zone `tskrlabs.com` is on Cloudflare nameservers (verified during the v2 design session),
which is the prerequisite for an R2 custom domain.

## One-time setup

Either run these commands, or do the equivalent in the dashboard. `npx wrangler` needs no
install — the repo pins version 4.x through `npx`.

### 1. Create the buckets

```bash
npx wrangler r2 bucket create hololive-ocg-wiki-images
npx wrangler r2 bucket create hololive-ocg-wiki-artifacts
```

Location hint is deliberately unset: R2 places the bucket automatically, and the CDN
serves reads from the edge regardless.

### 2. Custom domain on the images bucket

Dashboard → R2 → `hololive-ocg-wiki-images` → Settings → Public access → Custom domains
→ **Connect domain** → `img.hololive-ocg-wiki.tskrlabs.com`

or:

```bash
npx wrangler r2 bucket domain add hololive-ocg-wiki-images \
  --domain img.hololive-ocg-wiki.tskrlabs.com \
  --zone-id <tskrlabs.com zone id>
```

The custom domain is not cosmetic. `r2.dev` URLs are **rate-limited**, documented as
development-only, and get **no Cloudflare cache at all** — every image view would be a
Class B operation against the bucket. A custom domain puts the normal CDN in front, so
repeat views never reach R2.

### 3. Disable the r2.dev URL on the images bucket

```bash
npx wrangler r2 bucket dev-url disable hololive-ocg-wiki-images
```

**Do not skip this.** Enabling a custom domain does *not* disable `r2.dev` — Cloudflare's
docs are explicit that the bucket stays reachable at both. Leaving it on means an
un-cached, rate-limited path into the same objects, and if anything ever hot-links that
URL we cannot remove it without breaking them.

Confirm both buckets:

```bash
npx wrangler r2 bucket dev-url status hololive-ocg-wiki-images     # disabled
npx wrangler r2 bucket dev-url status hololive-ocg-wiki-artifacts  # disabled
```

The artifacts bucket must never be public. The Phase 3 seeder reads it over the S3 API
with credentials; the Phase 4 Worker reads it over the `ARTIFACTS` binding. Neither needs
a public URL.

### 4. Mint the R2 API token

Dashboard → R2 → **Manage API Tokens** → Create API token

- **Permission:** Object Read & Write
- **Scope:** *Apply to specific buckets* → both `hololive-ocg-wiki-images` and
  `hololive-ocg-wiki-artifacts`, and nothing else
- **TTL:** whatever you're comfortable rotating

Put the Access Key ID and Secret into `pipeline/.env` (see `pipeline/.env.example`).

Bucket-scoped rather than account-wide because the CLI may be driven by an agent (D4). A
token that structurally cannot reach any other bucket — including buckets created later —
bounds a misfire to the two we already reason about. That is the same instinct as D10's
gates, applied to credentials.

## Verifying the setup

```bash
uv sync --extra publish
holo-data publish --dry-run
```

A correct setup prints the two bucket names, lists both buckets, and reports what it would
upload. Failures are specific by design: missing credentials name the variables, a missing
`wrangler.jsonc` binding names the binding, and a missing `boto3` names the extra.

## Cost posture

Everything here is free tier, and cost is a hard constraint (`v2-plan.md` §6).

| | Free allowance | Our usage |
|---|---|---|
| R2 storage | 10 GB | ~425 MB WebP (4.3%) |
| R2 Class A (writes/lists) | 1M/month | ~3,000 per full publish |
| R2 Class B (reads) | 10M/month | near zero — the CDN absorbs repeats |
| R2 egress | free, unlimited | — |

### ⚠️ Never enable Workers "Smart Caching"

With caching enabled, static asset requests become **billable** at the normal per-request
rate. With it off — the default — they are free and unlimited. This one toggle is the
difference between $0/month and a real bill.

Note this is a *Workers* setting and is unrelated to the R2 custom domain's CDN caching in
step 2, which is both free and desirable.

### Image cache headers

`publish` sets `Cache-Control: public, max-age=31536000, immutable` on every image, set
explicitly at upload rather than left to Cloudflare's default cached-extension list — a
cache policy that lives in a provider default is invisible in review and can change
without us noticing.

A year-long immutable cache is safe because image keys are immutable *by construction*:
the key is `{set}/{stem}`, so a different print gets a different key. F-006 is the proof —
`hBP03-044_SR` exists in two sets as genuinely different artwork, and the two get separate
keys and separate objects.

The trade-off: replacing an image in place (say, re-converting the whole set at a
different WebP quality) would leave clients on the old bytes until the cache expires. If
that ever becomes necessary, add a version prefix to the key rather than overwriting.
