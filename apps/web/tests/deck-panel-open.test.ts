/**
 * @vitest-environment happy-dom
 *
 * Choosing a deck opens the panel and starts editing (ADR 0009 D18).
 *
 * Creating a deck, clicking its name, or clicking the pencil are all one statement of
 * intent — "I want to work on this deck" — and all three used to do exactly one thing:
 * set the current deck. The panel stayed shut, editing stayed off, and the next click on
 * a card did nothing, because `CardItem`'s add controls only render while editing. Three
 * more actions to reach the state the first click already meant.
 *
 * **The subtlety worth a test is that `openFor` sets editing at every width, and
 * `setOpen` does not.** D18 says the deck surface implies editing only where it does not
 * occlude the grid — that is a rule about *toggling the panel*, and it is right. It is
 * the wrong rule for *choosing a deck*: below `xl` the sheet occludes the grid, so
 * deferring to `setOpen` would leave editing off, and the user closing the sheet to reach
 * the cards would find that picking a deck had not put them in a state to add any.
 *
 * These call the real composable against a real deck store, because the whole behaviour
 * is the interaction between the two and a stub of either would be asserting the stub.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, effectScope, nextTick, onMounted, ref, watch } from "vue";

import type { Deck } from "../app/types/deck";

const stateStore = new Map<string, unknown>();
function useStateShim<T>(key: string, init: () => T) {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()));
  return stateStore.get(key) as ReturnType<typeof ref<T>>;
}

/**
 * The media query, controlled by the test.
 *
 * `useDeckPanel` reads exactly one — the `xl` push threshold — so a single ref is the
 * whole surface, and flipping it is how a test says "this is a phone" or "this is a
 * desktop" without a layout engine that happy-dom does not have.
 */
const pushed = ref(false);

Object.assign(globalThis, {
  ref,
  computed,
  watch,
  onMounted,
  useState: useStateShim,
  useI18n: () => ({ locale: ref("en"), t: (key: string) => key }),
  useMediaQuery: () => pushed,
});

vi.mock("vue-sonner", () => ({
  toast: { warning: () => {}, error: () => {}, success: () => {} },
}));

const { useDecks } = await import("../app/composables/decks-states");
Object.assign(globalThis, { useDecks });
const { useDeckPanel } = await import("../app/composables/useDeckPanel");

const deck = (name: string): Deck =>
  ({
    id: `${name}-1`,
    name,
    author: "",
    oshiCardIds: [],
    mainCardIds: [],
    yellCardIds: [],
    version: "test",
  }) as Deck;

/**
 * The composable is constructed inside an `effectScope`, and disposed after each test.
 *
 * `useDeckPanel` registers a `watch` — the #57 guard that closes the panel when its deck
 * is deleted. In the app that watcher is owned by the component's scope and dies with it;
 * a bare call from a test would leave one alive per test, all writing to the same
 * `useState` refs. The scope reproduces the ownership the app has, so what is asserted is
 * the guard rather than an accumulation of them.
 */
let scope: ReturnType<typeof effectScope>;

function inScope<T>(fn: () => T): T {
  return scope.run(() => fn())!;
}

/**
 * Reset the shared state **in place**, rather than clearing the map.
 *
 * `useState` is keyed global state: one ref per key for the life of the app, shared by
 * every caller. Clearing the map would hand the next test fresh refs while watchers from
 * the previous one still hold the old, which is a shape the app never has. Writing
 * through the existing refs keeps one identity per key for the whole file, so what the
 * tests exercise is the arrangement production actually runs.
 */
function resetState() {
  for (const [key, value] of stateStore) {
    const target = value as { value: unknown };
    if (key === "decks") target.value = [];
    else if (key === "currentDeck") target.value = null;
    else target.value = false;
  }
}

describe("choosing a deck (D18)", () => {
  beforeEach(() => {
    resetState();
    pushed.value = false;
    scope = effectScope();
  });

  /**
   * ⚠️ **Stopping the scope is what makes `stateStore.clear()` safe.**
   *
   * The shim hands out a fresh ref per key once the store is cleared, but a watcher
   * registered in an earlier test is still watching the *old* one — and still running.
   * Left alive it observes a ref nothing writes to any more, and, worse, writes to the
   * previous test's `isEditing` when it does fire. Stopping the scope disposes those
   * watchers with the state they were built against, so each test gets a clean pair.
   */
  afterEach(() => scope.stop());

  it("opens the panel and starts editing on a phone", () => {
    // The case the rule would have got wrong. Below `xl` the sheet occludes the grid, so
    // `setOpen` deliberately leaves editing alone — and picking a deck must not.
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    panel.openFor(deck("mine"));

    expect(decks.currentDeck.value?.name).toBe("mine");
    expect(panel.isOpen.value).toBe(true);
    expect(decks.isEditing.value).toBe(true);
  });

  it("does the same when the panel is pushed", () => {
    pushed.value = true;
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    panel.openFor(deck("mine"));

    expect(panel.isOpen.value).toBe(true);
    expect(decks.isEditing.value).toBe(true);
  });

  it("is what plain selection did not do", () => {
    // The regression, stated directly: this is the old behaviour of all three call sites.
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    decks.setCurrentDeck(deck("mine"));

    expect(decks.currentDeck.value?.name).toBe("mine");
    expect(panel.isOpen.value).toBe(false);
    expect(decks.isEditing.value).toBe(false);
  });

  it("leaves D18's toggle rule intact", () => {
    // `openFor` is an extra door into the open state, not a change to what opening means.
    // On a phone, toggling the panel still must not touch editing.
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    panel.setOpen(true);
    expect(decks.isEditing.value).toBe(false);

    // ...and above `xl` it still must.
    pushed.value = true;
    panel.setOpen(false);
    panel.setOpen(true);
    expect(decks.isEditing.value).toBe(true);
  });

  it("keeps editing on when the sheet is closed again", () => {
    // The reason `openFor` works below `xl` at all. You open the deck, close it to see
    // the grid, and are still editing — which is exactly the decoupling D18 specifies
    // there, now doing useful work rather than only preventing harm.
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    panel.openFor(deck("mine"));
    panel.setOpen(false);

    expect(panel.isOpen.value).toBe(false);
    expect(decks.isEditing.value).toBe(true);
  });

  /**
   * The #57 guard, through the new door.
   *
   * ⚠️ **Two awaits, and both are load-bearing.** Vue coalesces writes within a tick, so
   * `openFor` followed immediately by `deleteDeck` presents the watcher with one net
   * change and the guard never observes the deck it was meant to react to. Letting the
   * open settle first is what makes the delete a second, separate transition — which is
   * what it always is in the app, where the two are different user actions seconds apart.
   *
   * Diagnosed the hard way: without the first `await`, the guard appears never to run,
   * and every plausible cause (effect scopes, module registries, ref identity) looks
   * guilty. Instrumenting the watcher showed it firing correctly all along.
   */
  it("closes and stops editing when the chosen deck is deleted, on a phone", async () => {
    // The width that makes it interesting: `openFor` turns editing on below `xl`, where
    // `setOpen(false)` deliberately does not turn it off — so the delete path is the only
    // thing that can clear it.
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    const mine = deck("mine");
    decks.addDeck(mine);
    panel.openFor(mine);
    await nextTick();

    decks.deleteDeck(mine.id);
    await nextTick();

    expect(panel.isOpen.value).toBe(false);
    expect(decks.isEditing.value).toBe(false);
  });

  it("does the same where the panel is pushed", async () => {
    pushed.value = true;
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    const mine = deck("mine");
    decks.addDeck(mine);
    panel.openFor(mine);
    await nextTick();

    decks.deleteDeck(mine.id);
    await nextTick();

    expect(panel.isOpen.value).toBe(false);
    expect(decks.isEditing.value).toBe(false);
  });

  it("stops editing even when the sheet was already closed", async () => {
    // Reachable below `xl` in three taps: open the deck, close the sheet (editing stays
    // on, by D18), delete it from the Decks list. The panel guard has nothing to close,
    // and editing would have outlived its deck.
    const panel = inScope(useDeckPanel);
    const decks = useDecks();

    const mine = deck("mine");
    decks.addDeck(mine);
    panel.openFor(mine);
    await nextTick();

    panel.setOpen(false);
    expect(decks.isEditing.value).toBe(true);

    decks.deleteDeck(mine.id);
    await nextTick();

    expect(decks.isEditing.value).toBe(false);
  });
});
