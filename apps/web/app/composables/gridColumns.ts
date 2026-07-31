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

/** The viewport below which #52's compact column bonus applies. */
export const MOBILE_GRID_MAX_WIDTH = 640;

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
  /** The text block's height, in px. Zero in compact mode. */
  textHeight: number;
}

/** Cards sit tighter on a phone, which is the one thing the old ladder got right. */
export function paddingForWidth(width: number): number {
  return width < 640 ? 4 : 8;
}

/**
 * The height the tile's text block adds below the art (#37 §5).
 *
 * ⚠️ **This is why `itemSize` takes the density and the toggle as arguments at all.**
 * `RecycleScroller` positions every row from `itemSize` and cannot measure a child, so a
 * height that does not match what the tile actually renders makes rows overlap or leaves
 * gaps — and both are silent. Turning show-original on adds a line to *every* tile, so it
 * changes the geometry of the whole grid, not the appearance of one card.
 *
 * The numbers are the rendered line boxes from the type scale commit 1 landed:
 * `text-sm` is 12/18 and `text-xs` is 11/16, plus `pt-1.5` (6px) between art and text.
 *
 * | mode                        | lines            | height |
 * |-----------------------------|------------------|--------|
 * | compact                     | —                |   0    |
 * | comfortable                 | name + number    |  40    |
 * | comfortable + show-original | + original       |  58    |
 */
export const TEXT_BLOCK_GAP = 6;
export const NAME_LINE = 18;
export const ORIGINAL_LINE = 18;
export const NUMBER_LINE = 16;

export function textBlockHeight(showsText: boolean, showsOriginal: boolean): number {
  if (!showsText) return 0;
  return TEXT_BLOCK_GAP + NAME_LINE + NUMBER_LINE + (showsOriginal ? ORIGINAL_LINE : 0);
}

/**
 * Options for a grid measurement. All optional, so the existing call shape still means
 * "comfortable, toggle off" — the state the site was in before density existed.
 */
export interface GeometryOptions {
  /** False in compact mode, where the tile is art alone. */
  showsText?: boolean;
  /** Whether the source-language name occupies its own line (#29, D14). */
  showsOriginal?: boolean;
  /**
   * Compact on a phone earns an extra column (#52): 4 cards per screen against 9 is the
   * difference between browsing and scrolling, and at 3 columns there is no text to lose.
   */
  compactMobileBonus?: boolean;
}

export function gridGeometry(width: number, options: GeometryOptions = {}): GridGeometry {
  const { showsText = true, showsOriginal = false, compactMobileBonus = false } = options;

  const padding = paddingForWidth(width);
  let columns = columnsForWidth(width);

  // #52's mobile rule. Deliberately additive and phone-only: on desktop the target-width
  // rule already gives a good count in both modes, and overriding it there would
  // reintroduce exactly the breakpoint special-casing #43 removed.
  if (compactMobileBonus && !showsText && width < MOBILE_GRID_MAX_WIDTH) {
    columns += 1;
  }

  const ratio = (558 + padding * 2) / (400 + padding * 2);
  const itemSecondarySize = Math.max(100, width / columns);
  const textHeight = textBlockHeight(showsText, showsOriginal);

  return {
    columns,
    itemSecondarySize,
    itemSize: Math.max(140, itemSecondarySize * ratio) + textHeight,
    padding,
    textHeight,
  };
}
