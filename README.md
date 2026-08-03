# hololive-ocg-wiki

A fan-made wiki for the Hololive Official Card Game — card database, search, and deck
builder, in seven languages.

**→ [hololive-ocg-wiki.tskrlabs.com](https://hololive-ocg-wiki.tskrlabs.com)**

2,463 cards with full rulings, filterable by colour, rarity, card type, bloom level, tag
and set code, plus a deck builder that round-trips a deck through a shareable URL.

## Where to go

| You want to | Go to |
|---|---|
| **Use the wiki** | [the site](https://hololive-ocg-wiki.tskrlabs.com) |
| **Report a bad translation, or a bug** | [open an issue](https://github.com/tskrlabs/hololive-ocg-wiki/issues/new/choose) |
| **Contribute code or site copy** | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| **Understand the design** | [`docs/v2-plan.md`](docs/v2-plan.md), then [`docs/adr/`](docs/adr/) |
| **See what is being worked on** | [`docs/progress.md`](docs/progress.md) — the maintainer's working log |

## Running it locally

Node 24 (pinned in `.node-version`) is all you need:

```bash
npm install
make dev       # site on :3000, API on :8787, against local fixtures
make help      # list all targets
```

`make dev` needs **no Cloudflare credentials and no Python**. The Worker runs against a
local D1 seeded from 34 committed fixture cards and a local R2 seeded from committed
artifacts, and those fixtures deliberately cover every card type, every rarity, all 9
colours including both fused codes, all 7 locales and 546 Q&A items — so the edge cases are
reachable without an account.

That property is verified from a scratch clone, and it is what separates a public repo from
a contributor-ready one. [`CONTRIBUTING.md`](CONTRIBUTING.md) has the rest.

## Structure

```
packages/schema/   the card contract — pydantic → JSON Schema → TS types → D1 DDL
pipeline/          Python pipeline (uv), `holo-data` CLI — scrape, translate, publish, seed
content/           editorial site copy (info.json), published to R2
fixtures/          34 cards covering every edge case, for credential-free local dev
apps/api/          the Worker — Hono + Zod over D1 and R2
apps/web/          Nuxt 4 SPA, generated static and served as Worker assets
```

One Cloudflare Worker serves both the API and the static site from a single origin, on free
tiers throughout.

## The contract

The card shape is defined **once**, in `packages/schema/src/holo_schema/`. Everything
else — the JSON Schema, the TypeScript types, the enum lists the filter UI iterates, the
D1 schema, and the local-development fixtures — is generated from those pydantic models.

```ts
import type { Card, LocalizedCard } from "@holo/schema";
import { RARITIES, DEFAULT_LOCALE } from "@holo/schema/enums";
```

```python
from holo_schema import Card, CardCollection, localize
```

If you edit a model, run `make generate && make golden`. This is the one trap in the repo,
and [`CONTRIBUTING.md`](CONTRIBUTING.md) explains what it protects.

## About the rebuild

This is v2, rebuilt from the ground up. The v1 repo is
[`lichingchester/hololive-ocg-wiki`](https://github.com/lichingchester/hololive-ocg-wiki).

The rebuild exists because of one bug class. In v1 the card shape was hand-written in four
places — a TypeScript union, a SQL schema, a JSON fixture and the scraper — and they
drifted, until 24 cards were silently unfilterable in the live UI because one union was
missing a rarity. Nothing was broken enough to notice, which is why it lasted. Generating
all four from a single pydantic definition makes that particular bug impossible rather than
unlikely; see [ADR 0001](docs/adr/0001-card-contract-generation.md).

The design and the reasoning behind every decision are in
[`docs/v2-plan.md`](docs/v2-plan.md); decisions taken while building are in
[`docs/adr/`](docs/adr/). Neither is required reading to contribute.

## Disclaimer

This wiki is a fan-made, non-official project. All content is created by the community and
follows [Cover Corp.'s Derivative Works Guidelines](https://hololivepro.com/en/terms/).
Hololive names, images, and related content are the property of Cover Corp. This site is
not affiliated with or endorsed by Cover Corp. or hololive production.

Code is [Apache-2.0](LICENSE); the licence covers this repository's code, not the card data
or images.
