# Hololive OCG Wiki — v2 plan & handover

**Status:** design agreed, implementation not started
**Agreed:** 2026-07-25 (via `/grilling` session in the v1 repo)
**Next step:** Phase 0 — workspaces skeleton + `packages/schema`

This document is the complete handover from the v1 repo. It carries every decision,
the reasoning behind it, and the verified facts the decisions rest on. A new session
should be able to start from this file alone.

---

## 1. What this is

`hololive-ocg-wiki` is a fan-made wiki for the Hololive Official Card Game — card
database, search/filter, and a deck builder. It has been running for about a year.

**v2 is a rebuild on new infrastructure, not an in-place upgrade.** The v1 site stays
live and untouched throughout. Everything is built in parallel here, on a new domain,
against new Cloudflare resources. Nothing is at risk until we deliberately cut over.

### The three problems v2 solves

1. **The data pipeline lives in a different repo** (and inside an unrelated multi-project
   repo at that), so publishing card updates means hand-copying a 22 MB JSON between
   directories.
2. **Deployment is manual across three separate Cloudflare resources** (Pages, Worker,
   D1) with no git integration — the Pages project isn't even connected to the repo.
3. **The repo is 4.6 GB** (1.2 GB of git history), because 1 GB of card images and
   66 MB of JSON snapshots are committed. That makes it effectively un-contributable-to.

---

## 2. Source material

| What | Where | Notes |
|---|---|---|
| v1 repo | `/Users/chingli/lichingchester/projects/hololive-ocg-wiki` | branch `v2`; public, Apache-2.0, 212 commits |
| Data pipeline | `/Users/chingli/lichingchester/tool/python-scripts/hololive-ocg-data-v2` | lives inside `github.com/lichingchester/python-scripts` |
| Architecture review | v1 repo → `docs/architecture-review-v2.md` (+ `.html`) | 4 refactor candidates; **copy this over in Phase 5** |
| v1 live site | `hololive-ocg-wiki.lichingchester.dev` | stays live until cutover |
| New repo | `github.com/tskrlabs/hololive-ocg-wiki` (this one) | **private** until launch |
| New domain | `hololive-ocg-wiki.tskrlabs.com` | ✅ verified on CF nameservers |

> **Note on naming:** this repo is under the `tskrlabs` **org**, so it already has the
> final name. The earlier plan to use a `-v2` suffix and rename later is unnecessary.
> At launch: archive `lichingchester/hololive-ocg-wiki` → rename to
> `hololive-ocg-wiki-archive`; make this repo public.

---

## 3. Verified facts

Measured during the design session — trust these over re-deriving, but re-verify
anything that looks stale before relying on it.

### v1 scale

- **2,448 cards**, 7 locales: `ja` `en` `tc` `id` `ko` `th` `es` (`tc` is default)
- **~48,700 D1 rows** under the current normalized schema — `card_translations` alone is
  17,136 (2,448 × 7). This is the number that drives the schema redesign.
- **6,039 image files** = ~3,019 PNG + WebP pairs, **1.0 GB**
- `data/*.json` = **66 MB** committed (4 snapshots; only `cards_i18n.json` is imported,
  and only by dead code)
- `cloudflare/worker.ts` = **1,269 lines**, one file, 8 endpoints
- Pipeline = **~3,000 LOC** Python across 9 numbered scripts

### v1 topology (what we're replacing)

```
Pages (Nuxt SPA, ssr:false)
  └─ functions/api/[[path]].ts     ← proxy that exists only to bridge Pages→Worker
       └─ service binding
            └─ Worker "hololive-ocg-api"
                 └─ D1 "hololive-ocg-db"  (id addd37d0-f107-4a77-9781-36119dfc91e1)
```

`wrangler.toml`, `wrangler.service.toml`, `migrations/`, and `migration.sql` are all
**gitignored** in v1 — the infra config isn't in version control at all.

### API endpoints (v1 — preserve behaviour, reshape internals)

```
GET /api/cards/search
GET /api/cards/filter
GET /api/cards/:id
GET /api/cards-list/:ids
GET /api/cards/by-card-numbers/:numbers
GET /api/cards/filter-by-card-number/:number
GET /api/filter-options
GET /api/static-filters
```

### Cloudflare free tiers (checked 2026-07-25)

| Service | Free allowance | Our usage | Headroom |
|---|---|---|---|
| Workers requests | 100k/day | API calls only | ✅ static assets **free & unlimited** |
| Workers Builds | 3,000 min/mo, 1 concurrent, 20 min timeout | ~2–3 min/build | ✅ ample |
| R2 | 10 GB, 1M Class A, 10M Class B /mo, **egress free** | ~500 MB (WebP only) | ✅ comfortable |
| D1 | 5M reads/day, **100k writes/day**, 5 GB | ~2,500 writes/reseed | ✅ after redesign |
| Cron Triggers | 5 | 0 | n/a — external detector |

**Everything in this plan fits free tiers.** Cost is a hard constraint (see §6).

---

## 4. Decisions

Each was put to the maintainer individually and confirmed.

### D1 — Data lives outside git
Repo holds source only. Card images → **R2**; generated `cards.json`, `status.json`,
`info.json` → **R2 artifacts**.
*Why:* a 1.2 GB clone makes contribution impossible, and every pipeline run grows
history permanently. **A data update now touches zero git commits.**

### D2 — One Worker, not Pages + Worker
Merge the Pages project into a single Worker with static assets. One `wrangler.jsonc`
declares assets + D1 + R2 + routes; one `wrangler deploy` ships everything.
*Why:* this is the "group all resources and control them" ask. Deletes the
`functions/api/[[path]].ts` proxy and the service binding — both exist only because
Pages and the Worker are separate. Also unlocks Workers-only features (Workers Logs,
Cron Triggers, gradual deployments).
*Caveats:* SPA fallback routing must be configured manually (Pages auto-detected it);
custom domain must be on CF nameservers (✅ verified for `tskrlabs.com`).

### D3 — Pipeline stays Python, repackaged
Keep the scrapers' behaviour. Repackage as a `pipeline/` module with a single
`holo-data` CLI (subcommands replace the `1-` … `8-` filename ordering), `uv` for
deps/lockfile, pydantic models as the output contract.
*Why:* those scrapers encode a year of knowledge about the official site's HTML quirks.
A port's *best* case is "works exactly as before" — bad risk/reward. `uv` removes the
historic pain of a polyglot repo. Contributors touching only the website never run Python.

### D4 — Local CLI, no pipeline automation
The full pipeline runs on the maintainer's machine, on demand.
*Why:* **a Discord detector already exists externally** and notifies on new card sets —
so there is nothing to build. Automating translation would also push unreviewed LLM
output to production.
*Constraint:* the CLI may be driven **by an agent** on request, so every destructive or
paid step needs an explicit gate (see D10).

### D5 — Workspaces monorepo
```
apps/web/          Nuxt SPA
apps/api/          Worker: Hono API + static assets + wrangler.jsonc
packages/schema/   the card contract — pydantic → JSON Schema → TS types (SQL in Phase 3)
pipeline/          Python (uv), holo-data CLI, corrections/ overlay
fixtures/          ~40 cards for credential-free local dev
docs/              CONTEXT.md, adr/, this file
```
*Why:* v1's root is Nuxt's directories plus a `cloudflare/` folder — adding `pipeline/`
makes it a grab-bag. `packages/schema/` is the important part: **the card shape is
currently defined in four places** (Python, `schema.sql`, `worker.ts`, `types/card.ts`)
and drifts. Workers Builds supports monorepos natively.

### D6 — Fresh git history
Start at commit 1. v1 becomes `hololive-ocg-wiki-archive`, stays public with full history.
*Why:* nothing is lost — it's one link away — and `filter-repo` on 1.2 GB would produce a
partly-fictional history (commits referencing files that no longer exist) while changing
every hash anyway. The workspace restructure would break `--follow` regardless.

### D7 — API: Hono + Zod + schema redesign
Full rework. Hono replaces the `if (path === …)` router chain and hand-rolled CORS; Zod
replaces the manual validators, sourced from `packages/schema`; split into
`routes/` / `db/` / `lib/`.
*Why:* new resources mean **no rollback case to protect** — do it properly now. v1's
`checkRateLimit()` is a stub that unconditionally `return true`.

### D8 — D1: per-locale translations as JSON columns
One row per card; `translations` / arts / QA stored as JSON keyed by locale. Filterable
fields (type, colors, rarity, bloom) stay real indexed columns. FTS5 retained for search.
*Why:* **~48,700 rows → ~2,500 (95% cut)**. A full reseed drops from 50% of the daily
D1 write budget to 2.5%. Also kills the 6-way join in `enrichCardDataBatch`, and adding
an 8th locale becomes zero extra rows. We never query a single locale's field in
isolation — and search comes from FTS5, which is a separate index either way.

### D9 — Images: store the key, build the URL; WebP only
D1 stores `image_key` (e.g. `default/hBP01-028_C_02`). One `cardImage()` helper composes
`https://img.hololive-ocg-wiki.tskrlabs.com/{key}.webp` from configured config.
Upload **WebP only**; PNG stays a local pipeline intermediate.
*Why:* v1 bakes folder layout *and* extension into the database (`image_path` =
`card_images/default/hBP01-028_C_02.png`), so changing CDN host or format means a full
reseed. Halves R2 storage and upload ops. Also fixes `getImagePath()` being copy-pasted
verbatim across three components.

### D10 — Gated update flow
```
holo-data scrape       → raw + structured          (local, free)
holo-data translate    → Poe API                   ($$ — never implicit)
holo-data build        → cards.json + status diff  (local, free, reversible)
holo-data publish      → images → R2, artifacts → R2
holo-data seed --dry   → prints row counts + D1 write estimate   ← always first
holo-data seed --confirm → diff-based upsert into D1
```
`seed` refuses to run without a preceding dry-run. `--full` (the ~48k-write path) is
gated separately. Port v1 `migrate.js`'s `D1_WRITE_LIMIT` accounting into the Python CLI.
*Why:* everything before `seed` is local and reversible; an agent-driven run that
misfires must not be able to burn the daily write budget or corrupt live data.

### D11 — `status.json` and `info.json` → R2
`status.json` is written by `holo-data publish`. `info.json` is pushed via CLI or the CF
dashboard.
*Why:* v1 fetches `info.json` from **raw.githubusercontent.com on `main`** — a live
production dependency on a git URL that breaks the moment repos are renamed. R2 keeps
the edit-without-redeploy property that motivated the hack, and drops GitHub from the
production path.

### D12 — Single production env + local D1 fixtures
One Worker, one D1, one R2 bucket. **No preview environment for now** — the
un-announced new domain *is* staging until launch. Plus a local-only D1
(`wrangler d1 --local`) seeded from a checked-in fixture subset.
*Why:* a second D1 doubles seed writes and needs its own 48k-row seed, all to duplicate
what the un-announced domain gives free. The fixtures matter independently: **a fresh
clone must run with zero Cloudflare credentials.** That single property is what separates
"public repo" from "contributor-ready repo."
*Revisit:* add a preview env post-launch, once live data needs protecting.

### D13 — Website: refactors only, stays SPA
The four architecture-review candidates + dead-code purge. Point at the new API/R2.
**No new features, no redesign, no rendering-mode change.**
*Why:* Candidate 01 alone deletes ~6 unreferenced files and stops an **8 MB JSON import
at every page load** — a real user-facing win with no design work. The dual-store fork
exists *because* a migration was left half-done; piling features on unmigrated code
recreates the problem. SSR/prerender was considered and deliberately deferred.

### D14 — Open source = readable + locally runnable + corrections overlay
Fixture-based local dev, a `CONTRIBUTING.md` explicit about maintainer-only steps, and a
`corrections/` overlay applied *after* translation.
*Why:* the pipeline needs a paid Poe key and the maintainer's CF account — outsiders can
never run `translate` or `seed`, and pretending otherwise wastes everyone's time. But the
contribution people actually want to make is **fixing a bad translation**, which is
currently impossible: fixes get overwritten on the next pipeline run. An overlay makes it
a reviewable PR. (v1's `7-manual-translate.py` / `8-replace-manual-to-card.py` grope
toward this; the overlay supersedes them.)

### D15 — Build order: contract first
See §5. `packages/schema` is upstream of everything — pipeline writes to it, seeder reads
it, worker validates against it, frontend types derive from it. Building anything else
first means building against a moving contract.
*Accepted cost:* Phases 0–1 produce nothing visible in a browser.

---

## 5. Phases

| # | Phase | Done when |
|---|---|---|
| 0 | Repo skeleton + `packages/schema` | ✅ **Done** — card contract defined once; TS types + JSON Schema generate from pydantic models. See [ADR 0001](adr/0001-card-contract-generation.md) |
| 1 | Pipeline migration (`pipeline/`, uv, `holo-data`, corrections overlay) | `holo-data build` reproduces today's card **data** — same 2,448 cards, same values, validated against `packages/schema` (see ADR 0001: the canonical artifact is snake_case now, so this is data-equivalence, not a byte-diff of v1's `cards.json`) |
| 2 | CF resources + R2 publish | Images live at `img.hololive-ocg-wiki.tskrlabs.com`; `publish` is idempotent |
| 3 | D1 redesign + seeder | `seed --dry` reports ~2,500 rows; production D1 populated; FTS5 working |
| 4 | Worker rewrite (Hono + Zod, assets binding) | All 8 endpoints serve correctly; SPA + API from one Worker |
| 5 | Website (new API/R2, 4 refactors, dead-code purge) | ✅ **Done** — live at `hololive-ocg-wiki.tskrlabs.com`, `noindex` until launch. See [ADR 0006](adr/0006-website.md) |
| 6 | Workers Builds + fixtures + docs | Push-to-deploy works; **fresh clone runs with zero CF creds** — and, amended, with no Python toolchain either. See [ADR 0007](adr/0007-push-to-deploy.md) |
| 7 | Launch | v1 archived; this repo public; domain decision executed; the three switches in `progress.md` flipped |

---

## 6. Gotchas

### ⚠️ Never enable Workers "Smart Caching"
Cloudflare's pricing docs are explicit: **with caching enabled, static asset requests
become billable** at the normal per-request rate. With it off (the default), they are
free and unlimited. This one toggle is the difference between $0/month and a real bill.

### ⚠️ D1 writes are the binding constraint
100k/day, free tier. The redesigned schema makes a full reseed ~2,500 writes — but a
naive "drop and reload" loop during development can still burn the quota. Always
`seed --dry` first. Keep the diff-based upsert; never make full-reseed the default path.

### ⚠️ Cost is a hard requirement
Free tier only. If a design needs a paid service, it needs a decision first, not an
assumption.

### ⚠️ Never use GitHub Actions
No `.github/workflows/`, in this repo or any other. The maintainer has had a GitHub
account banned over Actions usage — the risk is account-level, not project-level.
Verification is local: `make check`, plus an opt-in pre-commit hook (`make hooks`).

**Workers Builds (Phase 6) is unaffected** — it runs on Cloudflare's infrastructure and
GitHub only sends a webhook. Push-to-deploy is still on the table.

### Other
- v1's `.venv`, `node_modules`, and `dist` symlink should not be carried over.
- v1's `wrangler*.toml` are gitignored — the new `wrangler.jsonc` **must be committed**.
- Poe API is OpenAI-compatible (v1 uses the `openai` SDK against it).
- Nuxt 3, `ssr: false`, i18n `strategy: "prefix"`, default locale `tc`.

---

## 7. Still open

**Domain/SEO strategy at cutover (Phase 7).** `hololive-ocg-wiki.lichingchester.dev` has
a year of accumulated SEO. Options: 301-redirect the old domain to the new one, run both
in parallel, or hard cut. Deliberately deferred — it blocks nothing before Phase 7 and is
better decided with the new site in front of us.

---

## 8. Working agreement

- Commit directly; **do not push** until the maintainer says so.
- Decisions in §4 are settled — don't re-litigate them without new information. If
  implementation reveals one was wrong, say so explicitly and propose the change rather
  than quietly working around it.
- Prefer reading the v1 source over guessing at behaviour; the paths are in §2.
