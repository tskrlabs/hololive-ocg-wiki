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
import {
  classifyError,
  setCardSource,
  useCardQuery,
} from "../app/composables/useCardQuery";
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
const { gridGeometry, textBlockHeight } = await import("../app/composables/gridColumns");
// Density and show-original are real modules too, for the same reason: their `useState`
// is the shim, and the geometry under test is the one the component actually computes.
const { useCardDensity, showsText } = await import("../app/composables/useCardDensity");
const { useShowOriginal } = await import("../app/composables/useShowOriginal");
Object.assign(globalThis, {
  useFilter,
  useCardQuery,
  gridGeometry,
  textBlockHeight,
  useCardDensity,
  showsText,
  useShowOriginal,
});

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

/**
 * A card source whose `filter` rejects — offline, HTTP 500, or a timeout (#45).
 *
 * This is the shape no pure-function test could reach: the bug only exists when a real
 * fetch *rejects*, and every one of the other tests here resolves. Same blind spot as
 * F-019.
 */
function failingSource(rejection: unknown, failures = Infinity) {
  let calls = 0;
  const { source } = fakeSource();
  return {
    get calls() {
      return calls;
    },
    source: {
      ...source,
      async filter(...args: unknown[]) {
        calls++;
        if (calls <= failures) throw rejection;
        return (source.filter as (...a: unknown[]) => unknown)(...args);
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
        // Nuxt auto-imports the shadcn `Button`; outside Nuxt it does not resolve, and
        // an unresolved component renders nothing — which would let the Retry test
        // "pass" by clicking some other button entirely.
        Button: {
          inheritAttrs: false,
          template: "<button class='ui-button' v-bind='$attrs'><slot /></button>",
        },
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
  // Density and show-original persist to `localStorage`, and happy-dom keeps one store
  // for the whole file — so without this a test that switches to compact sets the mode
  // for every test after it.
  localStorage.clear();

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

describe("a failed fetch (#45)", () => {
  /*
   * The bug: every failure was written down as `cards: []`, which is what a genuine
   * zero-result also produces — so going offline rendered "No cards found — try adjusting
   * your filters". The advice cannot help, and a user on a flaky connection concludes the
   * wiki has no cards.
   */
  it("does not blame the user's filters when the API is unreachable", async () => {
    setCardSource(failingSource(new Error("Failed to fetch")).source as never);

    const wrapper = await mountList();
    await settle();

    const text = wrapper.text();
    expect(text).not.toContain("Try adjusting your filters");
    expect(text).not.toContain("No cards found");
    expect(text).toContain("errors.cards.offline.title");
    expect(text).toContain("errors.retry");
  });

  it("still blames the filters when the filters really did match nothing", async () => {
    // The other half: the empty state has to survive, or this trades one wrong message
    // for another.
    const { source } = fakeSource();
    setCardSource({
      ...source,
      async filter() {
        return { cards: [], total: 0 };
      },
    } as never);

    const wrapper = await mountList();
    await settle();

    expect(wrapper.text()).toContain("No cards found");
    expect(wrapper.text()).toContain("Try adjusting your filters");
    expect(wrapper.text()).not.toContain("errors.cards");
  });

  it("tells a server error apart from an unreachable network", async () => {
    // The distinction is worth drawing because the useful advice differs: "check your
    // connection" is wrong when the connection is fine and our Worker is down.
    setCardSource(failingSource({ statusCode: 500 }).source as never);

    const wrapper = await mountList();
    await settle();

    expect(wrapper.text()).toContain("errors.cards.server.title");
  });

  it("recovers when Retry succeeds", async () => {
    // A failure caches nothing, so the retry is a real second request rather than a
    // replay of the empty result.
    const failing = failingSource(new Error("Failed to fetch"), 1);
    setCardSource(failing.source as never);

    const wrapper = await mountList();
    await settle();
    expect(wrapper.text()).toContain("errors.cards.offline.title");

    const retry = wrapper.find("button.ui-button");
    expect(retry.exists(), "the Retry button should render").toBe(true);
    await retry.trigger("click");
    await settle();

    expect(failing.calls).toBe(2);
    expect(wrapper.text()).not.toContain("errors.cards");
    expect(wrapper.findComponent(ScrollerStub).props("items")).toHaveLength(PAGE);
  });

  it("keeps the cards already on screen when the *next* page fails", async () => {
    // Replacing a working list with an error panel would be a worse answer than leaving
    // the list alone, so the error surfaces only when there is nothing else to show.
    const { source } = fakeSource();
    let calls = 0;
    setCardSource({
      ...source,
      async filter(...args: unknown[]) {
        if (++calls > 1) throw new Error("Failed to fetch");
        return (source.filter as (...a: unknown[]) => unknown)(...args);
      },
    } as never);

    const wrapper = await mountList();
    await settle();
    await wrapper.findComponent(ScrollerStub).vm.$emit("scroll-end");
    await settle();

    expect(wrapper.findComponent(ScrollerStub).props("items")).toHaveLength(PAGE);
    expect(wrapper.text()).not.toContain("errors.cards");
  });
});

describe("classifying a failure (#45)", () => {
  it("reads an HTTP status as the server's fault, and its absence as the network's", () => {
    // `$fetch` rejects with a `statusCode` when a response came back and with none when
    // the request never completed — which is exactly the distinction the user needs.
    expect(classifyError({ statusCode: 500 })).toBe("server");
    expect(classifyError({ statusCode: 404 })).toBe("server");
    expect(classifyError({ statusCode: 504 })).toBe("timeout");
    expect(classifyError({ statusCode: 408 })).toBe("timeout");
    expect(classifyError(new Error("Failed to fetch"))).toBe("offline");
    expect(classifyError(undefined)).toBe("offline");
    expect(classifyError({ name: "AbortError" })).toBe("timeout");
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

/**
 * The scroller's geometry follows the density mode and the toggle (#37 §5).
 *
 * `grid.test.ts` pins the arithmetic — that a text block is 40px, or 58px with the source
 * name. What it cannot see is whether the component ever *asks* for the right one, and
 * that is the half where this class of bug lives: `RecycleScroller` takes `itemSize` as a
 * prop and caches every row's position from it, so a component that computes the height
 * correctly and then fails to re-measure renders a grid whose rows overlap. Nothing
 * throws.
 *
 * This is F-019's shape exactly — a prop that was never passed, invisible to 44
 * pure-function tests — which is why the issue asked for a mounted assertion here.
 */
describe("density and the show-original toggle change the grid's geometry (#37)", () => {
  const itemSizeOf = (wrapper: Awaited<ReturnType<typeof mountList>>) =>
    wrapper.findComponent(ScrollerStub).props("itemSize") as number;

  const keyOf = (wrapper: Awaited<ReturnType<typeof mountList>>) =>
    wrapper.findComponent(ScrollerStub).vm.$.vnode.key as string;

  /**
   * Both inputs, set explicitly.
   *
   * `useState` is shared by key across the whole file (that is what makes it Nuxt's
   * `useState`), and `stateStore.clear()` in `beforeEach` drops the *refs* but not the
   * ones a still-mounted component captured. Stating both every time is what keeps each
   * assertion about the transition it names rather than about test order.
   */
  const setModes = async (density: "comfortable" | "compact", original: boolean) => {
    useCardDensity().density.value = density;
    useShowOriginal().enabled.value = original;
    await settle();
  };

  it("grows every row by one line when the toggle goes on", async () => {
    const wrapper = await mountList();
    await setModes("comfortable", false);

    const before = itemSizeOf(wrapper);

    await setModes("comfortable", true);

    // Exactly one line taller — the source name's own line (D14), on every tile at once.
    expect(itemSizeOf(wrapper) - before).toBe(18);
  });

  it("drops the whole text block in compact mode", async () => {
    const wrapper = await mountList();
    await setModes("comfortable", false);

    const comfortable = itemSizeOf(wrapper);

    await setModes("compact", false);

    expect(comfortable - itemSizeOf(wrapper)).toBe(40);
  });

  it("ignores the toggle in compact mode, where there is no name to pair", async () => {
    const wrapper = await mountList();
    await setModes("compact", false);

    const plain = itemSizeOf(wrapper);

    await setModes("compact", true);

    // Art-only is art-only: a source name with no name above it is not a line.
    expect(itemSizeOf(wrapper)).toBe(plain);
  });

  it("re-measures on a mode change, not only on a resize", async () => {
    // The wiring that makes the assertions above possible. Before this, `itemSize` was
    // written only by the resize observer, so flipping a toggle left the grid on the
    // previous mode's row height until the window happened to resize.
    const wrapper = await mountList();
    await setModes("comfortable", false);

    const start = itemSizeOf(wrapper);
    await setModes("compact", false);

    expect(itemSizeOf(wrapper)).not.toBe(start);
  });

  it("remounts the scroller, because a cached row position outlives a prop change", async () => {
    // The key is the actual fix. `RecycleScroller` computes each item's offset once from
    // the `itemSize` it was built with; handing it a new value does not reposition the
    // rows already measured, so the grid overlaps until it is rebuilt.
    const wrapper = await mountList();
    await setModes("comfortable", false);

    const before = keyOf(wrapper);

    await setModes("compact", false);
    const afterDensity = keyOf(wrapper);

    await setModes("comfortable", true);
    const afterOriginal = keyOf(wrapper);

    expect(afterDensity).not.toBe(before);
    expect(afterOriginal).not.toBe(before);
    expect(afterOriginal).not.toBe(afterDensity);
  });
});
