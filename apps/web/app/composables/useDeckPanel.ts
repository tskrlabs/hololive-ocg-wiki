/**
 * Whether the deck panel is open, and what that implies about editing (ADR 0009 D18).
 *
 * **The rule: the deck surface implies editing only where it does not occlude the grid.**
 * That principle is unchanged from the original D18 — what changed is where it is true.
 * The panel used to be an overlay drawer at every width, which meant the rule held above
 * `lg` in *intent* and nowhere in *fact*: `DeckDrawer` rendered a `SheetContent`, which
 * mounts an opaque overlay and a focus trap, so the grid it was supposed to sit beside
 * was blacked out and inert. Opening the deck implied editing on a surface you could not
 * click. See the amended D18.
 *
 * Now there are three bands, and the rule reads the same in each:
 *
 * | width      | surface       | occludes the grid | editing         |
 * |------------|---------------|-------------------|-----------------|
 * | ≥ 1280     | pushed column | no                | follows the panel |
 * | 1024–1280  | modal sheet   | yes               | decoupled       |
 * | < 1024     | modal sheet   | yes               | decoupled       |
 *
 * Above `xl` the panel is a flex sibling: `<main>` shrinks, the grid re-derives its
 * columns from the width it has left (#43), and **nothing is ever covered**. So having
 * the panel open *is* the statement "I am building a deck", and the separate Edit toggle
 * stops being a thing to remember. Below `xl` the sheet covers the grid, so the two
 * decouple: you close it to see the cards you are adding, and that must not mean you have
 * stopped editing.
 *
 * This composable is the only place that coupling lives.
 */

import type { Deck } from "~/types/deck";

/**
 * The width at or above which the panel **pushes** the grid rather than covering it.
 *
 * `xl`, not `lg`, and the difference is arithmetic rather than taste. The panel is 384px
 * and the filter rail is 280px, so a pushed panel leaves the grid `width - 664`:
 *
 * | viewport | grid  | columns | tile   |
 * |----------|-------|---------|--------|
 * | 1920     | 1256  | 6       | 209px  |
 * | 1512     | 848   | 4       | 212px  |
 * | 1280     | 616   | 3       | 205px  |
 * | 1152     | 488   | 2       | 244px ← over `MAX_TILE` |
 * | 1024     | 360   | 2       | 180px ← in band, but two columns |
 *
 * 1280 is the last width where the grid keeps three real columns inside `gridColumns`'
 * 150–240px band. Below it the split is not worth making, so the sheet stays.
 *
 * Stated here as a number because this is the one place the rule needs to be *known* in
 * JavaScript rather than expressed as a class. Everywhere else, `hidden xl:flex` and its
 * complement do the work with no measuring and no flash while JS decides — that remains
 * the preferred form; this exists because "does the panel occlude the grid" is a
 * behavioural question, not a styling one.
 *
 * ⚠️ It must stay equal to Tailwind's `xl`, because the `xl:` classes in `index.vue`
 * decide which container renders and this decides what that container *means*. If they
 * disagree, there is a width where editing follows a panel that is covering the grid.
 * `tests/grid.test.ts` pins the arithmetic that chose it.
 */
export const DECK_PANEL_PUSH_MIN_WIDTH = 1280;

export const useDeckPanel = () => {
  const decks = useDecks();
  const isOpen = useState<boolean>("deckPanelOpen", () => false);

  /**
   * Whether the panel pushes the grid rather than covering it.
   *
   * `useMediaQuery` rather than a width ref: it is the same media query the CSS uses, so
   * the two cannot disagree at the boundary, and it needs no resize listener.
   */
  const isPushed = useMediaQuery(`(min-width: ${DECK_PANEL_PUSH_MIN_WIDTH}px)`);

  /**
   * Open/close, applying D18.
   *
   * Editing follows the panel only where the panel is pushed. Below that, editing is left
   * exactly as it was — the footer's Edit badge stays the control.
   */
  const setOpen = (open: boolean) => {
    isOpen.value = open;
    if (isPushed.value) decks.isEditing.value = open;
  };

  const toggle = () => setOpen(!isOpen.value);

  /**
   * Choosing a deck: select it, show it, and start editing — at **every** width.
   *
   * Creating a deck or picking one from the Decks list is an unambiguous statement of
   * intent, in a way that opening the panel by itself is not. Before this, all three of
   * those paths set the current deck and nothing else: the panel stayed shut, editing
   * stayed off, and the next click on a card did nothing at all, because `CardItem`'s add
   * controls only render while editing. The user had to create a deck, open the panel, and
   * toggle Edit — three actions to reach the state the first one already implied.
   *
   * ⚠️ **Editing is set here rather than left to `setOpen`**, and that is the whole point
   * of a separate action. `setOpen` applies D18 — editing follows the panel only where the
   * panel does not occlude the grid — which is right for *toggling a surface* and wrong
   * for *choosing a deck*. Below `xl` the sheet does occlude the grid, so `setOpen` would
   * leave editing off; the user would then close the sheet to reach the cards and find
   * that picking a deck had not put them in a state to add any.
   *
   * D18's rule survives intact, because it is a rule about what *opening the panel*
   * implies, not about what every path to an open panel implies. Closing the sheet
   * afterwards still leaves editing on below `xl` — that decoupling is exactly what makes
   * this work there.
   */
  const openFor = (deck: Deck) => {
    decks.setCurrentDeck(deck);
    isOpen.value = true;
    decks.isEditing.value = true;
  };

  /**
   * Closing the panel — and stopping editing — when the deck goes away.
   *
   * Deleting the current deck leaves the panel open over nothing, and `isEditing` true
   * with no deck to edit — which is the state every one of the five "Please select a deck
   * to continue." guards exists to catch (#57).
   *
   * ⚠️ **Editing is cleared directly rather than through `setOpen`**, and the difference
   * is only visible below `xl`. `setOpen` applies D18, which leaves editing alone where
   * the panel occludes the grid — correct for a toggle, wrong here: there is no deck, so
   * there is nothing editing could mean. Routing through it left `isEditing` true on
   * every phone-width delete, and `openFor` made that reachable in one click by turning
   * editing on at those widths in the first place.
   *
   * Covered by `tests/deck-panel-open.test.ts`, which has to let the open settle before
   * deleting — Vue coalesces both writes within a tick otherwise, and the watcher sees
   * one net change rather than the two transitions the app always produces.
   */
  watch(
    () => decks.currentDeck.value,
    (deck) => {
      if (deck) return;
      if (isOpen.value) isOpen.value = false;
      decks.isEditing.value = false;
    },
  );

  return { isOpen, isPushed, setOpen, toggle, openFor };
};
