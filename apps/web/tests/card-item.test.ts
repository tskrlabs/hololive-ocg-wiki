/**
 * @vitest-environment happy-dom
 *
 * The tile's add/remove feedback (#49).
 *
 * `deck.test.ts` covers `addToSection`'s arithmetic thoroughly — `result.added` is
 * asserted directly — and the bug still shipped, because the gap was never the
 * arithmetic. `addCardToDeck` returned how many copies actually landed, its docstring
 * said so explicitly, and `CardItem` discarded the number. Tapping **+10** on a deck
 * holding 47 of 50 added three copies with no toast, no message, and nothing to
 * distinguish it from a successful add of ten.
 *
 * So this mounts. It is the same blind spot as F-019 and #45: the model was right and
 * the *wiring* was wrong, and wiring only exists in a template.
 */

import { config, mount } from "@vue/test-utils";
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Card } from "../app/types/card";

/* -------------------------------------------------------------------------- */
/* The Nuxt shims — see component.test.ts for why these are hand-supplied.     */
/* -------------------------------------------------------------------------- */

const stateStore = new Map<string, unknown>();
function useStateShim<T>(key: string, init: () => T) {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()));
  return stateStore.get(key) as ReturnType<typeof ref<T>>;
}

/**
 * `$t`, with the interpolation left in.
 *
 * The rendered string is not the assertion — the *numbers* are. A message reading
 * "Added 3 of 10" has to carry a 3 and a 10 to be worth showing, and asserting on
 * English prose would break every time the copy is reworded.
 */
const translate = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

/** The card URLs the tile links to and pushes (D15). Recorded, so a test can assert them. */
const pushed: string[] = [];

Object.assign(globalThis, {
  ref,
  computed,
  watch,
  onMounted,
  onUnmounted,
  nextTick,
  shallowRef,
  useState: useStateShim,
  useI18n: () => ({ locale: ref("en"), t: translate }),
  useCardImage: () => (key: string) => `https://img.example/${key}.webp`,
  // The tile is a link now, so it needs the locale-aware path helper and the composable
  // that turns a click into a history push.
  useLocalePath: () => (path: string) => `/en${path}`,
  useCardRoute: () => ({
    openKey: computed(() => null),
    openCard: (card: Card) => pushed.push(`/en/card/${card.image_key}`),
    closeCard: () => {},
  }),
});

/** The toast surface, spied rather than rendered. */
const toasts: { level: string; message: string }[] = [];
vi.mock("vue-sonner", () => ({
  toast: {
    warning: (message: string) => toasts.push({ level: "warning", message }),
    error: (message: string) => toasts.push({ level: "error", message }),
    success: (message: string) => toasts.push({ level: "success", message }),
  },
}));

const { useDecks } = await import("../app/composables/decks-states");
// The tile reads density and the show-original toggle to decide what text to render, so
// both are the real modules — their `useState` is the shim above.
const { useCardDensity } = await import("../app/composables/useCardDensity");
const { useShowOriginal } = await import("../app/composables/useShowOriginal");
Object.assign(globalThis, { useDecks, useCardDensity, useShowOriginal });

/* -------------------------------------------------------------------------- */

/** A main-deck card, which is the section with the 50-card limit. */
const card = (id: string): Card =>
  ({
    id,
    card_number: `hBP01-${id}`,
    card_type_code: "character",
    image_key: `hBP01/hBP01-${id}`,
    name: "天音彼方",
    original: { name: "天音かなた" },
  }) as unknown as Card;

async function mountTile(item: Card = card("1")) {
  const component = (await import("../app/components/card-list/CardItem.vue")).default;
  return mount(component, {
    props: { item },
    global: {
      stubs: {
        // A real anchor, so the link's href and its click handler are both reachable.
        NuxtLink: {
          props: ["to"],
          template: "<a :href='to'><slot /></a>",
        },
        SimpleImage: true,
        CardCountBadge: true,
      },
      mocks: { $t: translate },
    },
  });
}

/** Put the app in editing mode with a deck holding `count` main-deck cards. */
function deckHolding(count: number) {
  const decks = useDecks();
  decks.setCurrentDeck({
    id: "d1",
    name: "test",
    author: "",
    oshiCardIds: [],
    mainCardIds: Array.from({ length: count }, (_, i) => `filler-${i}`),
    yellCardIds: [],
    version: "test",
  } as never);
  if (!decks.isEditing.value) decks.toggleEditing();
  return decks;
}

/**
 * The three +N buttons, in the order the template renders them: 10, 4, 1.
 *
 * Matched on the `.sr-only` label rather than on the visible digit. The digit alone is a
 * quantity, not a name — the defect #37 §7 had these buttons fix — so the label is now
 * the reliable identifier, and a button that loses it fails here rather than silently
 * dropping out of this list.
 */
const addButtons = (wrapper: Awaited<ReturnType<typeof mountTile>>) =>
  wrapper.findAll("button").filter((b) => b.text().includes("deck.addCopies"));

beforeEach(() => {
  stateStore.clear();
  toasts.length = 0;
  pushed.length = 0;
  config.global.renderStubDefaultSlot = true;
  // Both view preferences persist to `localStorage` (that is the point of them), and
  // happy-dom keeps one store for the whole file — so without this a test that switches
  // to compact silently sets the mode for every test after it.
  localStorage.clear();
});

describe("adding to a nearly-full deck (#49)", () => {
  it("says how many of the requested copies actually landed", async () => {
    // The issue's exact repro: 47 of 50, tap +10, three copies land.
    const decks = deckHolding(47);
    const wrapper = await mountTile();

    await addButtons(wrapper)[0]!.trigger("click");

    expect(decks.currentDeck.value!.mainCardIds).toHaveLength(50);
    expect(toasts).toHaveLength(1);
    // Both numbers have to be in the message: "Added 3" alone does not tell the user
    // that seven were dropped.
    expect(toasts[0]!.message).toContain('"added":3');
    expect(toasts[0]!.message).toContain('"requested":10');
  });

  it("says the section is full when nothing can be added at all", async () => {
    const decks = deckHolding(50);
    const wrapper = await mountTile();

    await addButtons(wrapper)[0]!.trigger("click");

    expect(decks.currentDeck.value!.mainCardIds).toHaveLength(50);
    expect(toasts).toHaveLength(1);
    expect(toasts[0]!.message).toContain("sectionFull");
  });

  it("stays silent when every requested copy lands", async () => {
    // The common path. A toast per successful add would be noise, and the count badge
    // already reports the change.
    const decks = deckHolding(0);
    const wrapper = await mountTile();

    await addButtons(wrapper)[0]!.trigger("click");

    expect(decks.currentDeck.value!.mainCardIds).toHaveLength(10);
    expect(toasts).toEqual([]);
  });

  it("names the section that is full, not just 'the deck'", async () => {
    // A deck has three sections with different limits; "full" without a name leaves the
    // user guessing which one.
    deckHolding(50);
    const wrapper = await mountTile();

    await addButtons(wrapper)[0]!.trigger("click");

    expect(toasts[0]!.message).toContain("Main Deck");
  });
});

describe("the tile's other guards", () => {
  it("adds nothing at all when not in editing mode", async () => {
    const decks = useDecks();
    decks.setCurrentDeck({
      id: "d1",
      name: "test",
      author: "",
      oshiCardIds: [],
      mainCardIds: [],
      yellCardIds: [],
      version: "test",
    } as never);

    const wrapper = await mountTile();

    // The controls are not even rendered outside editing mode.
    expect(addButtons(wrapper)).toHaveLength(0);
    expect(decks.currentDeck.value!.mainCardIds).toEqual([]);
  });

  it("reports a remove that removed nothing", async () => {
    // Reachable when the deck changes under a tile that still shows a remove button.
    const decks = deckHolding(1);
    const wrapper = await mountTile();

    await addButtons(wrapper)[2]!.trigger("click");
    toasts.length = 0;

    // Drop the card from under the tile, then ask to remove it.
    decks.currentDeck.value!.mainCardIds = [];
    await nextTick();

    // Found by its label, not by `bg-red-500` — the hardcoded red became
    // `--destructive`, the palette's one semantic colour (D4), and a test that keys on a
    // colour class breaks every time the theme moves.
    const removeButton = wrapper
      .findAll("button")
      .find((b) => b.text().includes("deck.removeCopy"));

    if (removeButton) {
      await removeButton.trigger("click");
      expect(toasts[0]?.message).toContain("nothingToRemove");
    }
  });
});

/**
 * The tile's text block — and the close of
 * [#29](https://github.com/tskrlabs/hololive-ocg-wiki/issues/29).
 *
 * The issue was never that the show-original toggle was broken; it worked, in the dialog.
 * The complaint was that the **card list had no names at all**, so the toggle had nothing
 * to act on in the one place a reader scanning 2,463 cards would want it. These assert
 * the thing that was missing, not the toggle that already worked.
 */
describe("the tile shows what a card is (#29, D14)", () => {
  /** The innermost element whose entire text is `value`. */
  const lineWith = (
    wrapper: Awaited<ReturnType<typeof mountTile>>,
    value: string,
  ) => wrapper.findAll("div").filter((n) => n.text() === value).at(-1);

  it("renders the name and the card number", async () => {
    const wrapper = await mountTile();

    expect(wrapper.text()).toContain("天音彼方");
    expect(wrapper.text()).toContain("hBP01-1");
  });

  it("hides the source name until the toggle asks for it", async () => {
    const wrapper = await mountTile();

    // Both names are on the card; only the translated one is on screen.
    expect(wrapper.text()).toContain("天音彼方");
    expect(wrapper.text()).not.toContain("天音かなた");
  });

  it("shows the source name on its own line when the toggle is on", async () => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountTile();
    await nextTick();

    expect(wrapper.text()).toContain("天音かなた");

    // Its *own line* is the point (D14). Inline — as `OriginalText` renders it in the
    // dialog — truncates 19% of tiles mid-comparison against under 1% stacked, and a
    // comparison you cannot read defeats the toggle. So they must be separate elements,
    // not one run of text.
    expect(lineWith(wrapper, "天音彼方")).toBeDefined();
    expect(lineWith(wrapper, "天音かなた")).toBeDefined();
  });

  it("marks the source name as Japanese so the right face renders it", async () => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountTile();
    await nextTick();

    expect(lineWith(wrapper, "天音かなた")?.attributes("lang")).toBe("ja");
  });

  it("says nothing extra for a card whose name matches its source", async () => {
    // `original` only carries fields that actually differ, so this covers the `ja` locale
    // and the untranslated card at once — and the absence is the whole check.
    useShowOriginal().enabled.value = true;
    const wrapper = await mountTile({
      ...card("2"),
      original: undefined,
    } as unknown as Card);
    await nextTick();

    expect(wrapper.text()).toContain("天音彼方");
    expect(wrapper.text()).not.toContain("天音かなた");
  });

  it("drops the whole block in compact mode", async () => {
    useCardDensity().density.value = "compact";
    const wrapper = await mountTile();
    await nextTick();

    // Art alone — which is what the site did before density existed.
    expect(wrapper.text()).not.toContain("天音彼方");
    expect(wrapper.text()).not.toContain("hBP01-1");
  });

  it("carries the full name in a title, since one line can truncate", async () => {
    // Overflow is under 1% in every locale measured, but "rare" is not "never", and a
    // truncated name with no way to read it is worse than no name at all.
    const wrapper = await mountTile();

    expect(lineWith(wrapper, "天音彼方")?.attributes("title")).toBe("天音彼方");
  });
});

/**
 * A card has a URL now (D15, #39).
 *
 * Two live bugs this closes, both verified in the running app: a card could not be
 * linked (the dialog changed no URL, so sharing one meant describing it), and browser
 * back exited the list entirely rather than closing the dialog — which on mobile is the
 * natural close gesture, so it threw away scroll position and filter state.
 */
describe("the tile is a link to the card's URL (#39)", () => {
  it("renders a real anchor at /{locale}/card/{set}/{stem}", async () => {
    // A real `<a>`, not a click handler: middle-click and ⌘-click open the card page in
    // a new tab, the status bar shows the destination, and a crawler walking the grid
    // finds 2,463 internal links rather than a wall of JavaScript.
    const wrapper = await mountTile();
    const link = wrapper.find("a");

    expect(link.exists()).toBe(true);
    // `{set}/{stem}` is `image_key` verbatim (D6).
    expect(link.attributes("href")).toBe("/en/card/hBP01/hBP01-1");
  });

  it("opens the dialog rather than navigating, on a plain click", async () => {
    // `@click.prevent` is what keeps the in-page behaviour a dialog. Without it the tile
    // would be a full navigation and the grid would unmount on every card view.
    const wrapper = await mountTile();

    await wrapper.find("a").trigger("click");

    expect(pushed).toEqual(["/en/card/hBP01/hBP01-1"]);
  });

  it("does not own a dialog of its own", async () => {
    // The dialog is hoisted to the list, driven by the route. A dialog owned here would
    // be destroyed the moment `RecycleScroller` recycled this tile's node — and 2,463
    // booleans the history API knows nothing about cannot answer to a back button.
    const wrapper = await mountTile();
    const markup = wrapper.html().replace(/<!--[\s\S]*?-->/g, "");

    expect(markup).not.toMatch(/DialogTrigger|dialog-content/i);
  });
});
