# Phase 6 — grilling log

**Status:** ✅ grilling complete — 15 decisions, implementation done bar the dashboard step
**Held:** 2026-07-27
**Outcome:** [ADR 0007](adr/0007-push-to-deploy.md) · progress in [`progress.md`](./progress.md)

The record of the Phase 6 design interview. The ADR states the decisions; this states the
**alternatives that were rejected and why**, so a later session reopening one starts from
the reasoning rather than from scratch.

Read alongside [`v2-plan.md`](./v2-plan.md) §5 (the phase's done-when), D12 (single
environment, local fixtures) and D14 (open source, maintainer-only steps).

## State at the start of Phase 6

Established by inspection, not assumption:

- **The site is live** at `hololive-ocg-wiki.tskrlabs.com`, deployed by hand from
  `develop`'s tree, version `c44d51a1`. `wrangler deploy` is a direct upload — Cloudflare
  has no idea this repo exists.
- **`main` is 17 commits behind `develop`**, sitting at `ea0abcc docs: v2 design plan`.
  Everything from Phase 0 onward is on `develop` only.
- **The fixtures half looked done** — `fixtures.sql`, 34 cards, local R2 seeding, all
  committed and working.
- **`make dev` needed Python.** `seed-local-r2.sh` runs `build_local_artifacts.py`, which
  imports pydantic. Confirmed by running it against stock `python3`: `ModuleNotFoundError`.
- **No `CONTRIBUTING.md`, no `LICENSE`**, and `README.md` claimed "Phases 0–4 done, Phase
  5 in progress… nothing is deployed yet".
- Build image facts checked rather than assumed: Node defaults to **22.16**, Python 3.13
  is present, `npm ci` is the auto-install.

## The questions

### Q1 — What is Phase 6's scope?

**Decided: all four — Workers Builds, the fixtures gap, docs, phase record.**

The plan's one-line done-when hides that the fixtures half was nearly met and the docs
half was undefined. Ordering matters: the build config is what the docs describe, so it
comes first.

**Kept out, deliberately:** `CONTEXT.md` (a `/domain-modeling` artifact, not a launch
blocker), making the repo public, and flipping `NUXT_PUBLIC_LAUNCHED` — all Phase 7.

### Q2 — Which branch triggers a build?

**Decided: `main`.**

**Rejected — `develop`:** every intermediate commit of a phase would deploy, including a
half-finished one, removing the only gate that exists. The counter-argument (that `main`
is currently a dead branch) is true and self-correcting: the first merge fixes it.

### Q3 — Root directory and commands

**Decided: root `/`, build `npm run generate --workspace @holo/web`, deploy
`npx wrangler deploy --config apps/api/wrangler.jsonc`.**

**Rejected — root `apps/api`:** Cloudflare's auto-install would run there, and this is an
npm workspace — `@holo/schema` would not link into either app. It also hides the
workspace relationship from anyone reading the build config.

**Rejected — `make check` as the build command:** needs `uv` and a second toolchain
install per build, and verification is local by decision. A red build should mean the site
did not compile.

Verified during the interview that `--config` makes wrangler resolve `assets.directory`
against the config file rather than cwd. Without that, the deploy command would have had
to `cd`.

### Q4 — Preview builds for non-production branches?

**Decided: off.**

The deciding fact is that there is no preview *environment*. A preview version uploads
with the **same bindings** — same D1, same R2 — so a preview URL is a second live window
onto production data, and its reads count against the 5M/day v1 already breached once
(F-014). D12 deferred a preview environment deliberately; this would be that decision
arriving through a side door.

**Cost accepted:** PRs get no preview link. With one contributor, that costs nothing
today. Revisit alongside D12's own post-launch revisit.

### Q5 — Build caching?

**Decided: off.**

Not about minutes — 2–3 min against 3,000/month is noise. About correctness: a cache that
restores `node_modules` across builds is the shape of a stale-generated-artifact bug, and
this repo exists partly to prevent that class (ADR 0001, the `--check` flags, the
pre-commit hook). Builds are rare enough that a cold build is nearly free.

### Q6 — Pin the Node version?

**Decided: `.node-version` = `24`, and raise `engines.node` to `>=24`.**

Unpinned, the build would run 22.16 while every phase was verified on 24 — a difference
that surfaces as a build failure long after the change that caused it.

**Rejected — pin `22`** to match the platform default: then the laptop is the odd one out
and you would have to downgrade locally to keep them honest.

**Rejected — a `NODE_VERSION` build variable:** invisible in review, and dashboard-only
config is what `infra.md` exists to compensate for. A committed file is reviewable.

Noticed while checking: the root `allowScripts` block is an npm 11 feature, and npm 11
ships with Node 24. Pinning 22 would have silently made it inert.

### Q7 — Which token deploys?

**Decided: Cloudflare's auto-generated one.**

**Rejected — mint a scoped token** (Workers Scripts Edit + R2 + D1). Narrower on paper,
but the thing it defends against is Cloudflare's own CI. The project's other two tokens
are tightly scoped because they live in `pipeline/.env` and are handed to a CLI an agent
may drive (D4); the build token never leaves Cloudflare and is invoked only by a push to
`main`. Different threat, different answer — written down in `infra.md` so the
inconsistency reads as a decision rather than an oversight.

### Q8 — Disable `workers.dev` now?

**Decided: keep it until Phase 7.**

It is the **diagnostic** for F-017 — the zone's managed `robots.txt` rewrites the custom
domain but not `workers.dev`, and comparing the two is the only reason that bug was
caught. `infra.md` already prescribes curling both after a domain change. Turning it off
would remove the control from the one experiment worth rerunning at launch.

**Cost accepted:** a second reachable origin for a deliberately invisible site. Bounded —
un-announced, and `noindex` is in the HTML there too. Added to the Phase 7 switch list,
which grows from two to three.

### Q9 — How does `make dev` stop needing Python?

**Decided: commit the generated artifacts (64 KB), with a `--check` gate.**

**Rejected — reimplement `filter_options()` in Node.** It encodes F-015 (41% of characters
spelled inconsistently across their own cards) and a label-selection rule that takes three
paragraphs to explain. A second implementation of that is exactly the drift ADR 0001
exists to prevent. This was the strongest temptation and the clearest no.

**Rejected — document "run `uv sync` first".** Honest, but trades D12's headline property
for a 64 KB file.

The `--check` gate also catches **orphans** — a file no longer generated but still
committed would otherwise keep being uploaded to local R2 long after its reason expired.

**Left alone:** `smoke.sh` also shells out to `python3`, but stdlib-only. That needs an
*interpreter*, not a *toolchain*, and one ships with macOS and essentially every Linux.
Noted in `CONTRIBUTING.md` rather than rewritten.

### Q10 — How is "fresh clone works" verified?

**Decided: a manual walk in a scratch clone, recorded in `progress.md`.**

**Rejected — an automated fresh-clone test.** Honest automation needs a container or a
scrubbed environment; without one it tests the maintainer's machine. It is a once-per-phase
check, and what regresses it is a docs or tooling change — which the manual walk catches at
the right cadence.

Predicted during the interview and worth keeping straight: a fresh clone needs **network**
(`npx` downloads workerd), just not *credentials*. The existing "no token, no network"
line is a claim about the fixture *data*, not the tooling.

**This is the question that paid for itself** — see "What it found" below.

### Q11 — What does `CONTRIBUTING.md` say?

**Decided: four sections — the credential-free path, maintainer-only steps, fixing a bad
translation, and the contract trap.**

The wrinkle: D14 promised translation fixes as reviewable PRs via a `corrections/`
overlay, and ADR 0002 replaced that mechanism with cache entries in the **gitignored**
`pipeline/locales/`. Durability improved; reviewability disappeared silently.

**Decided not to fix it in Phase 6.** Closing it is pipeline design work — what a
committed correction file looks like, how `translate` merges it, how a correction is
verified without a Poe key — and deserves its own pass. The repo is private, so nobody is
being turned away. Logged as [F-018](./findings.md#f-018) with three options sketched.
`CONTRIBUTING.md` says plainly that a fix goes through an issue rather than implying a PR
path that does not exist.

### Q12 — License, and when?

**Decided: Apache-2.0, in Phase 6, copyright `lichingchester (tskrlabs)`.**

Matches v1, so the archive and this repo do not disagree about one lineage of code. Both
brand names on the line, at the maintainer's direction.

**Rejected — defer to Phase 7:** `CONTRIBUTING.md` lands this phase, and inviting
contributions to an all-rights-reserved repo is the incoherent state. The two decisions
are unrelated; only one has a deadline.

The licence covers **code**. Card data and art stay Cover Corp.'s under the Derivative
Works Guidelines — stated in the README and `CONTRIBUTING.md`, not in the LICENSE.

### Q13 — Which docs get corrected?

**Decided: `README.md`, `infra.md`, `progress.md`, `v2-plan.md`'s amendments table.**

`README.md` was the outlier and the front door — it claimed Phase 5 was in progress and
nothing was deployed. `infra.md` gains a Workers Builds section because that config lives
**only** in a dashboard, which is the exact failure v1 had and this runbook exists to
prevent.

**Left alone — `docs/agents/domain.md`**, which still says "this repo is pre-implementation".
Stale, but correcting it invites writing `CONTEXT.md`, which Q1 scoped out. One visibly
stale sentence pointing at deferred work beats half-doing it.

### Q14 — How does the phase record itself?

**Decided: ADR 0007 + this log, both deliberately short.**

Phase 5's ADR is 318 lines for fifteen commits of code; Phase 6 is configuration, four
docs and a 64 KB artifact. Length that is not earned makes the ADR set less useful, and
the pattern in this repo is that document size tracks the weight of what was decided.
ADR 0007 came out at 158 lines — ADR 0003's size, which was the target.

### Q15 — Execution order?

**Decided: land on `develop` → rehearse in a scratch clone → connect the dashboard →
merge to `main` → verify.**

Rehearsing **before** connecting is load-bearing: it is the last point where a mistake
costs nothing.

The failure mode is mild and worth stating, because it changes the risk calculus: Workers
Builds promotes **versions**, so a failed build promotes nothing and the live site is
untouched. The bad outcome is "no deploy", not "broken deploy".

## What it found

**`npm ci` failed on a clean clone**, at the first command of the rehearsal:

```
npm error Missing: vue-router@5.2.0 from lock file
```

The lockfile recorded `^4.5.1` for `apps/web` while its `package.json` declares `^5.2.0` —
the Nuxt 4 upgrade in `fce28d9` updated the manifest and not the lock. **The first
push-to-deploy build would have failed**, in a repo that was green locally and had already
deployed successfully by hand.

Worse, quietly: the live site was built against a tree the manifests do not describe. Local
`node_modules` held vue-router 4.6.4, which does not satisfy Nuxt 4.5's own `^5.2.0`
requirement. A clean install resolves 5.2.0; `make check` is green on it.

Q10 was almost answered with "it is true by construction". It was not.

## Done when

- Workers Builds is connected to the existing Worker, production branch `main`, with the
  three fields from ADR 0007
- a merge to `main` produces a green build and a new version, verified against the real
  2,448 cards on the custom domain
- a scratch clone runs `npm ci` → `nuxt generate` → `wrangler deploy --dry-run` with no
  Python at all
- `make dev` serves working filter dropdowns in all 7 locales from a clone with `uv`
  unavailable
- `CONTRIBUTING.md` and `LICENSE` exist; `README.md` describes the site that is actually
  running

## Open, deliberately

- **[F-018](./findings.md#f-018)** — a translation fix has no reviewable surface. Three
  options sketched, none chosen. Pipeline work, not docs work.
- **`CONTEXT.md`** — the domain glossary `docs/agents/domain.md` expects. Not a launch
  blocker; `/domain-modeling` creates it when terms actually need resolving.
- **Preview environment** — still deferred with D12, and Q4 declined to smuggle one in
  through preview URLs. Revisit post-launch, when live data needs protecting.
- **Three switches at Phase 7** — `NUXT_PUBLIC_LAUNCHED`, `workers_dev: false`, repo
  public. If they are missed, the new site stays invisible.
