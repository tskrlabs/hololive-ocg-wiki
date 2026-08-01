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
 */

/** Scroll offsets are only meaningful against the same result set. */
type ScrollMemory = { top: number; itemCount: number } | null;

export const useGridScrollMemory = () => {
  const memory = useState<ScrollMemory>("gridScrollMemory", () => null);

  /** Called as a card opens, while the scroller still exists to be read. */
  const remember = (element: HTMLElement | null | undefined, itemCount: number) => {
    if (!element || element.scrollTop <= 0) return;
    memory.value = { top: element.scrollTop, itemCount };
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
  const restore = (element: HTMLElement | null | undefined, itemCount: number): boolean => {
    const saved = memory.value;
    if (!element || !saved) return false;
    if (saved.itemCount !== itemCount) {
      // A different result set: the offset is meaningless and must not be retried.
      memory.value = null;
      return false;
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

  return { remember, restore, forget, isPending };
};
