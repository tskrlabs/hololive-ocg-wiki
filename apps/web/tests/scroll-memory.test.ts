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
