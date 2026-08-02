/**
 * Reading cards out of D1.
 *
 * Every function here is pure — it returns SQL and parameters, and the route executes
 * it. That is what lets the query shapes be tested with `node --test` and no database:
 * the expensive mistakes in Phase 3 were all shapes, not values.
 *
 * The row → card projection lives in `rowToCard`, which reassembles a `Card` from the
 * columns and the JSON payload and hands it to the shared `localize()`. Phase 4 added
 * `color_codes` and `card_sets` to the payload precisely so this needs no second query
 * against the junction tables — see ADR 0005.
 */

import type { Card } from "@holo/schema";
import type { LocalizedCard } from "@holo/schema";
import { localize } from "@holo/schema/localize";
import type { ColorCode, Locale } from "@holo/schema/enums";

/** Columns every card-returning query needs, minus the Q&A payload. */
const CARD_COLUMNS = `id, card_number, card_type_code, rarity_code, bloom_level_code,
    image_key, source_image_url, hp, life, baton_touch_count, baton_touch_types,
    illustrator, payload`;

/**
 * Dual-colour cards are printed as one fused icon and stored that way.
 *
 * `blue_red` is a single printed symbol, not "blue and red" — storage keeps it as
 * printed so the card renders one icon rather than two and a comma. Expanding it is
 * therefore a *query-layer* job, pinned by `test_fused_colours_are_stored_as_printed`
 * in the seeder's tests.
 *
 * Without this, filtering by `blue` silently misses the 5 `blue_red` cards. v1 did no
 * expansion at all and exposed `blue_red`/`white_green` as their own checkboxes, so its
 * blue filter was quietly incomplete.
 */
const FUSED_COLORS: Readonly<Record<string, readonly ColorCode[]>> = {
  blue: ["blue_red"],
  red: ["blue_red"],
  white: ["white_green"],
  green: ["white_green"],
};

/** A requested colour plus any fused code that contains it. */
export function expandColors(colors: readonly string[]): string[] {
  const expanded = new Set<string>();
  for (const color of colors) {
    expanded.add(color);
    for (const fused of FUSED_COLORS[color] ?? []) expanded.add(fused);
  }
  return [...expanded].sort();
}

/**
 * A set of card ids as **one** bound parameter, not one placeholder each.
 *
 * D1 caps a query at 100 bound parameters. Expanding an id list into `id IN (?, ?, …)`
 * therefore breaks the moment a search matches more than 100 cards — and the popular
 * queries are all above that line. Production returned a 500 for `hBP03`, `hBP01`,
 * `ホロメン` and `エール` while `hSD01` (65 matches) and `白上フブキ` (73) worked, which is
 * the parameter cap showing through as a search feature that fails on common words
 * (issue #66). Passing the ids as a JSON array makes the count irrelevant.
 *
 * **`IN (SELECT …)` here, even though #40 replaced exactly that form with `EXISTS`.**
 * The two cases are opposites, and the reason is what can be indexed. A junction table
 * has `idx_card_*_card_id`, so a correlated `EXISTS` probes it per card and the walk
 * stops at `LIMIT`. `json_each` has no index at all, so the same correlation re-parses
 * and rescans the whole array for every card considered. Measured on production over
 * the 283 `hBP03` ids:
 *
 * | form | page (LIMIT 50) | count(*) |
 * |---|---|---|
 * | `IN (SELECT value FROM json_each(?))` | 1,132 rows | 849 rows |
 * | `EXISTS (SELECT 1 FROM json_each(?) …)` | 169,940 rows | 659,306 rows |
 *
 * 150× and 776× worse respectively — so the rule from #40 is "correlate against
 * something indexed", not "always use EXISTS".
 *
 * The cost scales with the id set rather than the page (100 ids read 300 rows, 283 read
 * 1,132), which is the same materialise-then-sort shape #40 measured. It is accepted
 * here because the alternative is a broken endpoint: the id set is bounded by the card
 * count, and a search is one query per keystroke-debounce rather than the default view.
 */
const idSetClause = "id IN (SELECT value FROM json_each(?))";

export interface CardFilters {
  search?: string;
  name?: string;
  tag?: string;
  set?: string;
  colors?: string[];
  cardTypes?: string[];
  rarity?: string[];
  bloomLevel?: string[];
  page: number;
  limit: number;
}

interface WhereClause {
  sql: string;
  params: unknown[];
}

/**
 * The WHERE fragment shared by the count and page queries.
 *
 * **Junction filters use a correlated `EXISTS`, never a join and never `IN (SELECT …)`.**
 *
 * A join against a junction returns one row per matching *value*, so `colors=blue,red`
 * would return a card once per colour it matches and corrupt both the page and the count.
 * That rules out the join; the subquery forms both return one row per card.
 *
 * Between the two subquery forms the difference is where the sort happens.
 * `id IN (SELECT card_id …)` makes the id set the driver, so SQLite materialises every
 * match and sorts it in a temp b-tree *before* `LIMIT` applies — the page size then makes
 * no difference at all, and a filter costs the same 1,328 rows at `LIMIT 20` as at
 * `LIMIT 200`. The correlated `EXISTS` inverts it: `cards` is walked in
 * `idx_cards_card_number` order and the scan stops at `LIMIT`, with the junction probed
 * per row through `idx_card_colors_card_id` (the covering index Phase 3 added for the
 * seeder's deletes). Only the `id` tiebreak within one card number is sorted, and the
 * saving grows with the match set instead of shrinking:
 *
 * | filter | `IN` | `EXISTS` |
 * |---|---|---|
 * | 1 colour | 1,328 | 845 |
 * | 2 colours | 2,713 | 897 |
 * | top tag (`JP`) | 3,885 | 269 |
 * | top set | 1,513 | 152 |
 *
 * Measured on production D1 over 2,463 cards — 77% fewer rows read overall, which is
 * 66% → 15% of the free read tier at v1's traffic. See issue #40.
 *
 * Groups are OR'd internally and AND'd against each other, matching the checkbox UI.
 */
export function buildWhere(filters: CardFilters, searchIds?: readonly string[]): WhereClause {
  const conditions: string[] = [];
  const params: unknown[] = [];

  const inClause = (column: string, values: readonly string[]) => {
    conditions.push(`${column} IN (${values.map(() => "?").join(", ")})`);
    params.push(...values);
  };

  // The subquery is aliased so `cards.id` in the correlation can never be captured by
  // the junction's own columns, whatever they are named.
  const junction = (table: string, column: string, values: readonly string[]) => {
    conditions.push(
      `EXISTS (SELECT 1 FROM ${table} j WHERE j.card_id = cards.id AND j.${column} IN (${values
        .map(() => "?")
        .join(", ")}))`,
    );
    params.push(...values);
  };

  // Search is resolved against the FTS table first, then intersected here. An empty
  // id list means the search matched nothing, which must yield no cards — not every
  // card, which is what an omitted condition would do.
  if (searchIds !== undefined) {
    if (searchIds.length === 0) return { sql: "WHERE 1 = 0", params: [] };
    conditions.push(idSetClause);
    params.push(JSON.stringify(searchIds));
  }

  if (filters.colors?.length) junction("card_colors", "color_code", expandColors(filters.colors));
  if (filters.tag) junction("card_tags", "tag", [filters.tag]);
  if (filters.set) junction("card_sets", "set_name", [filters.set]);

  if (filters.cardTypes?.length) inClause("card_type_code", filters.cardTypes);
  if (filters.rarity?.length) inClause("rarity_code", filters.rarity);
  if (filters.bloomLevel?.length) inClause("bloom_level_code", filters.bloomLevel);

  // The source-locale name — the stable per-character identity. See schema.sql.
  if (filters.name) {
    conditions.push("name_ja = ?");
    params.push(filters.name);
  }

  return {
    sql: conditions.length ? `WHERE ${conditions.join(" AND ")}` : "",
    params,
  };
}

/** One page of filtered cards, ordered by card number. */
export function filterPageSql(
  filters: CardFilters,
  searchIds?: readonly string[],
): { sql: string; params: unknown[] } {
  const where = buildWhere(filters, searchIds);
  return {
    sql: `SELECT ${CARD_COLUMNS} FROM cards ${where.sql} ORDER BY card_number, id LIMIT ? OFFSET ?`,
    params: [...where.params, filters.limit, (filters.page - 1) * filters.limit],
  };
}

/** How many cards match, ignoring pagination. */
export function filterCountSql(
  filters: CardFilters,
  searchIds?: readonly string[],
): { sql: string; params: unknown[] } {
  const where = buildWhere(filters, searchIds);
  return { sql: `SELECT count(*) AS total FROM cards ${where.sql}`, params: where.params };
}

export function cardByIdSql(id: string): { sql: string; params: unknown[] } {
  return {
    sql: `SELECT ${CARD_COLUMNS}, qa_payload FROM cards WHERE id = ?`,
    params: [id],
  };
}

/**
 * One card by its `image_key` — the lookup behind a card URL (ADR 0009 D6).
 *
 * `/{locale}/card/{set}/{stem}` is `image_key` verbatim, so this is how a card page
 * resolves. Deriving the id client-side was rejected: it would mean shipping a
 * 2,463-entry key→id map to every visitor.
 *
 * Selects `qa_payload` like `cardByIdSql`, because a card *page* shows Q&A (35% of cards
 * have some) where a list tile does not.
 *
 * Matching is **case-sensitive**, which is the stored form and therefore canonical.
 * `image_key` preserves the printed casing (`hSD01/hSD01-001_OSR`), and an index on it
 * only serves exact matches — so a wrong-case URL misses here and is redirected by the
 * route rather than silently resolved. Commit 6's unique index makes this a seek; without
 * it, it is a 2,463-row scan per card view.
 */
export function cardByImageKeySql(imageKey: string): { sql: string; params: unknown[] } {
  return {
    sql: `SELECT ${CARD_COLUMNS}, qa_payload FROM cards WHERE image_key = ?`,
    params: [imageKey],
  };
}

/**
 * The same lookup, case-insensitively — the error path only.
 *
 * Verified over the real set: lowercasing all 2,463 keys still yields 2,463 distinct
 * values, so no two cards differ only by case and this can never be ambiguous. It costs a
 * second query and a full scan, which is why it runs *only* after the exact match has
 * already missed — a wrong-case URL is rare, and paying for it on the hot path would be
 * the wrong trade.
 */
export function cardKeyByLowercaseSql(imageKey: string): { sql: string; params: unknown[] } {
  return {
    sql: `SELECT image_key FROM cards WHERE lower(image_key) = lower(?) LIMIT 1`,
    params: [imageKey],
  };
}

/**
 * Several cards by id.
 *
 * Takes the same one-parameter id set as `buildWhere` — see `idSetClause`. This is the
 * second half of issue #66: `/api/cards/search` re-fetches the ids the index returned,
 * so it hit the 100-parameter cap too, and `limit=101` was a 500 where `limit=100` was
 * not.
 */
export function cardsByIdsSql(ids: readonly string[]): { sql: string; params: unknown[] } {
  return {
    sql: `SELECT ${CARD_COLUMNS} FROM cards WHERE ${idSetClause} ORDER BY card_number, id`,
    params: [JSON.stringify(ids)],
  };
}

/**
 * Every card carrying a given card number.
 *
 * Returns a list, not a card: `card_number` is not unique. 2,448 cards share 1,228
 * numbers because rarity variants all carry one number — hBP01-104 has nine.
 */
export function cardsByCardNumberSql(cardNumber: string): { sql: string; params: unknown[] } {
  return {
    sql: `SELECT ${CARD_COLUMNS} FROM cards WHERE card_number = ? ORDER BY id`,
    params: [cardNumber],
  };
}

/**
 * One representative card per requested card number — the lowest id of each group.
 *
 * `min(id)` is compared numerically via `CAST`, because ids are numeric *strings*: a
 * lexicographic min would pick "1000" over "999".
 */
export function firstCardPerNumberSql(
  cardNumbers: readonly string[],
): { sql: string; params: unknown[] } {
  const placeholders = cardNumbers.map(() => "?").join(", ");
  return {
    sql: `SELECT ${CARD_COLUMNS} FROM cards WHERE id IN (
        SELECT CAST(min(CAST(id AS INTEGER)) AS TEXT) FROM cards
        WHERE card_number IN (${placeholders}) GROUP BY card_number
      ) ORDER BY card_number`,
    params: [...cardNumbers],
  };
}

/** A D1 row, as selected by the queries above. */
export interface CardRow {
  id: string;
  card_number: string;
  card_type_code: string;
  rarity_code: string;
  bloom_level_code: string | null;
  image_key: string;
  source_image_url: string;
  hp: number | null;
  life: number | null;
  baton_touch_count: number | null;
  baton_touch_types: string | null;
  illustrator: string | null;
  payload: string;
  qa_payload?: string;
}

/**
 * Rebuild a card from its row and project it into one locale.
 *
 * The row carries everything needed — that is the property Phase 4's payload change
 * bought, and it is asserted end-to-end by `test_a_card_reassembles_from_its_row_alone`
 * on the Python side. `localize()` itself is the shared implementation from
 * `packages/schema`, already pinned byte-for-byte against the Python reference.
 */
export function rowToCard(row: CardRow, locale: Locale): LocalizedCard {
  const payload = JSON.parse(row.payload) as Partial<Card>;

  const card = {
    ...payload,
    id: row.id,
    card_number: row.card_number,
    card_type_code: row.card_type_code,
    rarity_code: row.rarity_code,
    image_key: row.image_key,
    source_image_url: row.source_image_url,
    ...(row.bloom_level_code !== null && { bloom_level_code: row.bloom_level_code }),
    ...(row.hp !== null && { hp: row.hp }),
    ...(row.life !== null && { life: row.life }),
    ...(row.baton_touch_count !== null && { baton_touch_count: row.baton_touch_count }),
    ...(row.baton_touch_types !== null && {
      baton_touch_types: JSON.parse(row.baton_touch_types),
    }),
    ...(row.illustrator !== null && { illustrator: row.illustrator }),
  } as Card;

  // Q&A lives in its own column and is only selected by the detail route, so a list
  // response simply has none — which is what `localize()` renders as an empty array.
  if (row.qa_payload) {
    const qa = JSON.parse(row.qa_payload) as Record<string, unknown[]>;
    for (const [qaLocale, items] of Object.entries(qa)) {
      const translation = card.translations?.[qaLocale as Locale];
      if (translation) {
        (translation as { qa_items?: unknown[] }).qa_items = items;
      }
    }
  }

  return localize(card, locale);
}
