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
 *
 * **Two vocabularies live in `counts`, and mixing them is the bug D26 fixed.** The first
 * five describe what *our database* did; the `source_*` trio describes what the *official
 * card list* did. They diverge exactly when we touch a row for our own reasons — the
 * translation rework rewrote every card's payload, so `changed` was 2,463 while the game
 * had published nothing. Lead with the source numbers; the re-seed number is a footnote,
 * not a headline.
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

  // --- what the database did ---
  new: number;
  changed: number;
  qa_updated: number;
  unchanged: number;
  removed: number;
  missing_from_build: number;

  // --- what the official card list did (D26) ---
  /**
   * Cards the source published since the last seed. Equal to `new` by construction — a
   * card id exists only once the official list carries it — and named separately because
   * this page speaks the source's vocabulary, not the database's.
   */
  source_added?: number;
  /** Cards whose Japanese text or columns the source edited. */
  source_changed?: number;
  /** Cards whose Q&A moved, whether or not anything else about them did. */
  faq_changed?: number;
};

export type StatusReport = {
  /** When `seed` ran. */
  generated_at: string;
  /** When the `cards.json` it seeded from was built. */
  built_at?: string;
  /** `diff` for an incremental upsert, `full` for a complete rewrite. */
  mode: string;
  counts: StatusCounts;
  /**
   * How many entries each list below is truncated to (D26).
   *
   * Compare a list's `length` against its count in `counts` to decide whether to render
   * "and N more" — never trust `length` as a total. Absent on an artifact written before
   * D26, in which case the lists are complete but may be enormous.
   */
  list_cap?: number;
  new: StatusEntry[];
  changed: StatusEntry[];
  qa_updated: StatusEntry[];
  source_added?: StatusEntry[];
  source_changed?: StatusEntry[];
  faq_changed?: StatusEntry[];
  removed: StatusEntry[];
  writes?: Record<string, number>;
};

/**
 * `StatusTab` and `StatusKind` are **gone** (ADR 0009 D19), and D26 did not bring them
 * back.
 *
 * The page has no tabs and no per-card badges to type. Production reported
 * `changed: 2463, new: 0` — a full reseed marks every card changed — so one tab held all
 * 2,463 entries and the other held none, in two view modes with a sort control and
 * pagination over a list nobody can act on.
 *
 * What D26 *did* restore is a list for the **source** buckets only, which are a different
 * animal: 0–100 entries, each a specific card a reader can open. The re-seed list stays a
 * single number. That is why the artifact caps every list and keeps the true totals in
 * `counts` — a set release cannot regress this page into pagination.
 *
 * Every field is still typed and still parsed, rendered or not: `/api/status` returns
 * them, and narrowing the *page* is not a reason to lie about the artifact's shape.
 */
