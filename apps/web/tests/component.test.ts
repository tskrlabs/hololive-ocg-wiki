/**
 * @vitest-environment happy-dom
 *
 * The card list's *wiring* (F-019).
 *
 * The other test files here cover pure functions, which is why this bug shipped: the
 * homepage fetched page 1 and stopped, showing 200 of 2,448 cards, and every one of the
 * 44 tests passed. The defect was a prop that was never written down. Nothing short of
 * mounting can see that.
 *
 * `RecycleScroller` gates its `scrollEnd` emit behind `emitUpdate`, which defaults to
 * false:
 *
 *     a.emitUpdate && (s?.onUpdate)?.call(s, P, A, ge, ze)
 *     onUpdate: (…, we) => { … we >= t.items.length - 1 && s("scrollEnd") }
 *
 * So `@scroll-end="handleScrollEnd"` was live, correct, and unreachable.
 *
 * The scroller is stubbed rather than driven for real: happy-dom reports every element as
 * zero-sized, so a real scroller would compute its visible range from a zero-height
 * viewport and the test would be measuring the shim, not us. The split is deliberate —
 * `the library contract` asserts the facts we depend on against the *real* import, so a
 * rename or a behaviour change in `vue-virtual-scroller` fails here rather than silently
 * making the stub a fiction; the rest assert what our component does with them.
 */

import { config, mount } from "@vue/test-utils";
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
  watch,
} from "vue";
import { RecycleScroller } from "vue-virtual-scroller";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createEmpty } from "../app/composables/filter-states";
import { setCardSource, useCardQuery } from "../app/composables/useCardQuery";
import type { CardCollection } from "../app/types/card";

/* -------------------------------------------------------------------------- */
/* The Nuxt shims                                                             */
/*                                                                            */
/* The component reaches `useI18n`, `useFilter`, `useState` and the Vue APIs   */
/* through Nuxt's auto-imports, which are free variables at runtime. Outside   */
/* Nuxt they resolve from the global scope, so they are supplied here rather   */
/* than by pulling in `@nuxt/test-utils` and a build.                          */
/* -------------------------------------------------------------------------- */

/** Nuxt's `useState`: one ref per key, shared across callers. */
const stateStore = new Map<string, unknown>();
function useStateShim<T>(key: string, init: () => T) {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()));
  return stateStore.get(key) as ReturnType<typeof ref<T>>;
}

const locale = ref("tc");

Object.assign(globalThis, {
  ref,
  computed,
  watch,
  onMounted,
  onUnmounted,
  nextTick,
  shallowRef,
  useState: useStateShim,
  useI18n: () => ({ locale, t: (key: string) => key }),
});

// The real filter module — its `useState` is the shim above, so this is the production
// module under test rather than a reimplementation of it.
const { useFilter } = await import("../app/composables/filter-states");
const { gridGeometry } = await import("../app/composables/gridColumns");
Object.assign(globalThis, { useFilter, useCardQuery, gridGeometry });

// happy-dom has no ResizeObserver, and `v-resize-observer` constructs one on mount.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

/* -------------------------------------------------------------------------- */

const TOTAL = 2448;
const PAGE = 200;

/** Cards numbered from an offset, so a page's identity is checkable. */
const pageOf = (page: number): CardCollection =>
  Array.from({ length: PAGE }, (_, i) => {
    const n = (page - 1) * PAGE + i;
    return { id: String(n), card_number: `hBP01-${n}` };
  }) as unknown as CardCollection;

/** A card source that serves 2,448 cards, and records what was asked for. */
function fakeSource() {
  const requests: { page: number; limit: number; skipCount: boolean }[] = [];
  return {
    requests,
    source: {
      async filter(
        _filters: unknown,
        _locale: unknown,
        page = 1,
        limit = 50,
        skipCount = false,
      ) {
        requests.push({ page, limit, skipCount });
        return skipCount
          ? { cards: pageOf(page) }
          : { cards: pageOf(page), total: TOTAL };
      },
      async byId() {
        return undefined;
      },
      async byIds() {
        return [];
      },
      async byCardNumber() {
        return [];
      },
      async byCardNumbers() {
        return [];
      },
      async search() {
        return [];
      },
      async filterOptions() {
        return { names: [], tags: [], sets: [] };
      },
    },
  };
}

/** Records the scroller's props and the imperative calls made against it. */
const scrollToItem = vi.fn();
const ScrollerStub = {
  name: "RecycleScroller",
  props: [
    "items",
    "itemSize",
    "itemSecondarySize",
    "gridItems",
    "buffer",
    "keyField",
    "emitUpdate",
  ],
  methods: { scrollToItem },
  template: "<div class='scroller-stub'><slot :item='items[0]' /></div>",
};

async function mountList() {
  const component = (await import("../app/components/card-list/CardListViewAPI.vue"))
    .default;
  return mount(component, {
    global: {
      stubs: {
        RecycleScroller: ScrollerStub,
        CardItem: { template: "<div class='card-item' />" },
      },
      mocks: { $t: (key: string) => key },
      directives: { "resize-observer": {} },
    },
  });
}

/** The component debounces by 300ms and defers through `setTimeout`. */
async function settle(ms = 400) {
  await vi.advanceTimersByTimeAsync(ms);
  await nextTick();
  await nextTick();
}

let requests: { page: number; limit: number; skipCount: boolean }[];

beforeEach(() => {
  vi.useFakeTimers();
  scrollToItem.mockClear();
  stateStore.clear();
  locale.value = "tc";
  config.global.renderStubDefaultSlot = true;

  const fake = fakeSource();
  requests = fake.requests;
  setCardSource(fake.source as never);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("the library contract", () => {
  // Asserted against the real import: the stub below is only honest while these hold.
  it("gates scrollEnd behind emitUpdate, which defaults to false", () => {
    const props = RecycleScroller.props as Record<string, { default?: unknown }>;
    expect(props).toHaveProperty("emitUpdate");
    expect(props.emitUpdate?.default).toBe(false);
  });

  it("still emits the event the component listens for", () => {
    expect(RecycleScroller.emits).toContain("scrollEnd");
  });
});

describe("CardListViewAPI", () => {
  it("passes emit-update, without which scroll-end never fires (F-019)", async () => {
    const wrapper = await mountList();
    await settle();

    const scroller = wrapper.findComponent(ScrollerStub);
    expect(scroller.exists()).toBe(true);
    // The whole bug, in one assertion.
    expect(scroller.props("emitUpdate")).toBe(true);
  });

  it("loads the first page and reports the full total", async () => {
    const wrapper = await mountList();
    await settle();

    expect(requests).toHaveLength(1);
    expect(requests[0]).toMatchObject({ page: 1, limit: PAGE, skipCount: false });
    expect(wrapper.findComponent(ScrollerStub).props("items")).toHaveLength(PAGE);
    expect(useCardQuery().total.value).toBe(TOTAL);
  });

  it("appends the next page when the scroller reaches the end", async () => {
    const wrapper = await mountList();
    await settle();

    await wrapper.findComponent(ScrollerStub).vm.$emit("scroll-end");
    await settle();

    expect(requests).toHaveLength(2);
    // Page 2 skips the COUNT query — the total is already known (F-014).
    expect(requests[1]).toMatchObject({ page: 2, limit: PAGE, skipCount: true });
    expect(wrapper.findComponent(ScrollerStub).props("items")).toHaveLength(PAGE * 2);
  });

  it("keeps paging to the end of the set rather than stopping at page 2", async () => {
    const wrapper = await mountList();
    await settle();

    for (let i = 0; i < 3; i++) {
      await wrapper.findComponent(ScrollerStub).vm.$emit("scroll-end");
      await settle();
    }

    expect(requests.map((r) => r.page)).toEqual([1, 2, 3, 4]);
    expect(wrapper.findComponent(ScrollerStub).props("items")).toHaveLength(PAGE * 4);
  });

  it("does not request past the last page", async () => {
    const wrapper = await mountList();
    await settle();

    // Pretend everything is already loaded; `hasMore` is false and the guard should hold.
    useCardQuery().cards.value = pageOf(1).concat(
      Array.from({ length: TOTAL - PAGE }, (_, i) => ({
        id: `x${i}`,
      })) as unknown as CardCollection,
    );
    await nextTick();

    await wrapper.findComponent(ScrollerStub).vm.$emit("scroll-end");
    await settle();

    expect(requests).toHaveLength(1);
  });

  it("returns to the top when the filter changes", async () => {
    const wrapper = await mountList();
    await settle();

    await wrapper.findComponent(ScrollerStub).vm.$emit("scroll-end");
    await settle();
    scrollToItem.mockClear();

    const filter = useFilter();
    filter.filter.value = { ...createEmpty(), name: "Pekora" };
    await settle();

    // A fresh result set starts at page 1 …
    expect(requests.at(-1)).toMatchObject({ page: 1, skipCount: false });
    // … and the viewport follows it, rather than staying where the last list was.
    expect(scrollToItem).toHaveBeenCalledWith(0);
  });
});

describe("the scroller's height (#44)", () => {
  /*
   * happy-dom does no layout — every element measures zero — so these assert the *rules*
   * rather than the resulting pixels. That is a real limit and worth stating: they would
   * not catch a wrong flex-basis or a stacking-context mistake, only a return to the
   * shapes that caused the bug. The pixel check is a browser, and was done by hand.
   *
   * What they do cover is the specific regression: a height keyed to the viewport rather
   * than to the space between the bars, which put ~138px of the list under the chrome,
   * and the two workarounds that grew on top of it.
   */
  it("sizes itself from its parent, never from the viewport", async () => {
    const wrapper = await mountList();
    await settle();

    // `100dvh` is the bug. `h-full`/`height: 100%` is the fix, and the difference is
    // only visible in the class list — both render identically at zero size.
    //
    // Comments are stripped first: the markup carries prose *about* `100dvh` explaining
    // why it is gone, and matching that would make this pass for the wrong reason.
    const markup = wrapper.html().replace(/<!--[\s\S]*?-->/g, "");
    expect(markup).not.toMatch(/100dvh|h-dvh|h-screen/);
  });

  it("has no dead padding standing in for the hidden region", async () => {
    const wrapper = await mountList();
    await settle();

    // `pb-[65vh]` was 520px of empty space at an 800px viewport, added to keep the last
    // row clear of chrome that overlapped it. With the scroller sized correctly there is
    // nothing to clear.
    const markup = wrapper.html().replace(/<!--[\s\S]*?-->/g, "");
    expect(markup).not.toMatch(/pb-\[\d+vh\]/);
  });

  it("puts the results summary in flow rather than floating it", async () => {
    const wrapper = await mountList();
    await settle();

    // It was `fixed` *because* of this bug — in flow it sat below a full-viewport
    // scroller and was never on screen, which is how "Showing 200 of 2448" went unseen
    // while infinite scroll was broken (F-019).
    const summary = wrapper
      .findAll("div")
      .find((node) => node.text().startsWith("Showing {count} of {total} cards"));

    expect(summary, "the results summary should render").toBeDefined();
    expect(summary!.classes()).not.toContain("fixed");
  });
});
