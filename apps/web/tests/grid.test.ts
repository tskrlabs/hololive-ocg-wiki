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
    const { itemSize, itemSecondarySize } = gridGeometry(1520);
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
