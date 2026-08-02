/**
 * A card's URL, and the dialog that owns it (ADR 0009 D15; #39).
 *
 * Clicking a tile opens the **dialog** and pushes `/{locale}/card/{set}/{stem}`; that
 * same URL opened cold renders the **page**. The dialog's open state is therefore not the
 * dialog's own — it is a function of the route, which is what makes browser back close it
 * and forward reopen it without a single history listener in a component.
 *
 * Two live bugs this fixes, both verified in the running app before it existed:
 *
 * - **A card could not be linked.** The dialog changed no URL, so the only way to share a
 *   card was to describe it.
 * - **Back exited the list.** With no history entry to pop, the browser left the page
 *   entirely — and on mobile the back gesture is *how you close things*, so the natural
 *   gesture threw away scroll position and filter state.
 *
 * Without the push, `/card/…` would be 2,463 pages built purely for crawlers that no real
 * user ever reaches — the failure mode #33 exists to avoid.
 */

import type { Card } from "~/types/card";

/** The `{set}/{stem}` a path names, or null if it is not a card URL. */
export function cardKeyFromPath(path: string): string | null {
  // `/{locale}/card/{set}/{stem}`, with the locale prefix always present (the i18n
  // strategy is `prefix`, so even the default `tc` carries one).
  const match = /^\/[^/]+\/card\/([^/]+)\/([^/?#]+)\/?$/.exec(path);
  return match ? `${match[1]}/${match[2]}` : null;
}

/**
 * Marks a navigation as "opened from inside the app", so the card URL renders as a
 * dialog over the list rather than as a page.
 *
 * Carried in history state rather than in a ref, because it has to survive back and
 * forward: returning to a card entry by pressing forward must reopen the dialog, not
 * suddenly render the page. History state is the only thing the browser restores with the
 * entry itself.
 */
const OVERLAY_STATE = "cardOverlay";

export const useCardRoute = () => {
  const route = useRoute();
  const router = useRouter();
  const localePath = useLocalePath();

  /**
   * The `image_key` of the card whose tile opened the dialog, for returning focus to it.
   *
   * `useState` because the tile that sets it (`CardItem`, inside the list) and the dialog
   * that reads it (`CardRouteDialog`, above `<NuxtPage>`) are in different trees — the
   * same split that forced the dialog out of the list in the first place.
   */
  const lastOpenedKey = useState<string | null>("cardFocusReturnKey", () => null);

  /**
   * Whether a card dialog should be open, and for which key.
   *
   * Derived from the path rather than stored, so it cannot disagree with the URL — the
   * same reason `QueryState` is derived (#38). A stored boolean plus a `router.push` is
   * two sources of truth for one question, and the back button updates only one of them.
   */
  const openKey = computed(() => cardKeyFromPath(route.path));

  /**
   * Is this card URL an overlay over a list, or a page in its own right?
   *
   * The same URL is both, depending on how it was reached (D15) — a tile click opens the
   * dialog, and the same link opened cold renders the page. `route.fullPath` is in the
   * dependency list so this recomputes on every navigation; `history.state` is not
   * reactive on its own.
   */
  const isOverlay = computed(() => {
    void route.fullPath;
    if (typeof window === "undefined") return false;
    return window.history.state?.[OVERLAY_STATE] === true;
  });

  /**
   * Show a card: push its URL, which opens the dialog.
   *
   * `push`, not `replace` — the whole point is a history entry to go back to.
   */
  const openCard = (card: Card) => {
    // Remembered by *key* rather than by element (#48 §6). Reka restores focus to the
    // node that opened the dialog, which fails here for the reason the whole scroller-
    // focus problem exists: `RecycleScroller` may have reused that node for another card
    // while the dialog was open, so restoring to it would focus the wrong card — and if
    // it was recycled out entirely, focus lands on `<body>`. Verified in Chromium before
    // this: closing a card dialog left focus on `<body>` every time.
    lastOpenedKey.value = card.image_key;

    router.push({
      path: localePath(`/card/${card.image_key}`),
      state: { [OVERLAY_STATE]: true },
    });
  };

  /**
   * Put focus back on the tile the dialog was opened from, if it is still on screen.
   *
   * Looked up by `href` at the moment it is needed, so a recycled node cannot be
   * mistaken for the original. When the tile is genuinely gone — the reader scrolled the
   * card out of the list while the dialog was open — focus is left alone rather than
   * moved somewhere arbitrary; `useScrollerFocus` handles the "lost to body" case.
   */
  const restoreTileFocus = () => {
    const key = lastOpenedKey.value;
    if (!key) return;

    // ⚠️ This is the *first* attempt, not the only one, and the key is deliberately not
    // cleared here.
    //
    // Traced in Chromium: Reka's `DialogContent` blurs the element it restored to as part
    // of unmounting — ~300ms after close, with the node still connected — so whatever this
    // focuses is undone shortly afterwards, and focus lands on `<body>`. Two frames of
    // delay does not outrun it; the unmount is not on a frame boundary.
    //
    // `useScrollerFocus` is what catches that final blur, and it reads this same key to
    // return to the right tile rather than merely the nearest one. So this sets focus
    // optimistically (correct when nothing steals it) and leaves the key for the recovery
    // path, which clears it.
    requestAnimationFrame(() => {
      const tile = document.querySelector<HTMLElement>(
        `.scroller a[href$="/card/${CSS.escape(key)}"]`,
      );
      tile?.focus({ preventScroll: true });
    });
  };

  /**
   * Close the dialog.
   *
   * `router.back()` when there is somewhere to go back to, so the history entry the open
   * created is *consumed* rather than added to — otherwise opening and closing a card ten
   * times would leave ten entries to walk back through.
   *
   * The fallback matters more than it looks: a card URL opened cold has no list behind it
   * in this tab's history, and `back()` there would leave the site. `replace` to the list
   * keeps the user in the app, which is also what makes the dialog's close button safe on
   * a page arrived at from a shared link.
   */
  const closeCard = () => {
    if (window.history.state?.back) {
      router.back();
      return;
    }
    router.replace(localePath("/"));
  };

  return { openKey, openCard, closeCard, isOverlay, restoreTileFocus };
};
