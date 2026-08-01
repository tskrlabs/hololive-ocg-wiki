/**
 * "You need a deck first" — said once, from one place (#57).
 *
 * Five call sites across four components each wrote their own copy of this guard and its
 * toast: `AppFooterOptionsButton` (×3), `AppFooterCurrentDeck`, and `FloatingDeck`. That
 * is the duplication #57 flagged, and it is not merely untidy — two of those paths can
 * fire in the same interaction, and until `<Toaster />` was mounted nobody could have
 * seen the message appear twice.
 *
 * `vue-sonner` de-duplicates by `id`, so giving the toast a stable one means a second
 * call while the first is still visible **replaces** it rather than stacking. That is the
 * actual fix for double-firing; collapsing five copies into one function is what makes it
 * enforceable.
 *
 * Returns whether there is a deck, so a caller reads:
 *
 *     if (!requireDeck()) return;
 */
import { toast } from "vue-sonner";

/** Stable across every call site, which is what makes the de-duplication work. */
const NO_DECK_TOAST_ID = "no-current-deck";

export const useDeckGuard = () => {
  const decks = useDecks();
  const { t } = useI18n();

  /**
   * True when a deck is selected. Otherwise warns and returns false.
   *
   * `toast.warning` rather than `error`: nothing has gone wrong and nothing was lost —
   * the app is telling you the order to do things in. D4's reasoning applied to copy
   * rather than colour.
   */
  const requireDeck = (): boolean => {
    if (decks.currentDeck.value) return true;
    toast.warning(t("deck.guard.selectFirst"), { id: NO_DECK_TOAST_ID });
    return false;
  };

  return { requireDeck };
};
