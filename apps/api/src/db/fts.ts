/**
 * Full-text search against `cards_fts`.
 *
 * The index is trigram-tokenised over one row per card, holding all 7 locales
 * concatenated (ADR 0004). Two consequences drive everything in this file:
 *
 * 1. **A query under 3 characters matches nothing.** Trigram indexes 3-character
 *    windows, so a shorter query returns *no rows* rather than an error — the dangerous
 *    shape, because "no such card" and "your query is too short for the index" look
 *    identical to a user. Real case: `そら` is 2 characters and matches 27 cards.
 * 2. **FTS5 `MATCH` takes a query language, not a literal.** Handing it raw user input
 *    means `a AND`, `-x` and a bare `"` throw a syntax error. Verified against local D1;
 *    in v1 those fell into a catch block, and in a naive port they are a 500.
 */

/** Below this many characters, trigram cannot match and the LIKE path takes over. */
export const TRIGRAM_MIN_LENGTH = 3;

/**
 * Wrap a user's query as an FTS5 *phrase*, so no input can be read as syntax.
 *
 * Everything between double quotes is literal text to FTS5; a double quote inside is
 * escaped by doubling it. That turns every syntax error into a clean zero-hit result,
 * which is why this is the only way a query reaches `MATCH`.
 *
 * The cost is that FTS5 operators (`OR`, `NEAR`, `*`) become literal text. That is the
 * intent: this is a card wiki's search box, users type card names into it, and the
 * alternative is an injection surface into FTS5's query language for a feature nobody
 * asked for.
 */
export function escapeFtsPhrase(query: string): string {
  return `"${query.replaceAll('"', '""')}"`;
}

/**
 * Escape a string for use as a `LIKE` operand, with `\` as the escape character.
 *
 * `%` and `_` are wildcards; a user searching for `100%` means the literal text. The
 * matching SQL must declare `ESCAPE '\'` — see `SHORT_QUERY_SQL`.
 */
export function escapeLikePattern(query: string): string {
  return query.replaceAll("\\", "\\\\").replaceAll("%", "\\%").replaceAll("_", "\\_");
}

/** Which strategy a query of this length needs. */
export function searchStrategy(query: string): "match" | "like" {
  return query.length >= TRIGRAM_MIN_LENGTH ? "match" : "like";
}

/**
 * Per-column `bm25()` weights, in the column order `cards_fts` declares.
 *
 * `ORDER BY rank` is `bm25()` with every column weighted 1.0, which is why a card that
 * merely *cites* another in a ruling used to outrank the card itself — Q&A is 88% of the
 * indexed text, so it dominated by sheer volume (issue #67).
 *
 * The ratios mirror the `FullText(weight=…)` values on the models: a name is 3.0 against
 * a Q&A field's 0.5. They could never act while both lived in one column, because a
 * trigram index cannot weight fields *inside* a column — the split is what makes the
 * declared intent executable.
 *
 * A lower `bm25()` score is better, so these are relevance multipliers, not penalties:
 * `qa` at 0.1 still returns its matches, it just cannot outrank card text.
 */
const BM25_WEIGHTS = "2.0, 1.0, 0.1"; // card_number, text, qa

/**
 * Card ids matching a query, most relevant first.
 *
 * Both branches return `cards_fts.rowid`, which *is* the card id — an FTS5 column
 * cannot be indexed for lookup, so the id was put in the rowid instead (ADR 0004).
 *
 * The LIKE branch scans all 2,448 rows. That is accepted rather than hidden: it only
 * fires under 3 characters, it is bounded by the table size, the result is capped, and
 * the response is cached for an hour. It searches `text` **and** `qa`, ordering card
 * matches first: they were one column until issue #67, so restricting it to `text` would
 * quietly narrow what a 1–2 character query can find while the MATCH branch above it
 * still searched everything.
 */
export function searchSql(
  query: string,
  limit?: number,
): { sql: string; params: unknown[] } {
  // Omitting the limit means *every* match, which is what the filter path wants.
  //
  // It used to pass a flat 500, chosen when the id list was expanded one bound parameter
  // per id and something had to bound it. That cap is gone (issue #66, `idSetClause`),
  // and while it stood it made `total` lie: a common word matches far more than 500 of
  // 2,463 cards, so the count under the search box reported the cap rather than the
  // answer. The id set is bounded by the table either way.
  const bound = limit === undefined ? "" : " LIMIT ?";
  const extra = limit === undefined ? [] : [limit];

  if (searchStrategy(query) === "match") {
    return {
      sql:
        `SELECT rowid AS id FROM cards_fts WHERE cards_fts MATCH ? ` +
        `ORDER BY bm25(cards_fts, ${BM25_WEIGHTS})${bound}`,
      params: [escapeFtsPhrase(query), ...extra],
    };
  }

  // The pattern is bound twice — once per column — because SQLite has no way to reuse a
  // parameter across two predicates in the same statement.
  const pattern = `%${escapeLikePattern(query)}%`;
  return {
    sql:
      `SELECT rowid AS id FROM cards_fts ` +
      `WHERE text LIKE ?1 ESCAPE '\\' OR qa LIKE ?1 ESCAPE '\\' ` +
      `ORDER BY text LIKE ?1 ESCAPE '\\' DESC${bound}`,
    params: [pattern, ...extra],
  };
}
