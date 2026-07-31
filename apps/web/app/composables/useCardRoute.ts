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
    router.push({
      path: localePath(`/card/${card.image_key}`),
      state: { [OVERLAY_STATE]: true },
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

  return { openKey, openCard, closeCard, isOverlay };
};
