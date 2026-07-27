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
 * **Junction filters use `id IN (SELECT card_id FROM …)`, never a join.** A join against
 * a junction returns one row per matching *value*, so `colors=blue,red` would return a
 * card once per colour it matches and corrupt both the page and the count. The `IN` form
 * returns one row per card and is still fully index-driven — verified on real D1:
 * `SEARCH card_colors USING PRIMARY KEY (color_code=?)` plus a Bloom filter, no scan.
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

  const junction = (table: string, column: string, values: readonly string[]) => {
    conditions.push(
      `id IN (SELECT card_id FROM ${table} WHERE ${column} IN (${values
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
    inClause("id", searchIds);
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

export function cardsByIdsSql(ids: readonly string[]): { sql: string; params: unknown[] } {
  return {
    sql: `SELECT ${CARD_COLUMNS} FROM cards WHERE id IN (${ids
      .map(() => "?")
      .join(", ")}) ORDER BY card_number, id`,
    params: [...ids],
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
