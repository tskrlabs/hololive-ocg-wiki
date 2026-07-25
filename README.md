# hololive-ocg-wiki

A fan-made wiki for the Hololive Official Card Game — card database, search, and deck builder.

> **v2 rebuild in progress.** This repo is a ground-up rebuild of
> [`lichingchester/hololive-ocg-wiki`](https://github.com/lichingchester/hololive-ocg-wiki)
> on new infrastructure. The v1 site remains live at
> `hololive-ocg-wiki.lichingchester.dev` throughout — nothing here affects it until cutover.
>
> **Start here → [`docs/v2-plan.md`](docs/v2-plan.md)** — the full design, every decision
> and its reasoning, verified facts, and the phase plan.

## Status

**Phase 0 complete** — the card contract is defined once, as pydantic models, with the
JSON Schema and TypeScript types generated from it. Next up: **Phase 1**, the pipeline
migration.

## Structure

```
packages/schema/   ✅ the card contract — pydantic → JSON Schema → TS types
fixtures/          ✅ 34 cards covering every edge case, for credential-free local dev
apps/web/          ⬜ Nuxt SPA                        (Phase 5)
apps/api/          ⬜ Cloudflare Worker: Hono + assets (Phase 4)
pipeline/          ⬜ Python pipeline (uv), `holo-data` CLI (Phase 1)
```

## Getting started

Requires [uv](https://docs.astral.sh/uv/) and Node 22.6+.

```bash
make setup     # install Python + Node dependencies
make hooks     # enable the pre-commit check (once per clone, recommended)
make check     # run every verification
make help      # list all targets
```

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
