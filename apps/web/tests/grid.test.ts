/**
 * The grid's column rule (#43).
 *
 * The bug this replaces was **non-monotonicity**, and that is not a property any single
 * width can show: every individual row of the old breakpoint ladder looked reasonable,
 * and only the comparison between 1440px and 1536px revealed that widening the window
 * made the cards smaller. So these sweep the whole width range and assert the shape of
 * the curve rather than checking a handful of examples.
 *
 * The old ladder fails the first two tests here at three separate steps.
 */

import { describe, expect, it } from "vitest";

import {
  columnsForWidth,
  gridGeometry,
  MAX_TILE,
  MIN_COLUMNS,
  MIN_TILE,
  TARGET_TILE,
  textBlockHeight,
} from "../app/composables/gridColumns";

/** Every width a real viewport could plausibly report, phone to 4K. */
const WIDTHS = Array.from({ length: 3841 - 320 }, (_, i) => 320 + i);

/**
 * The rule this replaces, kept verbatim so the tests below can show they discriminate.
 *
 * A property test that no plausible wrong implementation fails is not a regression net.
 * Each assertion here is run against this too, and must fail.
 */
function oldLadder(width: number): number {
  if (width < 640) return 3;
  if (width < 768) return 4;
  if (width < 1024) return 5;
  if (width < 1280) return 6;
  if (width < 1536) return 8;
  if (width < 2000) return 10;
  return 12;
}

/** The smallest tile each column count produces across the sweep. */
function tileFloors(rule: (width: number) => number): Map<number, number> {
  const floors = new Map<number, number>();
  for (const width of WIDTHS) {
    const columns = rule(width);
    floors.set(columns, Math.min(floors.get(columns) ?? Infinity, width / columns));
  }
  return floors;
}

describe("the column count", () => {
  it("never decreases as the width grows", () => {
    let previous = 0;
    for (const width of WIDTHS) {
      const columns = columnsForWidth(width);
      expect(
        columns,
        `columns fell from ${previous} to ${columns} at ${width}px`,
      ).toBeGreaterThanOrEqual(previous);
      previous = columns;
    }
  });

  it("adds at most one column at a time", () => {
    // The old ladder added *two* at each rung, which is precisely why the tile size
    // dropped: two extra columns outpace the width gained between breakpoints.
    let previous = columnsForWidth(WIDTHS[0]!);
    for (const width of WIDTHS) {
      const columns = columnsForWidth(width);
      expect(columns - previous, `jumped by more than one at ${width}px`).toBeLessThanOrEqual(1);
      previous = columns;
    }
  });

  it("is at least two, whatever the width", () => {
    for (const width of [0, 1, 50, 100, 320]) {
      expect(columnsForWidth(width)).toBeGreaterThanOrEqual(MIN_COLUMNS);
    }
  });

  it("treats a missing or nonsensical width as the narrowest grid", () => {
    // `contentRect.width` is 0 before layout and NaN if the observer misfires; neither
    // should produce a division by zero or an infinite column count.
    for (const width of [0, -100, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(columnsForWidth(width)).toBe(MIN_COLUMNS);
    }
  });
});

describe("the tile size", () => {
  it("has a floor that rises with the column count — the bug itself", () => {
    // The precise statement of "widening the window makes the cards smaller".
    //
    // Note what is *not* asserted: that the tile never shrinks between two adjacent
    // widths. That is unachievable for any integer-column grid — crossing into another
    // column always shrinks the tile, and the rule proposed in #43 does it too, going
    // 210px at 1280 to 203px at 1440 to 190px at 1536. "Monotonic" in the issue means
    // the count and the band, not the tile.
    //
    // What separates a good rule from the old ladder is the *envelope*: the smallest
    // tile each column count ever produces should not fall as columns are added. The
    // old ladder breaks it three times — 4→5 columns drops the floor from 160px to
    // 154px, 6→8 from 171px to 160px, 8→10 from 160px to 154px — because each rung
    // added two columns at once and outpaced the width gained.
    const regressions = (rule: (width: number) => number) => {
      const floors = tileFloors(rule);
      const counts = [...floors.keys()].sort((a, b) => a - b);
      const found: string[] = [];
      for (let i = 1; i < counts.length; i++) {
        const previous = floors.get(counts[i - 1]!)!;
        const current = floors.get(counts[i]!)!;
        if (current < previous - 0.001) {
          found.push(
            `${counts[i - 1]}→${counts[i]} columns: ` +
              `floor ${previous.toFixed(0)}px → ${current.toFixed(0)}px`,
          );
        }
      }
      return found;
    };

    expect(regressions(columnsForWidth)).toEqual([]);
    // And the assertion is not vacuous — the rule this replaces fails it three times.
    expect(regressions(oldLadder)).toHaveLength(3);
  });

  it("stays inside the readable band at every width", () => {
    // The old ladder leaves it for 90 widths, bottoming out at 107px — a card too small
    // to read on the phone widths where it happens.
    //
    // Below 360px the device itself is narrower than two readable tiles, so the floor
    // yields there rather than dropping to a single column.
    const outside = (rule: (width: number) => number) =>
      WIDTHS.filter((w) => w >= 360).filter((w) => {
        const tile = w / rule(w);
        return tile < MIN_TILE || tile > MAX_TILE;
      });

    expect(outside(columnsForWidth).map((w) => `${w}px`)).toEqual([]);
    expect(outside(oldLadder).length).toBeGreaterThan(0);
  });

  it("hits the target exactly when the width is a multiple of it", () => {
    // The sanity check on the rule's intent: nothing about the band should push the
    // count off the target when the target divides the width evenly.
    for (const columns of [3, 5, 8, 10, 13]) {
      expect(columnsForWidth(TARGET_TILE * columns)).toBe(columns);
    }
  });

  it("matches the counts measured in the issue", () => {
    // Content width is the viewport less the scroller's own 8px padding either side.
    const measured: [number, number][] = [
      [1280, 6],
      [1440, 7],
      [1536, 8],
      [1920, 10],
      [2560, 13],
    ];
    for (const [viewport, columns] of measured) {
      expect(columnsForWidth(viewport - 16), `${viewport}px viewport`).toBe(columns);
    }
  });
});

describe("the scroller geometry", () => {
  it("keeps the card's aspect ratio on both axes", () => {
    // RecycleScroller cannot measure its children, so a wrong ratio here shows up as
    // rows that overlap or as gaps between them.
    //
    // Compact mode is the pure-art case, so this is the ratio with no text block; the
    // comfortable cases add a fixed height on top and are pinned separately below.
    const { itemSize, itemSecondarySize } = gridGeometry(1520, { showsText: false });
    expect(itemSize / itemSecondarySize).toBeCloseTo((558 + 16) / (400 + 16), 2);
  });

  it("tightens the padding on a phone", () => {
    expect(gridGeometry(400).padding).toBe(4);
    expect(gridGeometry(1024).padding).toBe(8);
  });

  it("never returns a zero dimension, which would hide the list", () => {
    // `shouldRenderScroller` gates on all three being positive; a zero would silently
    // fall back to the static grid.
    for (const width of [0, 1, 320, 1920, 3840]) {
      const geometry = gridGeometry(width);
      expect(geometry.columns).toBeGreaterThan(0);
      expect(geometry.itemSize).toBeGreaterThan(0);
      expect(geometry.itemSecondarySize).toBeGreaterThan(0);
    }
  });
});

/**
 * The density model (#37, #52, D13, D14).
 *
 * The failure mode here is specific and silent: `RecycleScroller` positions every row
 * from `itemSize`, so if the number does not match what the tile actually renders, rows
 * overlap. Nothing throws and nothing logs — you get a grid that looks subtly wrong. That
 * makes the *arithmetic* worth pinning even though the bug appears visually.
 */
describe("the text block", () => {
  it("adds nothing at all in compact mode", () => {
    // Compact is art alone, so it must reproduce the pre-density geometry exactly.
    expect(textBlockHeight(false, false)).toBe(0);
    // ...even with the toggle on: there is no name line to add a source name beneath.
    expect(textBlockHeight(false, true)).toBe(0);
  });

  it("grows by exactly one line when show-original is on", () => {
    // #37 §5's measurement: the original line adds 17-18px per item, which is why the
    // toggle changes the geometry of every tile rather than the look of one card.
    const plain = textBlockHeight(true, false);
    const withOriginal = textBlockHeight(true, true);

    expect(plain).toBe(40);
    expect(withOriginal).toBe(58);
    expect(withOriginal - plain).toBe(18);
  });

  it("is what separates the three item heights", () => {
    const art = gridGeometry(1520, { showsText: false }).itemSize;
    const comfortable = gridGeometry(1520, { showsText: true }).itemSize;
    const withOriginal = gridGeometry(1520, {
      showsText: true,
      showsOriginal: true,
    }).itemSize;

    expect(comfortable).toBe(art + 40);
    expect(withOriginal).toBe(art + 58);
    // Strictly ordered — a mode that showed *more* must never be *shorter*.
    expect(art).toBeLessThan(comfortable);
    expect(comfortable).toBeLessThan(withOriginal);
  });

  it("defaults to comfortable with the toggle off", () => {
    // The call shape that existed before density did must still mean what it meant:
    // names shown, no source line.
    expect(gridGeometry(1520).itemSize).toBe(
      gridGeometry(1520, { showsText: true, showsOriginal: false }).itemSize,
    );
  });
});

describe("compact's extra column on a phone (#52)", () => {
  it("gives 3 columns at 375px where comfortable gives 2", () => {
    // The measurement that moved this from a preference to a necessity: 4 cards per
    // screen against 9 at 375×812.
    const comfortable = gridGeometry(375, { showsText: true, compactMobileBonus: true });
    const compact = gridGeometry(375, { showsText: false, compactMobileBonus: true });

    expect(comfortable.columns).toBe(2);
    expect(compact.columns).toBe(3);
  });

  it("does not touch the desktop count in either mode", () => {
    // The bonus is phone-only on purpose. Applying it at every width would reintroduce
    // exactly the breakpoint special-casing #43 removed.
    for (const width of [640, 768, 1280, 1512, 1920, 2560]) {
      const comfortable = gridGeometry(width, { showsText: true, compactMobileBonus: true });
      const compact = gridGeometry(width, { showsText: false, compactMobileBonus: true });

      expect(compact.columns, `${width}px`).toBe(comfortable.columns);
      expect(compact.columns, `${width}px`).toBe(columnsForWidth(width));
    }
  });

  it("is opt-in, so the plain column rule is unchanged", () => {
    // Without the flag, compact must not gain a column even on a phone — the rule stays
    // a pure function of width, which is what the monotonicity sweeps above assert.
    expect(gridGeometry(375, { showsText: false }).columns).toBe(columnsForWidth(375));
  });
});

/**
 * The grid, with the deck panel pushed beside it (ADR 0009 D18, amended).
 *
 * The panel takes a fixed 384px out of the row the filter rail and the grid already
 * share, so from `xl` the grid's width is `viewport - 280 - 384`. Whether that is a
 * *usable* grid is arithmetic, and it is the arithmetic that chose 1280 as the threshold
 * — below it, the rail plus the panel leave less than three columns' worth of room.
 *
 * These sweep, like everything else in this file, because the property is about the whole
 * range rather than a chosen width: the point of pushing rather than overlaying is that
 * *no* width above the threshold produces a grid outside the band. A handful of examples
 * cannot say that, and the failure it guards against — a tile squeezed under `MIN_TILE` —
 * is silent on screen.
 */
describe("the grid beside a pushed deck panel (D18)", () => {
  /** The panel's fixed width. Stated once; `useDeckPanel` documents why it is fixed. */
  const PANEL = 384;
  /** The filter rail, permanent from `lg` and therefore always present above `xl`. */
  const RAIL = 280;
  /** The threshold `useDeckPanel` switches on. */
  const PUSH_MIN_WIDTH = 1280;

  /** What the grid actually gets once both chrome columns have taken their share. */
  const gridWidth = (viewport: number) => viewport - RAIL - PANEL;

  /** Every width at or above the threshold, to 4K. */
  const PUSHED_WIDTHS = Array.from(
    { length: 3841 - PUSH_MIN_WIDTH },
    (_, i) => PUSH_MIN_WIDTH + i,
  );

  it("keeps every tile inside the 150–240px band", () => {
    for (const viewport of PUSHED_WIDTHS) {
      const width = gridWidth(viewport);
      const tile = width / columnsForWidth(width);

      expect(tile, `${viewport}px viewport`).toBeGreaterThanOrEqual(MIN_TILE);
      expect(tile, `${viewport}px viewport`).toBeLessThanOrEqual(MAX_TILE);
    }
  });

  it("keeps at least three columns, so the grid still reads as one", () => {
    // Two columns is `MIN_COLUMNS` — the point at which `columnsForWidth` stops being
    // able to protect the tile size at all, because it has nothing left to give back.
    for (const viewport of PUSHED_WIDTHS) {
      expect(columnsForWidth(gridWidth(viewport)), `${viewport}px viewport`)
        .toBeGreaterThanOrEqual(3);
    }
  });

  /**
   * The discriminator, in the spirit of `oldLadder` above — and the measurement that
   * says how much slack the threshold has.
   *
   * A threshold test that a *wrong* threshold also passes is not a regression net. `lg`
   * was the obvious candidate: it is where the rail appears, and it is what the original
   * D18 switched on. It fails, but **not everywhere in the band**, and the shape of the
   * failure is the useful part:
   *
   * | viewport | grid | columns | tile |
   * |----------|------|---------|------|
   * | 1024     | 360  | 2       | 180px |
   * | 1144     | 480  | 2       | 240px ← last two-column width |
   * | 1145     | 481  | 3       | 160px ← three columns, barely |
   * | 1280     | 616  | 3       | 205px |
   *
   * So the hard floor is **1145**, in one contiguous run, and `xl` sits 135px above it.
   * That gap is deliberate rather than incidental: 1145 is not a breakpoint any stylesheet
   * has, and a 160px tile is 10px off `MIN_TILE` — a threshold placed there would be one
   * padding change away from breaking. `xl` is the nearest real breakpoint that clears it
   * with room, which is what makes it a decision instead of a rounding.
   */
  it("has a hard floor at 1145px, and `xl` clears it with room", () => {
    const failures = [];
    for (let viewport = 1024; viewport < PUSH_MIN_WIDTH; viewport++) {
      const width = gridWidth(viewport);
      const columns = columnsForWidth(width);
      const tile = width / columns;
      if (columns < 3 || tile < MIN_TILE || tile > MAX_TILE) failures.push(viewport);
    }

    // One contiguous run from the bottom of the band — not a scattering, which would mean
    // the rule was non-monotonic and no single threshold could exist.
    expect(failures[0]).toBe(1024);
    expect(failures.at(-1)).toBe(1144);
    expect(failures.length).toBe(1145 - 1024);

    // And `lg` really is inside it, so the original constant was not merely untidy.
    expect(failures).toContain(1024);
  });

  it("costs columns rather than tile size, which is #43's rule paying off", () => {
    // The whole case for pushing: the cards you can still see are the same size as
    // before. Measured at the widths the ADR quotes.
    for (const viewport of [1280, 1512, 1920]) {
      const browsing = gridGeometry(viewport - RAIL);
      const building = gridGeometry(gridWidth(viewport));

      expect(building.columns, `${viewport}px`).toBeLessThan(browsing.columns);
      // Within 40px of the browsing tile — the tile is preserved, the count is not.
      expect(
        Math.abs(building.itemSecondarySize - browsing.itemSecondarySize),
        `${viewport}px`,
      ).toBeLessThan(40);
    }
  });
});


/**
 * The scrollbar's 10px, and what it may and may not do to the grid.
 *
 * The card grid's scroller is a native `overflow-y-auto`, and its scrollbar is styled as
 * a **classic gutter** rather than an overlay (`tailwind.css`). A classic
 * `::-webkit-scrollbar` is excluded from `ResizeObserver`'s `contentRect`, so the width
 * `columnsForWidth` measures is 10px short of the region — which makes a CSS choice an
 * input to the column rule, and that is worth a test rather than a comment.
 *
 * What it *is* allowed to do is move a threshold: a width already within 10px of a column
 * boundary drops a column, which is the rule working correctly on a narrower box. What it
 * must never do is push a tile outside the band, because that is the property #43 exists
 * to guarantee and the one a user would actually see.
 */
describe("the scrollbar gutter's effect on the grid", () => {
  /** The gutter set in `tailwind.css`. */
  const SCROLLBAR = 10;
  const RAIL = 280;
  const PANEL = 384;

  it("never pushes a tile outside the 150–240px band, at any real width", () => {
    // Every configuration the app actually renders above the push threshold: rail always
    // present from `lg`, panel present only when open.
    for (let viewport = 1280; viewport <= 3840; viewport++) {
      for (const panel of [0, PANEL]) {
        const width = viewport - RAIL - panel - SCROLLBAR;
        const tile = width / columnsForWidth(width);

        expect(tile, `${viewport}px, panel ${panel}`).toBeGreaterThanOrEqual(MIN_TILE);
        expect(tile, `${viewport}px, panel ${panel}`).toBeLessThanOrEqual(MAX_TILE);
      }
    }
  });

  it("costs at most one column, never more", () => {
    // A 10px loss is smaller than any column's worth of width, so it can only ever move a
    // width across one threshold. More than one would mean the rule was not monotonic.
    for (let viewport = 320; viewport <= 3840; viewport++) {
      for (const rail of [0, RAIL]) {
        for (const panel of [0, PANEL]) {
          const width = viewport - rail - panel;
          if (width < 200) continue;

          const delta = Math.abs(columnsForWidth(width) - columnsForWidth(width - SCROLLBAR));
          expect(delta, `${viewport}px`).toBeLessThanOrEqual(1);
        }
      }
    }
  });

  it("leaves the widths the ADR quotes unchanged", () => {
    // The three worked examples in D18's table. If these move, the ADR is wrong and the
    // table has to be rewritten — which is exactly the kind of drift a test should catch.
    const expected: Record<number, number> = { 1280: 3, 1512: 4, 1920: 6 };

    for (const [viewport, columns] of Object.entries(expected)) {
      const width = Number(viewport) - RAIL - PANEL - SCROLLBAR;
      expect(columnsForWidth(width), `${viewport}px with the panel open`).toBe(columns);
    }
  });
});
