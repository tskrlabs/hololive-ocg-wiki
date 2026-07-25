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

Design agreed 2026-07-25. Implementation not started. Next up: **Phase 0** — workspaces
skeleton and `packages/schema`.

## Planned structure

```
apps/web/          Nuxt SPA
apps/api/          Cloudflare Worker: Hono API + static assets
packages/schema/   the card contract (pydantic → JSON Schema → TS types + SQL)
pipeline/          Python data pipeline (uv), `holo-data` CLI
fixtures/          sample cards for credential-free local dev
```

## Disclaimer

This wiki is a fan-made, non-official project. All content is created by the community and
follows [Cover Corp.'s Derivative Works Guidelines](https://hololivepro.com/en/terms/).
Hololive names, images, and related content are the property of Cover Corp. This site is
not affiliated with or endorsed by Cover Corp. or hololive production.
