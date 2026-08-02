/**
 * The card grid is one tab stop, and the arrow keys move within it (#60, #48 §6).
 *
 * **The problem, measured before writing this.** Every visible tile was its own tab stop,
 * so the real tab order at 1440px ran: five header controls, the search box, thirteen
 * filter buttons, one button per colour — and then *forty cards*. Tabbing past the grid
 * to reach the footer was not realistically possible, and on 2,463 cards the count is
 * bounded only by what the scroller happens to have mounted.
 *
 * The fix is the standard roving-tabindex pattern, which browsers and screen readers both
 * understand: exactly one tile carries `tabindex="0"` and the rest carry `-1`, so Tab
 * enters and leaves the grid once, and the arrows move between cards.
 *
 * **What makes it harder here than the textbook version** is virtualisation. The tile an
 * arrow press targets **may not exist in the DOM** — `RecycleScroller` mounts roughly
 * forty of 2,463 — so moving focus is not `nextTile.focus()`. It is: record the index,
 * ask the scroller to bring it into view, wait for the row to mount, *then* focus it.
 * That is why this owns an index rather than an element.
 *
 * Deliberately **not** part of Phase 8 commit 13, which fixed focus being *lost*. This
 * changes how the grid is operated, and mixing the two would have made both unreviewable.
 */

/** Where the roving tabindex currently sits. Survives the list's remount (#59, D15). */
const STATE_KEY = "gridRovingIndex";

/** How a key maps to a movement, given the live column count. */
export function targetIndex(
  key: string,
  current: number,
  columns: number,
  total: number,
): number | null {
  if (total <= 0) return null;

  const clamp = (value: number) => Math.max(0, Math.min(value, total - 1));

  switch (key) {
    case "ArrowRight":
      return clamp(current + 1);
    case "ArrowLeft":
      return clamp(current - 1);
    case "ArrowDown":
      // Clamped rather than wrapped: on the last row there is nothing below, and jumping
      // to the start of the list would be a surprise rather than a convenience.
      return clamp(current + columns);
    case "ArrowUp":
      return clamp(current - columns);
    case "Home":
      return 0;
    case "End":
      return total - 1;
    case "PageDown":
      // A screen is four rows at the geometry `gridColumns.ts` produces.
      return clamp(current + columns * 4);
    case "PageUp":
      return clamp(current - columns * 4);
    default:
      return null;
  }
}

export const useGridRovingFocus = () => {
  /**
   * The index that holds `tabindex="0"`.
   *
   * `useState` so it survives the list unmounting when a card URL is pushed (D15) — the
   * same reason `useGridScrollMemory` does. Returning from a card should put Tab back
   * where it was, not at card zero.
   */
  const activeIndex = useState<number>(STATE_KEY, () => 0);

  /**
   * Whether a roving move is currently scrolling a tile into existence.
   *
   * Read by `useScrollerFocus`, whose job is to catch focus that recycling dropped — a
   * roving move looks exactly like that from the outside, and its recovery would land on
   * the nearest visible tile instead of the requested one.
   */
  const moving = useState<boolean>("gridRovingMoving", () => false);

  /** Whether a tile should be tabbable. Exactly one is, at any time. */
  const isTabbable = (index: number): boolean => index === activeIndex.value;

  /**
   * Move focus to `index`, scrolling it into existence first if need be.
   *
   * The wait is the whole difficulty. `scrollToItem` only schedules a scroll; the row is
   * mounted on a later frame, and asking for `querySelector` immediately finds nothing.
   * So this polls for the tile across a few frames and gives up rather than looping — a
   * target that never appears means the list changed underneath, and stealing focus at
   * that point would be worse than leaving it.
   */
  const focusIndex = (
    index: number,
    scroller: { scrollToItem?: (index: number) => void } | null | undefined,
  ) => {
    activeIndex.value = index;
    // Tells `useScrollerFocus` to stand down while this move is in flight. Focus passes
    // through `<body>` during the scroll, and its recovery would otherwise catch it and
    // drop it on the nearest visible tile — six cards from the requested one, measured.
    moving.value = true;
    scroller?.scrollToItem?.(index);

    // ⚠️ **Focus after the scroll settles, and hold it there.**
    //
    // Traced in Chromium on an `End` press: the target tile *is* focused correctly within
    // ~20ms, and then blurred to `<body>` at ~320ms — because `scrollToItem` is still
    // animating, and the row focused early is recycled out from under focus when the
    // scroller finally repaints at the destination.
    //
    // So this does not stop at the first success. It keeps checking until focus has been
    // on the right tile across consecutive frames, re-focusing whenever recycling takes it
    // away. It also re-queries every time rather than holding the element: the node is
    // recycled, so a reference kept across frames may belong to a different card.
    // ⚠️ **Hold focus for a fixed window, not until it looks settled.**
    //
    // Traced in Chromium on `End`: the target tile is focused correctly within ~20ms, then
    // blurred to `<body>` at ~320ms — while still in the DOM. `scrollToItem` is animating,
    // and the scroller's own repaint at the destination drops focus. An earlier version
    // stopped as soon as focus had held for two frames, which is satisfied long before
    // that blur ever happens, so it had already given up by the time it mattered.
    //
    // So the window is time-based and generous: keep re-asserting focus for ~600ms,
    // whenever anything takes it away. It re-queries every frame rather than holding the
    // element, because the node is recycled and a stale reference may belong to a
    // different card.
    const deadline = 600;
    let elapsed = 0;
    let previous: number | null = null;

    const settle = (timestamp: number) => {
      if (previous !== null) elapsed += timestamp - previous;
      previous = timestamp;

      const tile = document.querySelector<HTMLElement>(
        `.scroller [data-card-index="${index}"]`,
      );
      // `preventScroll`: `scrollToItem` owns the scroll position, and a second scroll from
      // the focus call fights it.
      if (tile && document.activeElement !== tile) tile.focus({ preventScroll: true });

      if (elapsed >= deadline) {
        moving.value = false;
        return;
      }
      requestAnimationFrame(settle);
    };
    requestAnimationFrame(settle);
  };

  /**
   * Keep the active index inside the list.
   *
   * A filter that shrinks the results can leave it past the end, which would make *no*
   * tile tabbable — the grid would silently drop out of the tab order entirely.
   */
  const clampTo = (total: number) => {
    if (total <= 0) {
      activeIndex.value = 0;
      return;
    }
    if (activeIndex.value > total - 1) activeIndex.value = total - 1;
  };

  return { activeIndex, isTabbable, focusIndex, clampTo };
};
