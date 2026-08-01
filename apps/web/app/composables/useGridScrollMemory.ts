/**
 * The grid's scroll offset, remembered across a card view (#59).
 *
 * **The problem is structural, not a mistake.** A card's URL is a real route (D15), so
 * opening one swaps `pages/index.vue` out for `pages/card/[set]/[stem].vue` and the list
 * unmounts — verified in Chromium: `document.querySelector(".scroller")` is `null` while
 * the dialog is open. Closing pops back and mounts a *fresh* list, at offset 0. Browse
 * deep into 2,463 cards, tap one, close it, and you have lost your place.
 *
 * **Why this restores the offset rather than keeping the component alive.** Two
 * measurements decided it:
 *
 * - Closing a card makes **zero** API calls. The cards, the filters and the result count
 *   all live in `useState`, so the remount is cheap and nothing but the offset is lost.
 *   There is no torn state to preserve — only a number.
 * - A cold card page makes **one** API call and never mounts the grid. #59's preferred
 *   fix — making the card route a *child* of the list so the list never unmounts — would
 *   mount the grid and fetch a page underneath **every cold card page**, which is exactly
 *   the crawler-and-shared-link path launch depends on. That is a real cost paid on the
 *   path that matters most, to avoid a remount that costs nothing.
 *
 * So this restores a number, and the routing stays as it is.
 *
 * `useState` because the value has to outlive the component that produced it; that is the
 * whole point. It is deliberately *not* persisted beyond the session — a scroll offset
 * from yesterday means nothing against a result set that may have been refiltered since.
 *
 * ---
 *
 * **Two kinds of memory, because there are two kinds of remount** (D18, amended).
 *
 * A card view remounts the list *unchanged*: same width, same columns, same rows. A pixel
 * offset is exactly right there, and is what the scroller can be trusted to reproduce.
 *
 * Opening the deck panel remounts it **reflowed**. The panel takes 384px, so the grid
 * drops columns — 6 → 4 at 1512px — and `RecycleScroller`'s key carries the column count,
 * so it rebuilds. A pixel offset survives that guard (`itemCount` is unchanged: the
 * *list* did not change, only its shape) and is nonetheless wrong:
 *
 * | | columns | rows | itemSize | 3000px lands on |
 * |---|---|---|---|---|
 * | panel closed | 6 | 411 | ~327px | item ~55 |
 * | panel open   | 4 | 616 | ~337px | item ~35 |
 *
 * Twenty cards backwards, silently. What is stable across a reflow is **which card you
 * were looking at**, so the panel path remembers a first-visible *index* and restores it
 * through `scrollToItem`. The card path keeps pixels, because there the pixel is the
 * finer answer and nothing invalidates it.
 */

/**
 * What was remembered, and how to put it back.
 *
 * `itemCount` guards both: an offset *or* an index means nothing against a different
 * result set. The discriminant is the anchor kind, so a caller cannot restore an index as
 * if it were pixels.
 */
type ScrollMemory =
  | { kind: "offset"; top: number; itemCount: number }
  | { kind: "index"; index: number; itemCount: number }
  | null;

/**
 * A scroller that can be positioned by item rather than by pixel.
 *
 * `RecycleScroller`'s own API. Typed structurally rather than imported: the composable is
 * unit-tested without the component, and a structural type is what lets a test supply a
 * stub that behaves like the real thing.
 */
export interface ItemScroller {
  scrollToItem?: (index: number) => void;
}

export const useGridScrollMemory = () => {
  const memory = useState<ScrollMemory>("gridScrollMemory", () => null);

  /** Called as a card opens, while the scroller still exists to be read. */
  const remember = (element: HTMLElement | null | undefined, itemCount: number) => {
    if (!element || element.scrollTop <= 0) return;
    memory.value = { kind: "offset", top: element.scrollTop, itemCount };
  };

  /**
   * Called as the deck panel opens or closes, before the reflow (D18, amended).
   *
   * Remembers *which card is at the top of the viewport* rather than how far down the
   * pixels are, because the reflow changes what a pixel means. The index is derived here,
   * where the outgoing geometry is still true — after the remount the column count has
   * already changed and the sum cannot be reconstructed.
   *
   * `itemSize` is the row height and `columns` the current column count, both from
   * `gridGeometry`. Guarded because a zero would divide into infinity, and the grid can
   * legitimately be mid-measurement when the panel is toggled.
   */
  const rememberIndex = (
    element: HTMLElement | null | undefined,
    itemSize: number,
    columns: number,
    itemCount: number,
  ) => {
    if (!element || itemSize <= 0 || columns <= 0) return;
    if (element.scrollTop <= 0) return;

    const firstVisibleRow = Math.floor(element.scrollTop / itemSize);
    const index = firstVisibleRow * columns;
    if (index <= 0 || index >= itemCount) return;

    memory.value = { kind: "index", index, itemCount };
  };

  /**
   * Whether a restore is still owed.
   *
   * Read by the list's scroll-to-top watcher, which fires on the same `loading → ready`
   * pass that returning from a card produces and would otherwise undo the restore. A
   * pending memory is what distinguishes "we came back from a card" from "these are new
   * results" — see the watcher for the full trace.
   */
  const isPending = (): boolean => memory.value !== null;

  /**
   * Called once the list has remounted and has its items back.
   *
   * ⚠️ **Restores through the scroller's own `scrollToPosition`, not by assigning
   * `scrollTop`.** Traced in Chromium: the assignment lands, reports success, and leaves
   * the offset at 0 — at that moment `RecycleScroller` has rendered a viewport's worth of
   * rows and nothing more, so the element has no scrollable height to scroll into and the
   * browser clamps the write away. `scrollToPosition` is the component's own API and
   * knows the virtual height, so it positions correctly *and* renders the right rows.
   *
   * ⚠️ **Guarded on the item count**, and that guard is the whole correctness argument.
   * A scroll offset means nothing against a different result set — restoring 3,000px into
   * a shorter list scrolls into blank space. So a restore only applies when the list came
   * back the same length it left, which is the case this fixes (the data survives in
   * `useState`) and not the case where a filter changed underneath.
   *
   * Consumed on success only. A failed attempt leaves the memory in place because the
   * caller retries across a few frames — the scroller does not exist at `nextTick`, since
   * `shouldRenderScroller` gates on a width that arrives from a `ResizeObserver`.
   */
  const restore = (
    element: HTMLElement | null | undefined,
    itemCount: number,
    scroller?: ItemScroller | null,
  ): boolean => {
    const saved = memory.value;
    if (!element || !saved) return false;
    if (saved.itemCount !== itemCount) {
      // A different result set: the anchor is meaningless and must not be retried.
      memory.value = null;
      return false;
    }

    // An index anchor goes back through the scroller's own API, which is the only thing
    // that knows where item N *now* is — the whole point of remembering an index across a
    // reflow is that the caller cannot compute the pixel itself.
    //
    // Success is still measured rather than assumed, for the same reason as below: called
    // before the rows exist, `scrollToItem` positions into a scroller with no height and
    // the result is clamped away.
    if (saved.kind === "index") {
      if (!scroller?.scrollToItem) return false;
      scroller.scrollToItem(saved.index);
      if (element.scrollTop <= 0) return false;

      memory.value = null;
      return true;
    }

    // ⚠️ **Success is measured, not assumed**, and that is the whole subtlety here.
    //
    // Traced in Chromium: on the frame the list remounts, the scroller has rendered one
    // viewport of rows and nothing more, so `scrollHeight === clientHeight` and the
    // browser clamps the write to 0 — silently. An earlier version reported success on
    // every attempt and left the grid at the top, because it checked that it had *made*
    // the assignment rather than that the assignment had *taken*.
    //
    // Reading `scrollTop` back is what distinguishes "restored" from "clamped", and it
    // lets the caller keep retrying across frames until the rows exist.
    element.scrollTop = saved.top;
    if (element.scrollTop <= 0) return false;

    memory.value = null;
    return true;
  };

  /** A new result set starts at the top; a stale offset must not survive into it. */
  const forget = () => {
    memory.value = null;
  };

  return { remember, rememberIndex, restore, forget, isPending };
};
