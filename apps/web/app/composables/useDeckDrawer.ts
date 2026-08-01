/**
 * Whether the deck drawer is open, and what that implies about editing (ADR 0009 D18).
 *
 * **The rule: the deck surface implies editing only where it does not occlude the grid.**
 * Above `lg` the drawer is an overlay beside a still-visible grid, so having it open *is*
 * the statement "I am building a deck" — opening it turns editing on and closing it turns
 * editing off, and the separate Edit toggle stops being a thing to remember. Below `lg`
 * the drawer covers the grid, so the two decouple: you close the drawer to see the cards
 * you are adding, and that must not mean you have stopped editing.
 *
 * This composable is the only place that coupling lives. It was previously a watcher
 * inside `FloatingDeck.vue` that force-set `decks.isEditing` whenever the current deck
 * changed — which meant selecting a deck silently entered editing mode at every width,
 * with no way to be in a deck without editing it.
 *
 * **Why a permanent column was rejected** (D18): it costs a full grid column at 1512px
 * (6 → 5), paid even while browsing, and today's floating deck already sits directly over
 * where the filter rail now is (#36 §6).
 */

/**
 * The `lg` breakpoint, in pixels — Tailwind's default, and the same one `FilterRail` and
 * `FilterAPI` switch on.
 *
 * Stated here as a number because this is the one place the rule needs to be *known* in
 * JavaScript rather than expressed as a class. Everywhere else, `hidden lg:flex` and its
 * complement do the work with no measuring and no flash while JS decides — that remains
 * the preferred form; this exists because "does the drawer occlude the grid" is a
 * behavioural question, not a styling one.
 */
export const DECK_DRAWER_INLINE_MIN_WIDTH = 1024;

export const useDeckDrawer = () => {
  const decks = useDecks();
  const isOpen = useState<boolean>("deckDrawerOpen", () => false);

  /**
   * Whether the drawer sits *beside* the grid rather than over it.
   *
   * `useMediaQuery` rather than a width ref: it is the same media query the CSS uses, so
   * the two cannot disagree at the boundary, and it needs no resize listener.
   */
  const isInline = useMediaQuery(`(min-width: ${DECK_DRAWER_INLINE_MIN_WIDTH}px)`);

  /**
   * Open/close, applying D18.
   *
   * Editing follows the drawer only when the drawer is an overlay beside the grid. Below
   * that, editing is left exactly as it was — the footer's Edit badge stays the control.
   */
  const setOpen = (open: boolean) => {
    isOpen.value = open;
    if (isInline.value) decks.isEditing.value = open;
  };

  const toggle = () => setOpen(!isOpen.value);

  /**
   * Closing the drawer when the last deck goes away.
   *
   * Deleting the current deck leaves the drawer open over nothing, and `isEditing` true
   * with no deck to edit — which is the state every one of the five "Please select a deck
   * to continue." guards exists to catch (#57).
   */
  watch(
    () => decks.currentDeck.value,
    (deck) => {
      if (!deck && isOpen.value) setOpen(false);
    },
  );

  return { isOpen, isInline, setOpen, toggle };
};
