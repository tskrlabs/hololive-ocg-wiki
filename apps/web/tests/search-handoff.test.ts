/**
 * @vitest-environment happy-dom
 *
 * The search box's set-code handoff (ADR 0010).
 *
 * Mounted rather than pure, for the reason `component.test.ts` exists at all: what this
 * feature is *made of* is wiring. `matchSetCode` is a pure function and tested as one in
 * `filter.test.ts`; the thing that can break here is the debounced watcher writing to
 * three pieces of state and clearing a fourth, and none of that lives in a function a
 * unit test can call.
 *
 * The failure this guards against is specific and quiet: writing `filter.value.setCode`
 * but not `draftFilter.value.setCode` leaves the panel showing the old value, so the
 * next Apply silently undoes the routing. Nothing throws, the grid just reverts.
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
  watchEffect,
} from "vue";
import { beforeEach, describe, expect, it } from "vitest";

/* -------------------------------------------------------------------------- */
/* The Nuxt shims — same approach as component.test.ts                         */
/* -------------------------------------------------------------------------- */

const stateStore = new Map<string, unknown>();
function useStateShim<T>(key: string, init: () => T) {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()));
  return stateStore.get(key) as ReturnType<typeof ref<T>>;
}

const locale = ref("en");

/** What `useCardQuery().filterOptions` will answer with. Swapped per test. */
let optionsResponse: Record<string, unknown> = { names: [], tags: [], sets: [] };

Object.assign(globalThis, {
  ref,
  computed,
  watch,
  watchEffect,
  onMounted,
  onUnmounted,
  nextTick,
  shallowRef,
  useState: useStateShim,
  useI18n: () => ({ locale, t: (key: string) => key }),
  useId: () => "search-test",
  useCardQuery: () => ({
    isLoading: ref(false),
    filterOptions: async () => optionsResponse,
  }),
  /**
   * `useDebounceFn`, run synchronously.
   *
   * The real 500 ms delay is `@vueuse/core`'s behaviour, not ours, and waiting for it
   * would make this test slow and flaky to no benefit — what is under test is *what* the
   * callback does, not when it fires.
   */
  useDebounceFn: (fn: (...args: unknown[]) => unknown) => fn,
});

const { useFilter } = await import("../app/composables/filter-states");
Object.assign(globalThis, { useFilter });

const SearchInputAPI = (await import("../app/components/filter/SearchInputAPI.vue"))
  .default;

// `$t` is a template global rather than a composable, so it is supplied to the renderer
// rather than to `globalThis`.
config.global.mocks = { $t: (key: string) => key };

// The shadcn wrappers are not what is under test; a bare input carries the v-model.
config.global.stubs = {
  Input: {
    props: ["modelValue"],
    emits: ["update:modelValue"],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)">',
  },
};

/** Let the options fetch and the watchers settle. */
const settle = async () => {
  for (let i = 0; i < 4; i++) await nextTick();
};

async function typeInto(text: string) {
  const wrapper = mount(SearchInputAPI);
  await settle();
  await wrapper.find("input").setValue(text);
  await settle();
  return wrapper;
}

describe("typing a set code into the search box", () => {
  beforeEach(() => {
    stateStore.clear();
    optionsResponse = {
      names: [],
      tags: [],
      sets: [],
      set_codes: [
        { value: "hBP01", label: "hBP01" },
        { value: "hBP03", label: "hBP03" },
        { value: "hSD01", label: "hSD01" },
      ],
    };
  });

  it("becomes the set-code filter, and empties the box", async () => {
    // The behaviour users asked for: `hBP03` should mean "show me hBP03", not "find text
    // matching hBP03" — which also matches every ruling that cites an hBP03 card.
    const wrapper = await typeInto("hBP03");
    const filter = useFilter();

    expect(filter.filter.value.setCode).toBe("hBP03");
    expect(filter.filter.value.search).toBe("");
    expect((wrapper.find("input").element as HTMLInputElement).value).toBe("");
  });

  it("moves the draft too, so Apply cannot undo it", async () => {
    // The quiet one. The rail reads the *draft*; if only the applied value moved, the
    // panel would still show empty and the next Apply would clear a filter the user can
    // see is active.
    await typeInto("hBP03");
    const filter = useFilter();

    expect(filter.draftFilter.value.setCode).toBe("hBP03");
    expect(filter.hasPendingChanges.value).toBe(false);
  });

  it("canonicalises the casing", async () => {
    // The index already matches `hbp03`, so the rule must too — but the chip and the URL
    // should show the printed form.
    await typeInto("hbp03");
    expect(useFilter().filter.value.setCode).toBe("hBP03");
  });

  it("leaves an ordinary query as a search", async () => {
    await typeInto("フブキ");
    const filter = useFilter();

    expect(filter.filter.value.search).toBe("フブキ");
    expect(filter.filter.value.setCode).toBe("");
  });

  it("leaves a partial code as a search", async () => {
    // `hBP` is a prefix of nine codes. Routing it would answer a question the user has
    // not finished asking.
    await typeInto("hBP");
    const filter = useFilter();

    expect(filter.filter.value.search).toBe("hBP");
    expect(filter.filter.value.setCode).toBe("");
  });

  it("searches normally when the artifact carries no set codes", async () => {
    // R2 holds whatever the last publish wrote, and a Worker deploy does not republish
    // it — so the site can legitimately run against an artifact with no `set_codes`.
    // Every query then stays a search rather than the box appearing to swallow input.
    optionsResponse = { names: [], tags: [], sets: [] };

    await typeInto("hBP03");
    const filter = useFilter();

    expect(filter.filter.value.search).toBe("hBP03");
    expect(filter.filter.value.setCode).toBe("");
  });
});
