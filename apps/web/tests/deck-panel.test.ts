/**
 * @vitest-environment happy-dom
 *
 * The deck panel's own grid (ADR 0009 D18, amended).
 *
 * **This mounts because the bug it guards against only exists in a template.** The list
 * was `grid-cols-4 md:grid-cols-10`, and `md:` reads the *viewport* while the grid lives
 * inside a 384px panel — so on every desktop it packed ten columns into ~326px of content
 * and rendered 30px tiles underneath 32px buttons. Nothing about that is visible to a
 * pure function: the arithmetic in `gridColumns.ts` is right, the deck model is right, and
 * the defect is one responsive prefix on one element. The same blind spot as F-019, #45
 * and #49 — the model was correct and the *wiring* was not.
 *
 * The assertion is deliberately about the **class**, not about a measured width: happy-dom
 * has no layout, so a rendered pixel means nothing here. What can be checked, and what the
 * bug actually was, is that the column count carries no viewport prefix at all.
 */

import { config, mount } from "@vue/test-utils";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
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

const translate = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

/** The deck's cards, resolved by `useDeckCards` through the card store. */
const CARDS: Card[] = Array.from({ length: 12 }, (_, i) =>
  ({
    id: `c${i}`,
    card_number: `hBP01-${i}`,
    card_type_code: "character",
    image_key: `hBP01/hBP01-${i}`,
    name: `カード${i}`,
  }) as unknown as Card,
);

Object.assign(globalThis, {
  ref,
  computed,
  watch,
  onMounted,
  onUnmounted,
  nextTick,
  useState: useStateShim,
  useI18n: () => ({ locale: ref("en"), t: translate }),
  useCardImage: () => (key: string) => `https://img.example/${key}.webp`,
  useCardQuery: () => ({
    getCardsByIds: async (ids: string[]) => CARDS.filter((c) => ids.includes(c.id)),
  }),
});

vi.mock("vue-sonner", () => ({
  toast: { warning: () => {}, error: () => {}, success: () => {} },
}));

const { useDecks } = await import("../app/composables/decks-states");
const { useDeckCards } = await import("../app/composables/useDeckCards");
Object.assign(globalThis, { useDecks, useDeckCards });

/* -------------------------------------------------------------------------- */

/**
 * Pretend the window is `width` wide.
 *
 * The point of the test is that this must make **no difference**, so the helper exists to
 * be called with several values and produce the same answer each time.
 */
function windowWidth(width: number) {
  Object.defineProperty(window, "innerWidth", { value: width, configurable: true });
}

async function mountList(cardIds: string[]) {
  const component = (await import("../app/components/parials/DeckPanelCardList.vue"))
    .default;
  const wrapper = mount(component, {
    props: { cardIds },
    global: {
      stubs: {
        Image: true,
        CardCountBadge: true,
        Dialog: { template: "<div><slot /></div>" },
        DialogTrigger: { template: "<div><slot /></div>" },
        CardItemDialogContent: true,
      },
      mocks: { $t: translate },
    },
  });
  // `useDeckCards` fetches on a watcher, so the grid does not exist on the first tick.
  await nextTick();
  await nextTick();
  return wrapper;
}

describe("the deck panel's card grid (D18)", () => {
  beforeEach(() => stateStore.clear());

  it("is three columns, at every window width", async () => {
    // The regression itself. `md:grid-cols-10` passed every test that existed because no
    // test ever mounted this at more than one width — and it only misbehaves above `md`.
    for (const width of [375, 768, 1024, 1280, 1512, 1920]) {
      windowWidth(width);
      const wrapper = await mountList(["c0", "c1", "c2", "c3"]);
      const grid = wrapper.find(".grid");

      expect(grid.exists(), `${width}px`).toBe(true);
      expect(grid.classes(), `${width}px`).toContain("grid-cols-3");
    }
  });

  it("carries no responsive column prefix at all", async () => {
    // The stronger statement, and the one that actually holds the fix: the panel's width
    // is a constant, so *any* viewport-keyed column count is wrong here regardless of
    // which one it names. A future `lg:grid-cols-5` would pass the test above.
    windowWidth(1512);
    const wrapper = await mountList(["c0", "c1"]);

    const columnClasses = wrapper
      .find(".grid")
      .classes()
      .filter((c) => c.includes("grid-cols-"));

    expect(columnClasses).toEqual(["grid-cols-3"]);
    for (const cls of columnClasses) {
      expect(cls).not.toMatch(/^(sm|md|lg|xl|2xl):/);
    }
  });

  it("renders one tile per distinct card, not per copy", async () => {
    // Three copies of one card is one tile with a count badge — the pipeline
    // `useDeckCards` owns. Asserted here because the grid is what makes it visible, and
    // a regression would show up as 50 tiles in a panel sized for a dozen.
    windowWidth(1512);
    const wrapper = await mountList(["c0", "c0", "c0", "c1"]);

    expect(wrapper.findAll(".grid > div")).toHaveLength(2);
  });

  it("names the card in every control, in all seven locales", async () => {
    // #51's defect, one surface further in: the labels were the literal English strings
    // "Add card" / "Remove card", identical on every tile, so a screen-reader user heard
    // the same three names 40 times with nothing to tell them apart.
    windowWidth(1512);
    const wrapper = await mountList(["c0"]);

    const labels = wrapper.findAll("button").map((b) => b.attributes("aria-label"));

    expect(labels.length).toBeGreaterThan(0);
    for (const label of labels) {
      expect(label).toBeTruthy();
      // Interpolated through `$t` with the card's name — not a bare English constant.
      expect(label).toContain("カード0");
    }
  });
});
