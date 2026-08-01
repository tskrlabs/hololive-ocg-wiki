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

/**
 * `StatusTab` and `StatusKind` are **gone** (ADR 0009 D19).
 *
 * The page no longer has tabs or per-card badges to type. Production reports
 * `changed: 2463, new: 0` — a full reseed marks every card changed — so one tab held all
 * 2,463 entries and the other held none, in two view modes with a sort control and
 * pagination over a list nobody can act on.
 *
 * The per-card arrays above are still typed and still parsed: `/api/status` returns them,
 * and narrowing the *page* is not a reason to lie about the artifact's shape.
 */
