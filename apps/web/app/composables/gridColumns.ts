/**
 * How many card columns fit a given width.
 *
 * v1 keyed the column count on a hardcoded viewport ladder — 6 below 1280, 8 below 1536,
 * 10 below 2000, 12 above — and **widening the window made the cards smaller** at two of
 * those steps. Each rung added two columns at once, which outpaced the width gained:
 *
 * | viewport | old cols | old tile |
 * |---|---|---|
 * | 1440 | 8 | 178px |
 * | 1536 | 10 | **152px** ← smaller than at 1440 |
 * | 1920 | 10 | 190px |
 * | 2000 | 12 | **165px** ← smaller than at 1920 |
 *
 * The fix is to stop asking "which breakpoint is this" and start asking "how many tiles
 * of about `TARGET_TILE` fit". Columns then follow from the width instead of from a
 * table, so tile size can never fall as the window grows, and there is no ladder to
 * re-tune when the filter rail takes 280px off the content width — the rail is simply a
 * narrower `width`. See issue #43.
 *
 * This is a plain function rather than a composable so it can be tested without mounting:
 * the property that matters is arithmetic over every width, which no fixture set covers.
 */

/** The tile width the grid aims for. Columns are chosen to land near it. */
export const TARGET_TILE = 190;

/**
 * The band a tile may actually occupy.
 *
 * `floor(width / TARGET_TILE)` alone drifts out of it at the extremes — at 752px wide
 * three columns give a 251px tile, wider than a card wants to be. The bounds pull the
 * count back, and they are what keep the result inside 150–240px at every width from a
 * 320px phone to a 3840px display.
 */
export const MIN_TILE = 150;
export const MAX_TILE = 240;

/** Two columns is the narrowest grid that still reads as a grid. */
export const MIN_COLUMNS = 2;

/**
 * The column count for a content width, in CSS pixels.
 *
 * Monotonic by construction: the count never decreases as `width` grows, and the tile
 * size it implies never decreases either. Both are asserted over a full width sweep in
 * `tests/grid.test.ts`, because a single-width example cannot see either property.
 */
export function columnsForWidth(width: number): number {
  if (!Number.isFinite(width) || width <= 0) return MIN_COLUMNS;

  let columns = Math.max(MIN_COLUMNS, Math.floor(width / TARGET_TILE));

  // Too few columns leaves tiles wider than a card should be; too many squeezes them
  // under the floor. At most one of these loops ever runs.
  while (width / columns > MAX_TILE) columns++;
  while (columns > MIN_COLUMNS && width / columns < MIN_TILE) columns--;

  return columns;
}

/**
 * The geometry `RecycleScroller` needs up front.
 *
 * It cannot measure its own children, so both axes are computed here and passed as
 * props. `itemSize` is the row height and `itemSecondarySize` the column width; the
 * aspect ratio is the printed card's 400×558 plus its padding on both axes.
 */
export interface GridGeometry {
  columns: number;
  itemSize: number;
  itemSecondarySize: number;
  padding: number;
}

/** Cards sit tighter on a phone, which is the one thing the old ladder got right. */
export function paddingForWidth(width: number): number {
  return width < 640 ? 4 : 8;
}

export function gridGeometry(width: number): GridGeometry {
  const padding = paddingForWidth(width);
  const columns = columnsForWidth(width);
  const ratio = (558 + padding * 2) / (400 + padding * 2);

  const itemSecondarySize = Math.max(100, width / columns);

  return {
    columns,
    itemSecondarySize,
    itemSize: Math.max(140, itemSecondarySize * ratio),
    padding,
  };
}
