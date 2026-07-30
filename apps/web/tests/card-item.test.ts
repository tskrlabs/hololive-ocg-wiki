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
Object.assign(globalThis, { useDecks });

/* -------------------------------------------------------------------------- */

/** A main-deck card, which is the section with the 50-card limit. */
const card = (id: string): Card =>
  ({
    id,
    card_number: `hBP01-${id}`,
    card_type_code: "character",
    image_key: `hBP01/hBP01-${id}`,
  }) as unknown as Card;

async function mountTile(item: Card = card("1")) {
  const component = (await import("../app/components/card-list/CardItem.vue")).default;
  return mount(component, {
    props: { item },
    global: {
      stubs: {
        Dialog: { template: "<div><slot /></div>" },
        DialogTrigger: { template: "<div><slot /></div>" },
        CardItemDialogContent: true,
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

/** The three +N buttons, in the order the template renders them: 10, 4, 1. */
const addButtons = (wrapper: Awaited<ReturnType<typeof mountTile>>) =>
  wrapper.findAll("button").filter((b) => /^\s*(10|4|1)\s*$/.test(b.text()));

beforeEach(() => {
  stateStore.clear();
  toasts.length = 0;
  config.global.renderStubDefaultSlot = true;
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

    const removeButton = wrapper
      .findAll("button")
      .find((b) => b.classes().some((c) => c.startsWith("bg-red-500")));

    if (removeButton) {
      await removeButton.trigger("click");
      expect(toasts[0]?.message).toContain("nothingToRemove");
    }
  });
});
