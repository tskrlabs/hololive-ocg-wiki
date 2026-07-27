/**
 * `status.json`, as the **seeder** writes it (D11, ADR 0004).
 *
 * Not the same shape v1's status page consumed, and it could not be: v1's artifact was
 * written by `migrate.js` and described a source-to-source diff, while this one is
 * written by `holo-data seed` and describes a *database* diff — knowledge `publish`
 * cannot have. The differences, all deliberate:
 *
 * | v1 | v2 |
 * |---|---|
 * | `generatedAt`, `diff.qaUpdated` | snake_case throughout |
 * | `source.total` / `source.valid` | `counts.total` — there is no valid-vs-source split |
 * | `skipped[]` with `missingFields` | **absent** — validation failures are reported by `build`'s collect-and-report, not here |
 * | `imagePath` | `image_key` (D9) |
 * | — | `built_at`, `counts.missing_from_build`, `writes{}` |
 *
 * `writes` is seeder telemetry — rows written, rows read, batch count, database size. It
 * is an audit record of the run and is deliberately not rendered: it answers "did the
 * seed behave" for the maintainer, not "what changed" for a reader.
 */

/** One card in a diff list. */
export type StatusEntry = {
  id: string;
  card_number?: string | null;
  image_key?: string | null;
  name?: string | null;
};

export type StatusCounts = {
  total: number;
  new: number;
  changed: number;
  qa_updated: number;
  unchanged: number;
  removed: number;
  missing_from_build: number;
};

export type StatusReport = {
  /** When `seed` ran. */
  generated_at: string;
  /** When the `cards.json` it seeded from was built. */
  built_at?: string;
  /** `diff` for an incremental upsert, `full` for a complete rewrite. */
  mode: string;
  counts: StatusCounts;
  new: StatusEntry[];
  changed: StatusEntry[];
  qa_updated: StatusEntry[];
  removed: StatusEntry[];
  writes?: Record<string, number>;
};

/** The tabs the page offers. v1 also had `qaUpdated`, `removed` and `skipped`. */
export type StatusTab = "new" | "changed";

/** A per-entry badge. `skipped` is gone with the tab; the rest still occur. */
export type StatusKind = "new" | "changed" | "qaUpdated" | "removed";
