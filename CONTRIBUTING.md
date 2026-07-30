# Contributing

Thanks for looking. This is a fan-made wiki for the Hololive Official Card Game, and
most of it is contributable without any credentials at all.

Start with [`docs/progress.md`](docs/progress.md) — it says where the rebuild is and what
is being worked on. [`docs/v2-plan.md`](docs/v2-plan.md) has the design and the reasoning
behind every decision; `docs/adr/` records decisions made while building.

## What you can do with no credentials

Everything in the site, the API, and the docs.

```bash
git clone https://github.com/tskrlabs/hololive-ocg-wiki
cd hololive-ocg-wiki
npm install
make dev          # site on :3000, API on :8787
```

That is the whole setup. The Worker runs against a **local** D1 seeded from 34 committed
fixture cards, and a local R2 seeded from committed artifacts — no Cloudflare account, no
tokens, no Python. The fixtures deliberately cover every card type, every rarity, all 9
colours including both fused codes, all 7 locales and 546 Q&A items, so the edge cases
are reachable locally.

```bash
make check-web    # the site's unit tests
make check-api    # the Worker: unit tests + every endpoint over real HTTP
make preview      # rehearse production — the Worker serves site and API on one port
make help         # everything else
```

**What you actually need installed:** Node 24 (pinned in `.node-version`), and a network
connection the first time — `npx wrangler` downloads the Workers runtime on first run.
`make check-api` also shells out to `python3` for its assertions, but only the standard
library, so the interpreter that ships with macOS and most Linux distributions is enough.

There is **no CI**, by decision — verification is local. `make check` is the single entry
point. Run `make hooks` once to have it fire before each commit.

## What needs the maintainer

Some steps need paid or account-scoped credentials, so they cannot be run from a fork.
This is a statement about credentials, not about who may contribute:

| Step | Why |
|---|---|
| `holo-data translate` | a paid Poe API key |
| `holo-data publish` | an R2 token scoped to this project's buckets |
| `holo-data seed` | a D1 token for the production database |
| deploying | Cloudflare Workers access |

If a change needs one of these — new card data, a re-translation, a schema migration —
open an issue and it will be run for you. Everything *before* those steps is local and
reversible, and the pipeline's design assumes it may be driven by an agent, so each
destructive or paid step is gated behind an explicit flag (see `docs/v2-plan.md` D10).

## Fixing a bad translation

Card text is machine-translated from Japanese into six languages, and some of it is
wrong. Corrections are welcome and durable — the pipeline stores a corrected field as a
cache entry marked `source: "manual"`, which survives the card being re-translated for
any other reason.

**Right now this has to go through an issue, not a pull request.** Open one with:

- the card id or card number (e.g. `hBP01-028`)
- the locale (`en`, `tc`, `id`, `ko`, `th`, `es`)
- the field, and what it should say

The honest reason it is not a PR: the translation cache lives in `pipeline/locales/`,
which is **not in git**, so there is no file for you to edit. D14 originally promised a
committed `corrections/` overlay, and ADR 0002 replaced that mechanism with cache entries
without replacing the reviewable surface it provided. That gap is logged as
[F-018](docs/archive/findings.md#f-018) and is not yet closed.

Bad *data* — as opposed to bad translation — is worth an issue too. Known anomalies are
in [`docs/archive/findings.md`](docs/archive/findings.md); check there first, since several surprising
things are already known and deliberately not "fixed".

## If you touch the card contract

The card shape is defined **once**, as pydantic models in
`packages/schema/src/holo_schema/`. The JSON Schema, the TypeScript types, the enum lists
the filter UI iterates, the D1 DDL and the fixtures are all generated from it.

This is the one trap in the repo. If you edit a model, regenerate:

```bash
make generate && make golden
```

`make check` fails if the committed output is stale, and the pre-commit hook runs it when
you touch `packages/schema/`, `pipeline/` or `fixtures/`. This matters because in v1 the
same shape was hand-written in four places and drifted — at one point 24 cards were
unfilterable in the live UI because a TypeScript union was missing a rarity. See
[ADR 0001](docs/adr/0001-card-contract-generation.md).

Working on the contract needs Python, which `make setup` installs via
[uv](https://docs.astral.sh/uv/). Frontend-only work does not.

## Conventions

- Work branches off **`develop`**; `main` is what is deployed. A merge to `main`
  deploys the site, so open pull requests against `develop`.
- Commit messages explain **why**, not what — the diff already says what.
- Data anomalies go in [`docs/archive/findings.md`](docs/archive/findings.md) rather than being silently
  worked around. Something unambiguously broken with an obvious fix gets fixed *and*
  logged.
- Decisions that shape the code get an ADR in `docs/adr/`.

## Licence and content

Code is Apache-2.0 (see [`LICENSE`](LICENSE)). Card data, card images, and the names and
likenesses they contain are the property of Cover Corp., used under the
[Derivative Works Guidelines](https://hololivepro.com/en/terms/) — the licence covers this
repository's code, not that content. This project is not affiliated with or endorsed by
Cover Corp. or hololive production.
