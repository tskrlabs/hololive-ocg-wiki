/**
 * `/api/info` and `/api/status` — the two editorial/telemetry artifacts, served from R2.
 *
 * **These are new in Phase 5, and they close a hole Phase 4 left.** `holo-data publish`
 * uploads `info.json` and `holo-data seed` uploads `status.json`, both into the
 * *private* `hololive-ocg-wiki-artifacts` bucket — and until now **nothing could read
 * either one**. Phase 4 built the seven card endpoints and stopped there, so the site
 * had no way to render its own about dialog or its status page.
 *
 * v1 got them from two places D11 exists to kill: `info.json` from
 * `raw.githubusercontent.com/…/main/public/info.json` (a live production dependency on a
 * git URL, which breaks the moment a repo is renamed or made private — this one is
 * private until launch) and `status.json` from a copy committed into `public/`, which
 * was therefore always as stale as the last deploy.
 *
 * Same shape as `filter-options`: fetch the object, stream the bytes through, 404 with a
 * written message when it is absent. The bucket stays private, which is what keeps the
 * 21 MB `cards.json` sitting next to these unreachable.
 */

import { Hono } from "hono";
import type { Context } from "hono";

import type { Env } from "../types.ts";
import { failure, INFO_TTL, NOTICES_TTL, STATUS_TTL } from "../lib/respond.ts";

export const artifacts = new Hono<{ Bindings: Env }>();

/**
 * Stream one artifact out of R2.
 *
 * Not parsed and re-serialised: the Worker has no reason to look inside, so the bytes R2
 * holds are the bytes the client gets. A missing object is a 404 with a message naming
 * the command that produces it — the realistic cause is a working directory that has not
 * published yet, not a malformed request, and the reader is usually the maintainer.
 */
async function stream(
  c: Context<{ Bindings: Env }>,
  key: string,
  ttl: number,
  hint: string,
): Promise<Response> {
  const object = await c.env.ARTIFACTS.get(key);
  if (!object) return failure(c, 404, `no ${key} published — run \`${hint}\``);

  c.header("Cache-Control", `public, max-age=${ttl}`);
  c.header("Content-Type", "application/json; charset=utf-8");
  return c.body(object.body);
}

/**
 * `/api/info` — the about/disclaimer panel's editorial copy.
 *
 * Committed at `content/info.json` and uploaded by `publish`, so it is reviewed as a
 * diff rather than edited in a dashboard. It deliberately carries **no facts about the
 * card data**: v1's copy embedded "Our database has 2448 cards (June 19, 2026)" in its
 * prose, hand-updated and therefore permanently wrong. The card count comes from
 * `/api/status` instead.
 */
artifacts.get("/info", (c) => stream(c, "info.json", INFO_TTL, "holo-data publish"));

/**
 * `/api/status` — what the last seed actually did.
 *
 * Written by `seed` rather than `publish` (D11), because it describes a *database diff*
 * — knowledge `publish` cannot have. It records D1's own reported `rows_written`, so it
 * is an audit record of the run rather than a restatement of the estimate.
 *
 * The site reads it twice: the status page renders the new/changed lists, and the info
 * dialog takes `counts.total` and `generated_at` from it for the card count and
 * last-updated date.
 */
artifacts.get("/status", (c) =>
  stream(c, "status.json", STATUS_TTL, "holo-data seed --confirm"),
);

/**
 * `/api/notices` — the non-card entries the official site publishes into its card list.
 *
 * Currently one: a Selection Cup format-legality notice stating which products are legal
 * and how card-number matching works across reprints. It is the legend for the
 * `card_sets` value the same update added to ~660 cards.
 *
 * Served from R2 rather than D1 for the `filter-options` reason (ADR 0004): a handful of
 * records, the same answer for every user until the next pipeline run, nothing that
 * needs an index. Keeping them out of `cards` also avoids dropping `NOT NULL` from
 * `card_number` and `rarity_code` on a populated table — see `holo_schema.notice`.
 *
 * Absent artifact returns an empty collection rather than a 404: "no notices published"
 * and "no notices exist" are the same answer to a caller, and a site that renders a
 * notices section should not have to treat a 404 as success.
 */
artifacts.get("/notices", async (c) => {
  const object = await c.env.ARTIFACTS.get("notices.json");
  if (!object) {
    c.header("Cache-Control", `public, max-age=${NOTICES_TTL}`);
    return c.json({ generated_at: null, schema_version: 1, notices: [] });
  }

  c.header("Cache-Control", `public, max-age=${NOTICES_TTL}`);
  c.header("Content-Type", "application/json; charset=utf-8");
  return c.body(object.body);
});
