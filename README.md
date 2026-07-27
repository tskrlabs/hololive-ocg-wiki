# hololive-ocg-wiki

A fan-made wiki for the Hololive Official Card Game — card database, search, and deck builder.

> **v2 rebuild in progress.** This repo is a ground-up rebuild of
> [`lichingchester/hololive-ocg-wiki`](https://github.com/lichingchester/hololive-ocg-wiki)
> on new infrastructure. The v1 site remains live at
> `hololive-ocg-wiki.lichingchester.dev` throughout — nothing here affects it until cutover.
>
> **Start here → [`docs/progress.md`](docs/progress.md)** — where the rebuild is now and
> what to pick up next. Then [`docs/v2-plan.md`](docs/v2-plan.md) for the full design,
> every decision and its reasoning.

## Status

**Phases 0–5 done, Phase 6 in progress.** The card contract is defined once as pydantic
models (Phase 0), the data pipeline runs from it (Phase 1), images and artifacts are live
in R2 (Phase 2), D1 holds all 2,448 cards (Phase 3), and one Worker serves the API and the
site from a single origin (Phases 4–5).

**The site is live** at `hololive-ocg-wiki.tskrlabs.com` — but deliberately **`noindex`**
until launch. v1 remains the public site, indexed on the same 2,448 cards, and an indexed
v2 would pre-empt a domain decision that is still open (`v2-plan.md` §7). The domain going
live is not the launch.

**Phase 6** is push-to-deploy and the contributor path: Workers Builds, a fresh clone that
runs with no credentials, and the docs for a repo that goes public at Phase 7. See
[ADR 0007](docs/adr/0007-push-to-deploy.md).

## Structure

```
packages/schema/   ✅ the card contract — pydantic → JSON Schema → TS types → D1 DDL
pipeline/          ✅ Python pipeline (uv), `holo-data` CLI
content/           ✅ editorial site copy (info.json), published to R2
fixtures/          ✅ 34 cards covering every edge case, for credential-free local dev
apps/api/          ✅ the Worker — Hono + Zod over D1 and R2
apps/web/          ✅ Nuxt 4 SPA, generated static and served as Worker assets
```

## Getting started

Node 24 (pinned in `.node-version`) is all you need for the site and the API:

```bash
npm install
make dev       # site on :3000, API on :8787, against local fixtures
make help      # list all targets
```

`make dev` needs **no Cloudflare credentials and no Python** — the Worker runs against a
local D1 seeded from 34 committed fixture cards and a local R2 seeded from committed
artifacts (D12). That property is deliberate, it is verified from a scratch clone each
phase, and it is what separates a public repo from a contributor-ready one.

Working on the **card contract** additionally needs [uv](https://docs.astral.sh/uv/):

```bash
make setup     # uv sync + npm install
make hooks     # enable the pre-commit check (once per clone, recommended)
make check     # run every verification
```

There is **no CI** — verification is local by design. `make check` is the single entry
point, and the pre-commit hook runs it when you touch the contract.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for what can be done without credentials, what
needs the maintainer, and how to report a bad translation.

## The contract

The card shape is defined **once**, in `packages/schema/src/holo_schema/`. Everything
else — the JSON Schema, the TypeScript types, the enum lists the filter UI iterates, the
D1 schema, and the local-development fixtures — is generated from those pydantic models.

This is the central fix of the v2 rebuild: in v1 the same shape was hand-written in four
places and had measurably drifted, to the point that 24 cards were unfilterable in the
live UI because one TypeScript union was missing a rarity. See
[ADR 0001](docs/adr/0001-card-contract-generation.md).

```ts
import type { Card, LocalizedCard } from "@holo/schema";
import { RARITIES, DEFAULT_LOCALE } from "@holo/schema/enums";
```

```python
from holo_schema import Card, CardCollection, localize
```

## Disclaimer

This wiki is a fan-made, non-official project. All content is created by the community and
follows [Cover Corp.'s Derivative Works Guidelines](https://hololivepro.com/en/terms/).
Hololive names, images, and related content are the property of Cover Corp. This site is
not affiliated with or endorsed by Cover Corp. or hololive production.
