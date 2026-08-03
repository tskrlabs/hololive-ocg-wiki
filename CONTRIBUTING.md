# Contributing

Thanks for looking. This is a fan-made wiki for the Hololive Official Card Game, and most
of it is contributable without any credentials at all.

The two most useful things you can do are **fix a bug** and **fix wording in your own
language**. Neither needs a Cloudflare account, a paid API key, or Python.

## How changes get in

Fork → branch → pull request against **`develop`**. That is the only path, including for
the maintainer.

```bash
# on your fork
git clone https://github.com/<you>/hololive-ocg-wiki
cd hololive-ocg-wiki
npm install
git switch -c fix-the-thing
make dev          # site on :3000, API on :8787
```

**`main` is not a branch you open PRs against.** A merge to `main` deploys the live site,
so it is protected and only ever receives merges from `develop`. A PR aimed at `main` will
be asked to re-target.

There is **no CI**, by decision — verification is local (see
[below](#what-to-run-before-you-open-a-pr)). That means review is a human reading your
change, so a PR that says *why* in a sentence or two gets merged faster than one that
does not.

## What you can change without asking first

Open a PR directly. No issue needed.

| | Where |
|---|---|
| **Bug fixes** | anywhere — see [the issue list](https://github.com/tskrlabs/hololive-ocg-wiki/issues) |
| **UI and UX** | `apps/web/app/` |
| **Site copy and its translations** | `apps/web/i18n/locales/*.json` |
| **Docs** | `README.md`, this file, `docs/` |
| **Tests** | anywhere — a failing test that demonstrates a bug is a complete contribution on its own |

## What needs an issue first

Not a rejection — these have consequences a PR cannot show, so they are worth agreeing on
before you spend time:

| | Why |
|---|---|
| **The card contract** (`packages/schema/`) | it generates the TS types, the D1 DDL and the fixtures; changing it is a migration, not an edit |
| **The pipeline** (`pipeline/`) | its outputs are paid (translation) or destructive (reseed) |
| **Card text and card data** | not in git — see [below](#fixing-card-text) |
| **Anything needing credentials** | a paid Poe key, R2 or D1 tokens, or Workers access |

If a change needs one of those, open an issue and it will be run for you. Everything
*before* those steps is local and reversible, and each destructive or paid step is gated
behind an explicit flag (`docs/v2-plan.md` D10).

## Fixing site copy

The site's own words — buttons, labels, empty states, error messages — are hand-written in
`apps/web/i18n/locales/`, one file per locale, 81 keys each:

```
en.json  es.json  id.json  ja.json  ko.json  tc.json  th.json
```

These are **in git and PR-able right now.** If a label reads awkwardly in your language,
edit the file and open a PR. Native speakers are the only people who can catch these, and
`en.json` is the reference for what a key means.

## Fixing card text

Card names, skill text and rulings are a different thing entirely: they are
machine-translated from Japanese into six languages, and some of it is wrong.

**These have to go through an issue, not a pull request.** Use the
[bad translation form](https://github.com/tskrlabs/hololive-ocg-wiki/issues/new/choose) —
it asks for the card number (e.g. `hBP01-028`), the locale, the field, and what it should
say.

The honest reason it is not a PR: the translation cache lives in `pipeline/locales/`, which
is **not in git**, so there is no file for you to edit. D14 originally promised a committed
`corrections/` overlay, and ADR 0002 replaced that mechanism with cache entries without
replacing the reviewable surface it provided. That gap is
[#18](https://github.com/tskrlabs/hololive-ocg-wiki/issues/18) and is not yet closed.

Corrections are durable despite that — a corrected field is stored as a cache entry marked
`source: "manual"`, which survives the card being re-translated for any other reason.

Bad *data* — as opposed to bad translation — is worth an issue too. Known anomalies are in
[`docs/archive/findings.md`](docs/archive/findings.md); check there first, since several
surprising things are already known and deliberately not "fixed".

## What to run before you open a PR

Run what covers what you touched. **You are not expected to install a Python toolchain to
fix a button label.**

| You changed | Run | Needs |
|---|---|---|
| `apps/web/` — UI, copy, locales | `make check-web` | Node only |
| `apps/api/` — the Worker | `make check-api` | Node only |
| `packages/schema/`, `pipeline/`, `fixtures/` | `make generate && make golden && make check` | Node + [uv](https://docs.astral.sh/uv/) (`make setup`) |

`make preview` rehearses production — the Worker serving the site and the API on one port —
and is worth running for anything that touches routing or the API.

**`make check` is the authoritative bar, and it is run before merging.** If you cannot run
all of it, that is fine: run what applies and say so in the PR.

`make hooks` (once per clone) makes the relevant checks fire before each commit.

**What you actually need installed:** Node 24 (pinned in `.node-version`), and a network
connection the first time — `npx wrangler` downloads the Workers runtime on first run.
`make check-api` also shells out to `python3`, but only the standard library, so the
interpreter shipped with macOS and most Linux distributions is enough.

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

- Branch off **`develop`**; PRs target `develop`. `main` is what is deployed.
- Commit messages explain **why**, not what — the diff already says what.
- Data anomalies get logged rather than silently worked around. Something unambiguously
  broken with an obvious fix gets fixed *and* logged.
- Decisions that shape the code get an ADR in `docs/adr/`.

## Licence and content

Code is Apache-2.0 (see [`LICENSE`](LICENSE)). Card data, card images, and the names and
likenesses they contain are the property of Cover Corp., used under the
[Derivative Works Guidelines](https://hololivepro.com/en/terms/) — the licence covers this
repository's code, not that content. This project is not affiliated with or endorsed by
Cover Corp. or hololive production.

By opening a pull request you agree that your contribution is licensed under Apache-2.0.
