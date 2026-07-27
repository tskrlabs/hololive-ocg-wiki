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
| D1 database | `hololive-ocg-wiki` — **not created yet**, see §5 | **no** | 3 |
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

`R2_ACCOUNT_ID` is 32 hex characters. The dashboard shows it as part of the S3 endpoint
(`https://<account_id>.r2.cloudflarestorage.com`) — pasting that whole URL works too, it
is reduced to the ID.

Bucket-scoped rather than account-wide because the CLI may be driven by an agent (D4). A
token that structurally cannot reach any other bucket — including buckets created later —
bounds a misfire to the two we already reason about. That is the same instinct as D10's
gates, applied to credentials.

### 5. Create the D1 database (Phase 3)

```bash
npx wrangler d1 create hololive-ocg-wiki
```

It prints a `database_id`. Paste it into `apps/api/wrangler.jsonc`, replacing the
`"REPLACE_ME"` placeholder — `holo-data seed` reads the name and id from there, because
the infra config is the one place a resource is named. The placeholder is checked for
explicitly, so forgetting this step gives you the `wrangler d1 create` command rather
than a 404 with an opaque id in it.

Then apply the schema. This is the only DDL step, and it is deliberately manual:

```bash
npx wrangler d1 execute hololive-ocg-wiki --remote \
    --file=packages/schema/sql/schema.sql
```

`schema.sql` is **generated** from the pydantic models (`make generate`), so it is never
hand-edited and `make check` fails if the committed copy is stale. Every statement is
`IF NOT EXISTS`, so re-running is safe.

**`holo-data seed` never runs DDL.** The CLI may be driven by an agent (D4); a command
that can `DROP TABLE` is a blast radius D10 exists to bound. Schema changes are rare and
human-driven.

### 6. Mint the D1 API token

Dashboard → My Profile → API Tokens → Create Token → Custom token

- **Permissions:**
  - *Account* → **D1** → **Edit**
  - *Account* → **Account Analytics** → **Read**
- **Account resources:** this account only

Put them in `pipeline/.env`:

```
CLOUDFLARE_ACCOUNT_ID=…
CLOUDFLARE_API_TOKEN=…
```

**A separate token from the R2 one**, for the same reason the R2 token is scoped to two
buckets: an agent-driven misfire should be structurally unable to reach anything it was
not pointed at. The R2 credentials cannot touch D1 and these cannot touch R2.

Account Analytics Read is what lets `seed` check **today's actual write usage** before
running, rather than assuming the full 100k/day budget is available. Without it `seed`
still works — it warns that it could not read usage and only refuses if the estimate
exceeds the whole daily limit. The failure that permission prevents is specific: a
second seed in one day running out of budget *mid-run* and leaving the database
partially updated.

### Seeding

```bash
uv run holo-data seed --dry        # reads only; prints the diff and the write estimate
uv run holo-data seed --confirm    # writes
```

A first full seed is **~29,650 writes (30% of the daily budget)**; a new card set is
~1,450 (1.5%). `seed` refuses on a stale `cards.json`, on a card set that collapsed
since the last run, on a schema-version mismatch, and when the estimate would not fit in
what remains of today's budget — none of which a flag can override. Deleting cards needs
`--prune`.

## Local development — no credentials at all

D12's requirement is that a fresh clone runs with zero Cloudflare credentials:

```bash
npx wrangler d1 execute hololive-ocg-wiki --local --file=packages/schema/sql/schema.sql
npx wrangler d1 execute hololive-ocg-wiki --local --file=fixtures/fixtures.sql
```

`fixtures/fixtures.sql` is committed and generated from the 34 fixture cards — every card
type, every rarity, all 9 colours including both fused codes, all 7 locales, 546 Q&A
items. No token, no network, no Python toolchain.

## Verifying the setup

```bash
uv sync --extra publish
uv run holo-data publish --dry-run
```

**`uv run`, not bare `holo-data`.** The CLI installs into the project venv, not onto your
PATH — a bare `holo-data` gives `command not found`. Either prefix with `uv run` or
`source .venv/bin/activate` once per shell.

A correct setup prints the two bucket names, lists both buckets, and reports what it would
upload. Failures are specific by design: missing credentials name the variables, a
malformed account ID shows the expected shape, a missing `wrangler.jsonc` binding names
the binding, and a missing `boto3` names the extra.

To check the credentials alone, before there is anything to publish:

```bash
uv run python -c "
from holo_data import cli, r2
cfg = r2.load_config(); s3 = r2.client(cfg)
for b in (cfg.images_bucket, cfg.artifacts_bucket):
    print(b, len(r2.list_objects(s3, b)), 'objects')
"
```

## Cost posture

Everything here is free tier, and cost is a hard constraint (`v2-plan.md` §6).

| | Free allowance | Our usage |
|---|---|---|
| R2 storage | 10 GB | 191 MB WebP (1.9%) |
| R2 Class A (writes/lists) | 1M/month | ~3,000 per full publish |
| R2 Class B (reads) | 10M/month | near zero — the CDN absorbs repeats |
| R2 egress | free, unlimited | — |
| **D1 storage** | **500 MB** (not 5 GB — that is the paid tier) | ~17 MB data + ~36 MB FTS index |
| D1 rows written | 100,000/day | ~29,650 per full reseed, ~1,450 per new set |
| D1 rows read | 5,000,000/day | see below |

### ⚠️ D1 rows read is the number to watch

Writes are what `seed` spends and they have enormous headroom. **Reads are what the
*site* spends, and v1 breached them** — 5,582,892 rows read on 2026-07-12 against a 5M
limit, at which point D1 returns errors until 00:00 UTC ([F-014](./findings.md#f-014)).

v1 scanned 882 rows per query on a 2,448-row table because JSON-array filters cannot use
an index and `enrichCardDataBatch` issued five follow-up queries per page. The v2 schema
measures at ~50–100 rows for the same page. Rows-read scales with traffic while writes do
not, so this is the metric to check after launch:

```bash
npx wrangler d1 info hololive-ocg-wiki       # size and state
npx wrangler d1 insights hololive-ocg-wiki   # per-query stats (experimental)
```

For the daily totals against the quota, the dashboard's D1 → Metrics → Row Metrics view
is authoritative. `holo-data seed` reads the same numbers over the GraphQL analytics API
(`d1AnalyticsAdaptiveGroups`) to decide whether a run fits in the remaining budget.

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
