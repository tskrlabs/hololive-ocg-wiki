/**
 * The Worker (D2, D7).
 *
 * Replaces v1's `cloudflare/worker.ts`: 1,269 lines in one file, an `if (path === …)`
 * chain, hand-rolled CORS across three helpers, and a `checkRateLimit()` that
 * unconditionally returned `true`.
 *
 * **Seven endpoints, not eight.** `/api/static-filters` is gone — see `routes/filters.ts`.
 *
 * **No static assets yet.** D2's "one Worker serves site and API" needs `apps/web`,
 * which arrives in Phase 5; the `assets` binding and SPA fallback land with it. Until
 * then this is an API-only Worker on `workers.dev`, and anything outside `/api/` is a
 * 404 rather than a half-configured SPA fallback.
 */

import { Hono } from "hono";
import { cors } from "hono/cors";
import { HTTPException } from "hono/http-exception";
import { ZodError } from "zod";

import type { Env } from "./types.ts";
import { cards, cardsList } from "./routes/cards.ts";
import { filters } from "./routes/filters.ts";
import { failure } from "./lib/respond.ts";

const app = new Hono<{ Bindings: Env }>();

/**
 * CORS.
 *
 * Under D2 the site and the API share an origin, so production browser traffic sends no
 * `Origin` header and needs none of this. It exists for local development, where Nuxt
 * runs on another port. The allowlist is a `var` so localhost never has to be compiled
 * into a production deploy.
 */
app.use("/api/*", (c, next) =>
  cors({
    origin: (origin) => {
      const allowed = (c.env.ALLOWED_ORIGINS ?? "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      return allowed.includes(origin) ? origin : undefined;
    },
    allowMethods: ["GET", "OPTIONS"],
  })(c, next),
);

app.route("/api/cards", cards);
app.route("/api/cards-list", cardsList);
app.route("/api", filters);

/** Liveness, and a cheap way to confirm the bindings resolved after a deploy. */
app.get("/api/health", (c) => c.json({ ok: true }));

app.notFound((c) => failure(c, 404, "not found"));

/**
 * One error handler.
 *
 * Invalid input is the client's problem (400); anything else is ours (500) and the
 * detail stays in the log. v1 returned a message derived from the exception's own text
 * via substring matching, which leaked `D1_ERROR` and SQL fragments before it was
 * patched.
 */
app.onError((err, c) => {
  if (err instanceof ZodError) {
    return failure(c, 400, err.issues[0]?.message ?? "invalid request");
  }
  if (err instanceof HTTPException) {
    return failure(c, err.status === 404 ? 404 : 400, err.message);
  }
  console.error("unhandled error", err);
  return failure(c, 500, "internal error");
});

export default app;
