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

**Phases 0–4 done, Phase 5 in progress.** The card contract is defined once as pydantic
models (Phase 0), the data pipeline runs from it (Phase 1), images and artifacts are live
in R2 (Phase 2), D1 holds all 2,448 cards (Phase 3), and the Worker serves them over nine
endpoints (Phase 4 + 5).

**Phase 5** is the website: porting the frontend to `apps/web` on Nuxt 4, applying the
four refactors from [`docs/architecture-review-v1.md`](docs/architecture-review-v1.md),
and deploying the site and API together for the first time. See
[ADR 0006](docs/adr/0006-website.md).

Nothing is deployed yet — that is deliberate, and it is the last step of Phase 5.

## Structure

```
packages/schema/   ✅ the card contract — pydantic → JSON Schema → TS types → D1 DDL
pipeline/          ✅ Python pipeline (uv), `holo-data` CLI
content/           ✅ editorial site copy (info.json), published to R2
fixtures/          ✅ 34 cards covering every edge case, for credential-free local dev
apps/api/          ✅ the Worker — Hono + Zod over D1 and R2
apps/web/          🚧 Nuxt SPA                        (Phase 5, in progress)
```

## Getting started

Requires [uv](https://docs.astral.sh/uv/) and Node 22.6+.

```bash
make setup     # install Python + Node dependencies
make hooks     # enable the pre-commit check (once per clone, recommended)
make dev       # run the site (:3000) and the API (:8787) against local fixtures
make check     # run every verification
make help      # list all targets
```

`make dev` needs **no Cloudflare credentials** — the Worker runs against a local D1 seeded
from 34 committed fixture cards (D12). That property is deliberate: it is what separates a
public repo from a contributor-ready one.

There is **no CI** — verification is local by design. `make check` is the single entry
point, and the pre-commit hook runs it when you touch the contract.

## The contract

The card shape is defined **once**, in `packages/schema/src/holo_schema/`. Everything
else — the JSON Schema, the TypeScript types, the enum lists the filter UI iterates, and
(from Phase 3) the D1 schema — is generated from those pydantic models.

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
