/**
 * @vitest-environment happy-dom
 *
 * The grid's scroll offset survives a card view (#59).
 *
 * Opening a card is a route change (D15), so the list unmounts and comes back fresh at
 * offset 0 — verified in Chromium, where `.scroller` is `null` while the dialog is open.
 * Browse deep into 2,463 cards, tap one, close it, and you have lost your place.
 *
 * These cover the composable's rules directly rather than through a mounted list, because
 * the bug is about *when* an offset may be applied and happy-dom has no layout to make a
 * mounted assertion mean anything. What is pinned is every decision that took a browser
 * to find:
 *
 * - a write can be **silently clamped to 0** when the scroller has not laid out yet, so
 *   success is measured by reading `scrollTop` back rather than by having assigned it
 * - a restore against a *different* result set must not happen at all
 * - `isPending()` is what tells the list's scroll-to-top watcher that a `loading → ready`
 *   pass is a return from a card rather than a new result set
 */

import { describe, expect, it, beforeEach } from "vitest";
import { ref } from "vue";

const stateStore = new Map<string, ReturnType<typeof ref>>();

Object.assign(globalThis, {
  ref,
  useState: <T>(key: string, init?: () => T) => {
    if (!stateStore.has(key)) stateStore.set(key, ref(init ? init() : null));
    return stateStore.get(key)!;
  },
});

const { useGridScrollMemory } = await import("../app/composables/useGridScrollMemory");

/**
 * An element that scrolls only as far as its content allows — which is the behaviour the
 * real bug turned on. happy-dom lets `scrollTop` be set to anything, so a naive stub
 * would make the clamped case untestable and the test would pass against the bug.
 */
function scrollable(maxScroll: number) {
  let top = 0;
  return {
    get scrollTop() {
      return top;
    },
    set scrollTop(value: number) {
      top = Math.max(0, Math.min(value, maxScroll));
    },
  } as unknown as HTMLElement;
}

describe("the grid's scroll offset across a card view (#59)", () => {
  beforeEach(() => stateStore.clear());

  it("restores the offset when the list comes back unchanged", () => {
    const memory = useGridScrollMemory();
    const before = scrollable(3000);
    before.scrollTop = 1073;

    memory.remember(before, 34);

    const after = scrollable(3000);
    expect(memory.restore(after, 34)).toBe(true);
    expect(after.scrollTop).toBe(1073);
  });

  it("reports failure when the write is clamped, so the caller can retry", () => {
    const memory = useGridScrollMemory();
    const before = scrollable(3000);
    before.scrollTop = 1073;
    memory.remember(before, 34);

    // A scroller mid-mount: one viewport of rows rendered, nothing to scroll into yet.
    const notReady = scrollable(0);
    expect(memory.restore(notReady, 34)).toBe(false);

    // ...and the memory survives, because the retry is the whole point.
    expect(memory.isPending()).toBe(true);

    const ready = scrollable(3000);
    expect(memory.restore(ready, 34)).toBe(true);
    expect(ready.scrollTop).toBe(1073);
  });

  it("refuses to restore into a different result set", () => {
    const memory = useGridScrollMemory();
    const before = scrollable(3000);
    before.scrollTop = 1073;
    memory.remember(before, 34);

    // A filter changed while the card was open: 1073px means nothing against 5 cards.
    const after = scrollable(3000);
    expect(memory.restore(after, 5)).toBe(false);
    expect(after.scrollTop).toBe(0);
    // Not retryable either — this is a definite no, not a "not yet".
    expect(memory.isPending()).toBe(false);
  });

  it("remembers nothing when the grid was already at the top", () => {
    const memory = useGridScrollMemory();
    memory.remember(scrollable(3000), 34);
    // Nothing to restore, and `isPending()` staying false is what lets the normal
    // scroll-to-top run on the next filter change.
    expect(memory.isPending()).toBe(false);
  });

  it("is consumed once, so a later remount does not re-apply it", () => {
    const memory = useGridScrollMemory();
    const before = scrollable(3000);
    before.scrollTop = 900;
    memory.remember(before, 34);

    const first = scrollable(3000);
    expect(memory.restore(first, 34)).toBe(true);

    const second = scrollable(3000);
    expect(memory.restore(second, 34)).toBe(false);
    expect(second.scrollTop).toBe(0);
  });

  it("forgets on demand, which is how a filter change drops a stale offset", () => {
    const memory = useGridScrollMemory();
    const before = scrollable(3000);
    before.scrollTop = 900;
    memory.remember(before, 34);
    expect(memory.isPending()).toBe(true);

    memory.forget();

    expect(memory.isPending()).toBe(false);
    const after = scrollable(3000);
    expect(memory.restore(after, 34)).toBe(false);
  });
});

/**
 * The same memory, anchored by **item index**, across the deck panel's reflow
 * (ADR 0009 D18, amended).
 *
 * A card view remounts the list unchanged, so a pixel offset is the right thing to keep —
 * that is everything above. Opening the deck panel remounts it *reflowed*: the panel takes
 * 384px, the grid drops columns, and `RecycleScroller` rebuilds because the column count
 * is in its key.
 *
 * The failure that motivates a second anchor kind is **silent and passes every existing
 * guard**. `itemCount` is unchanged — the result set did not change, only its shape — so
 * a pixel restore is judged valid and lands somewhere else entirely:
 *
 * | | columns | itemSize | 3000px is |
 * |---|---|---|---|
 * | panel closed | 6 | 327px | item ~54 |
 * | panel open   | 4 | 337px | item ~32 |
 *
 * So these pin the property that a pixel cannot have: *the same card stays put*.
 */
describe("the grid's scroll anchor across the deck panel's reflow (D18)", () => {
  beforeEach(() => stateStore.clear());

  /**
   * A scroller stub that knows its own geometry.
   *
   * `scrollToItem` is `RecycleScroller`'s API and is the only thing that can put an index
   * back, because the pixel it maps to depends on the *new* column count. Modelling that
   * arithmetic here is what makes the round-trip assertion mean anything.
   */
  function grid(columns: number, itemSize: number, itemCount: number) {
    const rows = Math.ceil(itemCount / columns);
    const element = scrollable(Math.max(0, rows * itemSize - 800));
    return {
      element,
      columns,
      itemSize,
      scrollToItem(index: number) {
        element.scrollTop = Math.floor(index / columns) * itemSize;
      },
    };
  }

  it("puts the same card back after the columns change", () => {
    const memory = useGridScrollMemory();
    const before = grid(6, 327, 2463);
    before.element.scrollTop = 3000;

    // Captured while the outgoing geometry is still true — after the reflow the column
    // count has already changed and the index cannot be recovered.
    memory.rememberIndex(before.element, before.itemSize, before.columns, 2463);

    // The panel opens: 6 columns become 4, and the scroller remounts at the top.
    const after = grid(4, 337, 2463);
    expect(memory.restore(after.element, 2463, after)).toBe(true);

    // The card that was in the top row is in the top row.
    //
    // ⚠️ Not "is the *first* item" — that is unachievable and asking for it would be a
    // wrong test. Item 54 begins a row at 6 columns but sits mid-row at 4 (52, 53, 54,
    // 55), and the scroller can only align to a row. What is guaranteed, and what the
    // user perceives, is that the card they were looking at is still at the top of the
    // viewport rather than twenty rows away.
    const rememberedCard = Math.floor(3000 / before.itemSize) * before.columns;
    const firstVisibleAfter =
      Math.floor(after.element.scrollTop / after.itemSize) * after.columns;

    expect(firstVisibleAfter).toBeLessThanOrEqual(rememberedCard);
    expect(firstVisibleAfter + after.columns).toBeGreaterThan(rememberedCard);
  });

  it("is what a pixel offset would have got wrong", () => {
    // The discriminator. Restoring the *pixels* passes `itemCount` and still moves the
    // user ~22 cards backwards — which is why the guard could not simply be tightened.
    const before = grid(6, 327, 2463);
    const after = grid(4, 337, 2463);

    const intended = Math.floor(3000 / before.itemSize) * before.columns;
    const whatPixelsWouldGive = Math.floor(3000 / after.itemSize) * after.columns;

    expect(whatPixelsWouldGive).not.toBe(intended);
    expect(whatPixelsWouldGive).toBeLessThan(intended);
  });

  it("retries rather than failing while the scroller has no rows yet", () => {
    const memory = useGridScrollMemory();
    const before = grid(6, 327, 2463);
    before.element.scrollTop = 3000;
    memory.rememberIndex(before.element, before.itemSize, before.columns, 2463);

    // Mid-mount: one viewport of rows, nothing to scroll into, so the write is clamped.
    const notReady = grid(4, 337, 2463);
    notReady.element = scrollable(0);
    expect(memory.restore(notReady.element, 2463, notReady)).toBe(false);
    expect(memory.isPending()).toBe(true);

    const ready = grid(4, 337, 2463);
    expect(memory.restore(ready.element, 2463, ready)).toBe(true);
  });

  it("refuses an index against a different result set", () => {
    const memory = useGridScrollMemory();
    const before = grid(6, 327, 2463);
    before.element.scrollTop = 3000;
    memory.rememberIndex(before.element, before.itemSize, before.columns, 2463);

    // A filter applied while the panel was opening: item 54 of a 5-card list is nowhere.
    const after = grid(4, 337, 5);
    expect(memory.restore(after.element, 5, after)).toBe(false);
    expect(memory.isPending()).toBe(false);
  });

  it("remembers nothing from the top of the list, or from a grid mid-measurement", () => {
    const memory = useGridScrollMemory();

    // Already at the top: there is nothing to put back, and a memory left pending would
    // suppress the scroll-to-top on the next filter change.
    const top = grid(6, 327, 2463);
    memory.rememberIndex(top.element, top.itemSize, top.columns, 2463);
    expect(memory.isPending()).toBe(false);

    // Zero geometry is a real state — the observer reports a width a frame after mount,
    // and dividing by it would anchor to Infinity.
    const measuring = grid(6, 327, 2463);
    measuring.element.scrollTop = 3000;
    memory.rememberIndex(measuring.element, 0, 6, 2463);
    expect(memory.isPending()).toBe(false);
    memory.rememberIndex(measuring.element, 327, 0, 2463);
    expect(memory.isPending()).toBe(false);
  });

  it("cannot be restored as pixels, nor an offset as an index", () => {
    const memory = useGridScrollMemory();

    // An index needs the scroller; without one the restore reports "not yet" and keeps
    // the memory, rather than silently writing the index as a pixel value.
    const before = grid(6, 327, 2463);
    before.element.scrollTop = 3000;
    memory.rememberIndex(before.element, before.itemSize, before.columns, 2463);

    const after = grid(4, 337, 2463);
    expect(memory.restore(after.element, 2463)).toBe(false);
    expect(after.element.scrollTop).toBe(0);
    expect(memory.isPending()).toBe(true);

    // And a pixel offset ignores a scroller it was given, so the card path is unchanged
    // by the existence of the index path.
    memory.forget();
    const card = scrollable(3000);
    card.scrollTop = 1073;
    memory.remember(card, 34);

    const back = grid(4, 337, 34);
    expect(memory.restore(back.element, 34, back)).toBe(true);
    expect(back.element.scrollTop).toBe(1073);
  });
});

/**
 * **When** the restore runs, which is a separate question from whether it is correct
 * (D18, amended).
 *
 * The reflow is not synchronous with the panel opening. `<main>` narrows, then a
 * `ResizeObserver` reports the new width, then the column count changes, then the
 * scroller's `:key` changes and it remounts. A restore attempted before that last step
 * finds a working scroller with the *old* geometry, succeeds, and consumes the memory —
 * and the remount that follows lands at the top with nothing left to put it back.
 *
 * The position is lost, and it looks exactly like never having tried. So the capture is
 * keyed on the panel and the restore on the column count, and this pins that.
 */
describe("the restore waits for the reflow, not the toggle (D18)", () => {
  beforeEach(() => stateStore.clear());

  function grid(columns: number, itemSize: number, itemCount: number) {
    const rows = Math.ceil(itemCount / columns);
    const element = scrollable(Math.max(0, rows * itemSize - 800));
    return {
      element,
      columns,
      itemSize,
      scrollToItem(index: number) {
        element.scrollTop = Math.floor(index / columns) * itemSize;
      },
    };
  }

  it("is consumed by a too-early restore, which is why the trigger is the column count", () => {
    const memory = useGridScrollMemory();

    // The panel opens. The index is captured while the old geometry is still true.
    const before = grid(6, 327, 2463);
    before.element.scrollTop = 3000;
    memory.rememberIndex(before.element, before.itemSize, before.columns, 2463);

    // ...and the observer has not fired yet, so this is still the *old* scroller: six
    // columns, rows laid out, entirely capable of satisfying a restore.
    expect(memory.restore(before.element, 2463, before)).toBe(true);

    // Which is the trap. The memory is now gone.
    expect(memory.isPending()).toBe(false);

    // The reflow finally arrives and remounts the scroller at the top. There is nothing
    // left to restore from, and the user is back at card 0.
    const after = grid(4, 337, 2463);
    expect(memory.restore(after.element, 2463, after)).toBe(false);
    expect(after.element.scrollTop).toBe(0);
  });

  it("survives when the restore waits for the new geometry", () => {
    const memory = useGridScrollMemory();

    const before = grid(6, 327, 2463);
    before.element.scrollTop = 3000;
    memory.rememberIndex(before.element, before.itemSize, before.columns, 2463);

    // Nothing touches the memory between the capture and the remount — the component
    // watches `gridColCount`, which changes only once the observer has reported.
    expect(memory.isPending()).toBe(true);

    const after = grid(4, 337, 2463);
    expect(memory.restore(after.element, 2463, after)).toBe(true);
    expect(after.element.scrollTop).toBeGreaterThan(0);
  });
});
