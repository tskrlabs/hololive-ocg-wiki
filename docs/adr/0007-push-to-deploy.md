# ADR 0007 — push-to-deploy, and what a fresh clone actually needs

**Status:** accepted · **Phase:** 6 · **Date:** 2026-07-27

Supersedes nothing. Extends [ADR 0001](0001-card-contract-generation.md)'s
committed-generated-output rule from the contract to the fixtures. Every decision below was
put to the maintainer during a grilling session; this ADR is the record of what came out
of it.

## Context

v2-plan.md §5 gives Phase 6 two done-whens: *push-to-deploy works*, and *a fresh clone
runs with zero CF creds*. Both looked close to met when the phase opened — the Worker was
deployed and live, `fixtures.sql` was committed, and `wrangler deploy` worked by hand.

Neither survived contact.

**Push-to-deploy** was blocked by a lockfile that had been broken since the Nuxt 4 upgrade
in `fce28d9` and could not be seen from a working laptop. **Zero credentials** was true and
still missed the point: `make dev` needed `uv`, a venv and pydantic before the site's
filter dropdowns worked.

Phase 5's [ADR 0006](0006-website.md) left one constraint for this phase: `nuxt generate`
in `apps/web` must precede `wrangler deploy` in `apps/api`, because `assets.directory`
points at a gitignored build output.

## Decisions

### `main` is the production branch; merging is the release

Work lands on `develop` per the working agreement, and phases have merged there by PR
since Phase 2. Pointing Workers Builds at `main` makes `develop` → `main` the release
action — which is how the two branches were already being used, so it names an existing
practice rather than inventing one.

Pointing it at `develop` was rejected: every intermediate commit of a phase would deploy,
which removes the only gate currently in place.

The cost is that the first merge is 17 commits and ships everything at once. That is also
what makes it a good first test — the tree is already what is live, so a successful build
produces a version identical in behaviour to the running one.

### Root directory `/`, with an explicit `--config`

| field | value |
|---|---|
| Root directory | `/` |
| Build command | `npm run generate --workspace @holo/web` |
| Deploy command | `npx wrangler deploy --config apps/api/wrangler.jsonc` |

Root at `/` because this is an npm workspace: the install has to happen at the root or
`@holo/schema` does not link into `apps/web` and `apps/api`. Rooting at `apps/api` and
`cd`-ing up from the build command was rejected for putting the install in the wrong
place and hiding the workspace dependency.

`--config` follows from that: the deploy runs from the root, not from `apps/api`. Verified
that wrangler resolves `assets.directory` relative to the **config file** rather than cwd —
98 files, all four bindings, from a clean clone.

`make check` is deliberately **not** part of the build. It needs a second toolchain in the
image, and verification is local by decision. A red build should mean "the site did not
compile", not "a Python test failed".

### No preview builds, no build caching

Non-production branch builds would upload preview versions **against the same bindings** —
there is only one D1 and one R2 (D12). A preview URL would be a second live window onto
production, and its reads count against the 5M/day that v1 already breached once
([F-014](../findings.md#f-014)). D12 deferred the preview environment deliberately;
enabling this would be that decision arriving through a side door.

Caching is off for correctness rather than cost. Builds are rare — merges to `main` only —
and a cache that restores `node_modules` between builds is the shape of a stale-artifact
bug, which is the failure this repo is built to prevent. A cold 2–3 minute build against
3,000 free minutes/month is not a constraint worth trading for.

### Node pinned to 24

The build image defaults to **22.16** and Cloudflare bumps it without notice; the repo
pinned nothing and declared `engines: >=22.6.0` while every phase was verified on 24.
`.node-version` (committed, reviewable — the same instinct as committing
`wrangler.jsonc`) now says `24`, and `engines` agrees.

A floating major, not `24.18.0`: security patches without pinning to a build image that
may not carry an exact patch. 24 also ships npm 11, which is what makes the root
`allowScripts` block meaningful at all.

### The build token is account-wide, deliberately

The R2 token is scoped to two buckets and the D1 token is separate and scoped to D1 Edit
plus Analytics Read, because both sit in `pipeline/.env` on a laptop and are handed to a
CLI an agent may drive (D4) — that is the blast radius those scopes bound.

The build token is different in kind: it never leaves Cloudflare, nothing in this repo can
read it, and the only thing that invokes it is a push to `main`. A custom token would add
a rotation chore and a "why did the build start failing" mode without narrowing anything
we control. Recorded in [`infra.md`](../infra.md) as the third token in the project.

### Fixture artifacts are committed

This is ADR 0001's rule, applied one layer out.

`seed-local-r2.sh` generated the seven `filter-options/{locale}.json` and `status.json` on
every `make dev` by running a script that imports `holo_data.build`, and therefore
pydantic. So a frontend contributor needed a full Python toolchain before the filter
dropdowns worked in six of seven locales. D12 asks for zero *Cloudflare credentials*; the
spirit is zero setup, and this was the last thing in the way.

`fixtures/artifacts/` is 64 KB, generated by `make generate`, and its staleness — including
files no longer generated — is caught by `make check`.

**`filter_options()` is not reimplemented in Node.** It encodes
[F-015](../findings.md#f-015): 41% of characters are spelled inconsistently across their
own cards, and the function picks a label by a rule that is three paragraphs of docstring.
A second copy of that rule in TypeScript is precisely the drift ADR 0001 exists to
prevent. One implementation, output committed, staleness checked.

### The fresh-clone walk is a per-phase step, not a test

Verified by hand in a scratch clone with `uv` replaced by a shim that exits 127 — so a
Python dependency fails loudly rather than passing silently on the maintainer's machine.
Results are recorded in [`progress.md`](../progress.md).

Automating it was rejected: an honest version needs a container or a scrubbed environment,
and this is a once-per-phase check, not a per-commit one. `make check` already covers the
per-commit surface. What would regress this property is a docs or tooling change, which
the manual walk catches at exactly the right cadence.

## What the rehearsal found

**`npm ci` failed on a clean clone.** The lockfile recorded `vue-router: ^4.5.1` for
`apps/web` while `apps/web/package.json` declares `^5.2.0` — the Nuxt 4 upgrade updated
the manifest and not the lock. Cloudflare's auto-install runs `npm ci`, so the first
push-to-deploy build would have failed, in a repo that was green locally.

It also meant the live site was built against a tree the manifests do not describe: local
`node_modules` held vue-router **4.6.4**, which does not satisfy Nuxt 4.5's own `^5.2.0`.
A clean install resolves 5.2.0. `make check` is green on it, including the `vue-tsc`
suppression in the Makefile whose comment describes vue-router 5 behaviour — written,
it turns out, while 4.6.4 was installed.

This is Phase 3's lesson in a different costume: the expensive bug appears only when the
thing is actually run, in the environment it will actually run in.

## Consequences

- A merge to `main` now deploys. The "commit directly, don't push" habit from earlier
  phases no longer applies to `main`; `develop` is unchanged.
- Manual and build-triggered deploys both produce **versions**, and the last promoted one
  wins — so a manual `wrangler deploy` overrides the last pushed build until the next
  push.
- `make dev` needs Node and nothing else. Working on the *contract* still needs `uv`,
  which `CONTRIBUTING.md` states plainly.
- The Phase 7 switch list grows from two to three: `workers_dev: false` joins
  `NUXT_PUBLIC_LAUNCHED` and repo visibility. It is kept on while
  [F-017](../findings.md#f-017) is open, because comparing the two origins is the only way
  that bug is visible.
- [F-018](../findings.md#f-018) is open and deliberately unfixed: D14 promised translation
  fixes as reviewable PRs, and no reviewable surface exists.
