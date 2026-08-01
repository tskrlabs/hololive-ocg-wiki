/**
 * Keep keyboard focus alive across `RecycleScroller`'s node recycling (#48 §6).
 *
 * **The bug is real and was reproduced in Chromium before this existed.** Focus a card
 * link near the top of the grid, scroll 6000px, and `document.activeElement` is
 * `<body>` — the node holding focus was recycled out from under it. The next Tab starts
 * from the top of the document, so a keyboard user scrolling through 2,463 cards is
 * returned to the beginning every time the viewport turns over.
 *
 * This is inherent to node recycling rather than a mistake in our markup, and it is the
 * same class of blind spot as F-019: a scroller behaviour no pure-function test can see,
 * because it only exists once real nodes are being reused.
 *
 * **What this does, and what it deliberately does not.** When focus is lost to `<body>`
 * while the pointer was never involved, it moves to the nearest live tile — so Tab
 * continues from where the reader is *looking* rather than from the top. It does **not**
 * make the grid a single tab stop with arrow-key navigation, which #48 §6 also proposes:
 * that is a new keyboard model over a virtualised list where the target tile may not be
 * in the DOM at all, and it is tracked separately rather than folded in here.
 */

/** What a focusable tile looks like inside the scroller. */
const TILE_SELECTOR = 'a[href*="/card/"]';

export const useScrollerFocus = () => {
  /**
   * Whether the last focus change came from a real keyboard user.
   *
   * Restoring focus for a mouse user would be actively wrong — clicking the page
   * background is a deliberate way to drop focus, and yanking it onto a card would move
   * the viewport under a reader who never asked for it. `:focus-visible`'s own heuristic,
   * applied here because we need the answer in JavaScript.
   *
   * ⚠️ `useState`, not `ref`. Opening a card is a *route change* (D15), which unmounts the
   * list entirely — so a local ref is reconstructed as `false` every time the reader comes
   * back from a card, which is exactly the moment focus needs restoring. Traced in
   * Chromium: the handler fired, every guard passed, and the recovery was skipped because
   * the flag had been reset by the remount.
   */
  const keyboardActive = useState("scrollerKeyboardActive", () => false);

  const onKeydown = (event: KeyboardEvent) => {
    // Enter and Escape count too, not just movement keys: opening a card with Enter and
    // closing it with Escape is a keyboard journey, and it is the one that ends with the
    // list re-rendering underneath the restored tile (see `onFocusOut`).
    if (
      event.key === "Tab"
      || event.key === "Enter"
      || event.key === "Escape"
      || event.key.startsWith("Arrow")
    ) {
      keyboardActive.value = true;
    }
  };
  const onPointerdown = () => {
    keyboardActive.value = false;
  };

  /**
   * Focus survives recycling.
   *
   * `focusout` fires *before* the browser settles on the next active element, so the
   * check is deferred a frame: at the moment of the event `document.activeElement` is
   * still the old node, and a real Tab to another control would look identical to a
   * recycled-away one.
   */
  const onFocusOut = (event: FocusEvent) => {
    if (!keyboardActive.value) return;

    const from = event.target as HTMLElement | null;
    if (!from) return;

    // ⚠️ `closest('.scroller')` is not enough on its own.
    //
    // The case this exists for is the tile being *removed* — recycled away, or the list
    // re-rendering after the card dialog closes. By the time `focusout` fires the node
    // can already be detached, and a detached node has no `.scroller` ancestor, so the
    // check that looks like it identifies "focus left a tile" silently skips exactly the
    // situation that loses focus. Verified in Chromium: focus returned to the correct
    // tile after closing a dialog and was on `<body>` 500ms later.
    //
    // A tile is identifiable by what it is, so match that too.
    const wasTile = from.closest?.(".scroller") !== null || from.matches?.(TILE_SELECTOR);
    if (!wasTile) return;

    // ⚠️ The tile may still be in the document.
    //
    // Traced in Chromium: closing a card dialog blurs the restored tile ~300ms later with
    // `isConnected === true` and no DOM removal at all — Reka's dialog cleanup calls
    // `blur()` as it unmounts, well after both the route change and any `requestAnimation`
    // Frame pair. So "was this node recycled away" is the wrong question; the only thing
    // that matters is whether focus ended up nowhere.
    //
    // Re-focusing the *same* node is right in that case, and that is what the nearest-tile
    // search below does naturally — the tile is still on screen, so it is the nearest one.
    requestAnimationFrame(() => {
      // Focus landed somewhere real — a sibling tile, the footer, the browser chrome.
      // Nothing to repair.
      if (document.activeElement && document.activeElement !== document.body) return;

      const scroller = document.querySelector(".scroller");
      if (!scroller) return;

      // The card dialog knows which tile the reader came from, and that beats geometry:
      // returning to the card you just looked at is what "close" should mean. Only when
      // that tile is genuinely gone — scrolled out while the dialog was open — does the
      // nearest-tile search below apply.
      const returnTo = useState<string | null>("cardFocusReturnKey");
      if (returnTo.value) {
        const origin = scroller.querySelector<HTMLElement>(
          `a[href$="/card/${CSS.escape(returnTo.value)}"]`,
        );
        returnTo.value = null;
        if (origin) {
          origin.focus({ preventScroll: true });
          return;
        }
      }

      // The nearest live tile to where the reader is looking. `getBoundingClientRect` is
      // read once per candidate, over the handful of tiles the scroller keeps mounted —
      // not over 2,463 cards.
      const tiles = [...scroller.querySelectorAll<HTMLElement>(TILE_SELECTOR)];
      if (!tiles.length) return;

      const middle = window.innerHeight / 2;
      let best = tiles[0]!;
      let bestDistance = Number.POSITIVE_INFINITY;
      for (const tile of tiles) {
        const box = tile.getBoundingClientRect();
        const distance = Math.abs(box.top + box.height / 2 - middle);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = tile;
        }
      }

      // `preventScroll`: the reader chose this scroll position, and focusing a tile that
      // is already on screen must not nudge it.
      best.focus({ preventScroll: true });
    });
  };

  onMounted(() => {
    window.addEventListener("keydown", onKeydown, true);
    window.addEventListener("pointerdown", onPointerdown, true);
    window.addEventListener("focusout", onFocusOut, true);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("keydown", onKeydown, true);
    window.removeEventListener("pointerdown", onPointerdown, true);
    window.removeEventListener("focusout", onFocusOut, true);
  });

  return { keyboardActive };
};
