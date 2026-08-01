/**
 * @vitest-environment happy-dom
 *
 * Keyboard focus survives the virtual scroller recycling its nodes (#48 §6).
 *
 * **Both bugs this covers were reproduced in Chromium before the fix**, and neither is
 * visible to a pure-function test — which is the whole reason #48 asked for a mounted one:
 *
 * 1. Focus a tile, scroll 6000px, and `document.activeElement` is `<body>`.
 *    `RecycleScroller` reused the node holding focus, so the next Tab restarts from the
 *    top of the document — on a 2,463-card list.
 * 2. Close a card dialog and focus is on `<body>` again. Reka's `DialogContent` restores
 *    focus to the element that opened it, and then *blurs it* as it unmounts (traced:
 *    ~300ms after close, node still connected).
 *
 * This asserts the composable's behaviour directly rather than mounting the whole card
 * list: the scroller's recycling needs real layout, which happy-dom does not do, so a
 * mounted list would exercise the geometry and not the focus rules. What is tested is
 * exactly what was wrong — where focus ends up after it is lost.
 */

import { describe, expect, it, beforeEach, vi } from "vitest";
import { ref } from "vue";

/** The real composable reads Nuxt's `useState`; here it is a plain per-key ref store. */
const stateStore = new Map<string, ReturnType<typeof ref>>();

Object.assign(globalThis, {
  ref,
  useState: <T>(key: string, init?: () => T) => {
    if (!stateStore.has(key)) stateStore.set(key, ref(init ? init() : null));
    return stateStore.get(key)!;
  },
  onMounted: (fn: () => void) => fn(),
  onBeforeUnmount: () => {},
});

const { useScrollerFocus } = await import("../app/composables/useScrollerFocus");

/**
 * A scroller holding `count` tiles, each with a real card href.
 *
 * `getBoundingClientRect` is stubbed because happy-dom reports zeros for everything —
 * without it "the tile nearest the middle of the viewport" has no meaning and the
 * nearest-tile search would pick the first element every time, passing for the wrong
 * reason.
 */
function buildScroller(count: number, keys: string[]) {
  document.body.innerHTML = `
    <div class="scroller">
      ${keys
        .slice(0, count)
        .map((key) => `<a href="/en/card/${key}">card</a>`)
        .join("")}
    </div>`;

  const tiles = [...document.querySelectorAll<HTMLElement>(".scroller a")];
  tiles.forEach((tile, index) => {
    tile.getBoundingClientRect = () =>
      ({ top: index * 100, height: 100 }) as DOMRect;
  });
  return tiles;
}

/** `focusout` plus a frame, which is what the composable listens for. */
async function loseFocusFrom(element: HTMLElement) {
  element.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
  await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
  await new Promise((resolve) => setTimeout(resolve, 0));
}

const KEYS = ["hSD01/hSD01-001_OSR", "hSD01/hSD01-002_OSR", "hBP01/hBP01-014_UR"];

describe("focus survives the recycling scroller (#48 §6)", () => {
  beforeEach(() => {
    stateStore.clear();
    document.body.innerHTML = "";
    // happy-dom has no rAF scheduler that advances on its own.
    vi.stubGlobal("requestAnimationFrame", (fn: FrameRequestCallback) =>
      setTimeout(() => fn(0), 0) as unknown as number,
    );
    vi.stubGlobal("innerHeight", 300);
  });

  it("moves focus to a live tile when a recycled node drops it to <body>", async () => {
    useScrollerFocus();
    const tiles = buildScroller(3, KEYS);

    // A keyboard journey: without this the composable deliberately does nothing, because
    // hijacking focus from a mouse user would move the viewport under them.
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));

    await loseFocusFrom(tiles[0]!);

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement?.getAttribute("href")).toContain("/card/");
  });

  it("leaves a pointer user's focus alone", async () => {
    useScrollerFocus();
    const tiles = buildScroller(3, KEYS);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    window.dispatchEvent(new PointerEvent("pointerdown"));

    await loseFocusFrom(tiles[0]!);

    // Clicking the page background is a deliberate way to drop focus.
    expect(document.activeElement).toBe(document.body);
  });

  it("returns to the tile the dialog was opened from, not merely the nearest", async () => {
    useScrollerFocus();
    const tiles = buildScroller(3, KEYS);

    // What `useCardRoute.openCard` records when a tile opens the dialog.
    stateStore.set("cardFocusReturnKey", ref(KEYS[2]));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));

    await loseFocusFrom(tiles[0]!);

    expect(document.activeElement?.getAttribute("href")).toBe(`/en/card/${KEYS[2]}`);
  });

  it("falls back to the nearest tile when the originating card scrolled away", async () => {
    useScrollerFocus();
    buildScroller(2, KEYS); // the third card's tile is not mounted

    stateStore.set("cardFocusReturnKey", ref(KEYS[2]));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));

    await loseFocusFrom(document.querySelector<HTMLElement>(".scroller a")!);

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement?.getAttribute("href")).toContain("/card/");
  });

  it("does nothing when focus landed somewhere real", async () => {
    useScrollerFocus();
    const tiles = buildScroller(3, KEYS);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    // Tabbing from the last tile to a control outside the grid must not be dragged back.
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    outside.focus();

    await loseFocusFrom(tiles[0]!);

    expect(document.activeElement).toBe(outside);
  });
});
