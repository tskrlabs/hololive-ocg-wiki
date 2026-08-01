/**
 * Arrow-key movement across the card grid (#60, #48 §6).
 *
 * The grid was ~40 tab stops — measured by walking the real tab order at 1440px, where
 * reaching the footer meant tabbing through every mounted tile. It is one stop now, with
 * the arrows moving between cards, which is the standard roving-tabindex pattern.
 *
 * `targetIndex` is the whole of the movement rule and is deliberately pure: the geometry
 * it depends on (how many columns) changes with width, density and the show-original
 * toggle, so the arithmetic is worth exercising across every shape rather than at the one
 * the test harness happens to render. The parts that need a browser — scrolling an
 * unmounted tile into existence, then holding focus on it while the scroller repaints —
 * were verified in Chromium and are described in the composable.
 */

import { describe, expect, it } from "vitest";

import { targetIndex } from "../app/composables/useGridRovingFocus";

const COLUMNS = 6;
const TOTAL = 34;

describe("targetIndex (#60)", () => {
  it("moves one card horizontally", () => {
    expect(targetIndex("ArrowRight", 10, COLUMNS, TOTAL)).toBe(11);
    expect(targetIndex("ArrowLeft", 10, COLUMNS, TOTAL)).toBe(9);
  });

  it("moves one row vertically, which is one column count", () => {
    expect(targetIndex("ArrowDown", 10, COLUMNS, TOTAL)).toBe(16);
    expect(targetIndex("ArrowUp", 10, COLUMNS, TOTAL)).toBe(4);
  });

  it("follows the live column count rather than a fixed grid", () => {
    // Columns derive from a target tile width (#43), so they change with the window, the
    // density mode and the show-original toggle. A hardcoded row length would send focus
    // to the wrong card at every width but one.
    expect(targetIndex("ArrowDown", 0, 2, TOTAL)).toBe(2);
    expect(targetIndex("ArrowDown", 0, 9, TOTAL)).toBe(9);
  });

  it("clamps at the edges instead of wrapping", () => {
    // Wrapping from the last row to the first would be a surprise, not a convenience —
    // and on 2,463 cards it would scroll the whole list without being asked to.
    expect(targetIndex("ArrowLeft", 0, COLUMNS, TOTAL)).toBe(0);
    // Up from the first row clamps to the *first card*, not to the same column. Landing
    // on index 0 is the conventional behaviour and keeps focus inside the grid; the
    // alternative — refusing to move — reads as an unresponsive key.
    expect(targetIndex("ArrowUp", 3, COLUMNS, TOTAL)).toBe(0);
    expect(targetIndex("ArrowRight", TOTAL - 1, COLUMNS, TOTAL)).toBe(TOTAL - 1);
    expect(targetIndex("ArrowDown", TOTAL - 1, COLUMNS, TOTAL)).toBe(TOTAL - 1);
  });

  it("clamps a partial last row rather than overshooting the list", () => {
    // 34 cards over 6 columns leaves 4 on the last row. Down from card 30 has no card
    // below it, and must not resolve to index 36.
    expect(targetIndex("ArrowDown", 30, COLUMNS, TOTAL)).toBe(TOTAL - 1);
  });

  it("jumps to the ends", () => {
    expect(targetIndex("Home", 20, COLUMNS, TOTAL)).toBe(0);
    expect(targetIndex("End", 2, COLUMNS, TOTAL)).toBe(TOTAL - 1);
  });

  it("pages by four rows", () => {
    expect(targetIndex("PageDown", 0, COLUMNS, 2463)).toBe(24);
    expect(targetIndex("PageUp", 100, COLUMNS, 2463)).toBe(76);
    // ...and still clamps.
    expect(targetIndex("PageUp", 3, COLUMNS, TOTAL)).toBe(0);
  });

  it("ignores keys the grid does not own", () => {
    // Returning null is what lets the caller leave `preventDefault` alone — Tab above all,
    // since it is how the roving tabindex is entered and left.
    for (const key of ["Tab", "Enter", " ", "Escape", "a", "F5"]) {
      expect(targetIndex(key, 5, COLUMNS, TOTAL)).toBeNull();
    }
  });

  it("has nowhere to go in an empty result set", () => {
    // A filter matching nothing still renders a focusable grid region; movement inside it
    // must not resolve to index -1.
    expect(targetIndex("ArrowRight", 0, COLUMNS, 0)).toBeNull();
    expect(targetIndex("End", 0, COLUMNS, 0)).toBeNull();
  });

  it("handles a single card", () => {
    for (const key of ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown", "Home", "End"]) {
      expect(targetIndex(key, 0, COLUMNS, 1)).toBe(0);
    }
  });
});
