/**
 * @vitest-environment happy-dom
 *
 * The source names actually reach the screen (#61).
 *
 * `CardListOriginalText` is reached by **auto-import name**, never by path: no module in
 * the app imports the file. That makes the name the entire contract between the five call
 * sites and the component, and it is a contract nothing checked — which is how the feature
 * shipped dead on 2026-07-30 and stayed that way.
 *
 * The failure was silent by construction. `nuxt.config` sets `pathPrefix: false`, so the
 * file registered as `OriginalText` while every call site asked for `CardListOriginalText`;
 * Vue resolves an unknown name to an inert custom element and **warns to the console**
 * rather than throwing. The build succeeded, the page rendered, and the Japanese text sat
 * in the DOM as an attribute on a `<cardlistoriginaltext>` tag that CSS never styled and a
 * reader never saw. The card list looked fine throughout because `CardItem` inlines its
 * own markup and never used the component at all.
 *
 * So these mount the blocks the way Nuxt assembles them — the component registered under
 * **the name derived from its filename** — and assert the text is *rendered*, not merely
 * passed. Registering it under a hand-written name would defeat the test: it would pass
 * against the very rename that was broken.
 *
 * `make check-site` covers the other half, bundle-wide, for call sites this file does not
 * name. Neither guard subsumes the other: this one asserts the user-visible behaviour and
 * runs pre-commit; that one catches typo'd names nobody wrote a test for.
 */

import { mount } from "@vue/test-utils";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { readdirSync } from "node:fs";
import { resolve } from "node:path";

import type { Card } from "../app/types/card";

const stateStore = new Map<string, unknown>();
function useStateShim<T>(key: string, init: () => T) {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()));
  return stateStore.get(key) as ReturnType<typeof ref<T>>;
}

const translate = (key: string) => key;

Object.assign(globalThis, {
  ref,
  computed,
  watch,
  nextTick,
  onMounted,
  onUnmounted,
  useState: useStateShim,
  useI18n: () => ({ locale: ref("tc"), t: translate }),
  useTranslation: () => ({
    getTranslatedText: (_scope: string, _key: string, fallback: string) => fallback,
  }),
  useGameIcon: () => ({
    color: () => "",
    artCost: () => "",
    specialTarget: () => "",
    keyword: () => "",
  }),
  useClipboard: () => ({ copy: () => {}, copied: ref(false), isSupported: ref(true) }),
});

// The real toggle module — its `useState` is the shim above. Stubbing it would make these
// tests about a mock rather than about the composable the components actually read.
const { useShowOriginal } = await import("../app/composables/useShowOriginal");
Object.assign(globalThis, { useShowOriginal });

vi.mock("vue-sonner", () => ({
  toast: { warning: () => {}, error: () => {}, success: () => {} },
}));

/**
 * The component, registered under the name **Nuxt would derive from its filename**.
 *
 * `pathPrefix: false` means the folder contributes nothing, so the registered name is the
 * basename — computed here rather than written out, so that renaming the file without
 * updating the call sites fails these tests instead of quietly passing.
 */
// Resolved from the repo rather than from `import.meta.url`: Vitest rewrites that during
// transform, and the rewritten value is not this file's location on disk.
const CARD_LIST_DIR = resolve(process.cwd(), "app/components/card-list");

/**
 * Read off disk rather than written out: the name has to *come from* the filename, or a
 * rename that breaks the app would leave these tests passing.
 */
const AUTO_IMPORT_NAME = readdirSync(CARD_LIST_DIR)
  .find((file) => file.endsWith("OriginalText.vue"))
  ?.replace(/\.vue$/, "");

const CardListOriginalText = (await import(
  "../app/components/card-list/CardListOriginalText.vue"
)).default;

const autoImports = { [AUTO_IMPORT_NAME as string]: CardListOriginalText };

const card = {
  id: "1",
  card_number: "hSD01-001",
  card_type_code: "oshiCharacter",
  rarity_code: "OSR",
  image_key: "hSD01/hSD01-001_OSR",
  name: "Tokino Sora",
  tags: [],
  arts: [{ name: "Sky Blue Melody", effect: "…", cost_types: [] }],
  keyword: { type: "gift", type_code: "gift", name: "Singing", effect: "…" },
  oshi_skill: { timing_code: "art", name: "Sora's Encore", effect: "…" },
  sp_oshi_skill: { timing_code: "art", name: "Dreaming Days", effect: "…" },
  original: {
    name: "ときのそら",
    art_names: ["蒼の旋律"],
    keyword_name: "歌",
    oshi_skill_name: "そらのアンコール",
    sp_oshi_skill_name: "ドリーミングデイズ",
  },
} as unknown as Card;

const stubs = {
  Badge: { template: "<span><slot /></span>" },
  Button: { template: "<button><slot /></button>" },
  Image: { template: "<div />" },
  CardDataRowsBlockItem: { template: "<div><slot /></div>" },
};

async function mountNameBlock() {
  const component = (await import("../app/components/card-list/CardDataNameBlock.vue"))
    .default;
  return mount(component, {
    props: {
      id: card.id,
      name: card.name ?? "",
      number: card.card_number,
      originalName: card.original?.name,
    },
    global: { components: autoImports, stubs, mocks: { $t: translate } },
  });
}

async function mountDetailBlocks() {
  const component = (await import("../app/components/card-list/CardDataDetailBlocks.vue"))
    .default;
  return mount(component, {
    props: { item: card },
    global: { components: autoImports, stubs, mocks: { $t: translate } },
  });
}

beforeEach(() => {
  stateStore.clear();
  // The toggle is *persisted*, and `happy-dom` keeps one `localStorage` for the whole
  // file — so without this a test that turns it on leaves it on for every test after it,
  // via the `onMounted` read-back rather than via the state shim.
  localStorage.clear();
});

describe("the source names render where the toggle promises them (#61)", () => {
  /**
   * The contract itself, stated once: the registered name *is* the filename, and it is
   * the name the templates write. Everything below would still pass if these two drifted
   * apart and this file happened to register the component under the call sites' spelling
   * anyway — so the equality is asserted rather than assumed.
   */
  it("registers under the name the call sites use", () => {
    expect(AUTO_IMPORT_NAME).toBe("CardListOriginalText");
  });

  it("shows the card's source name in the name block", async () => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountNameBlock();
    await nextTick();

    expect(wrapper.text()).toContain("ときのそら");
  });

  /**
   * The four labels in the detail blocks, which are what the dialog and the card page
   * show below the name. All four were dead for the same single reason.
   */
  it.each([
    ["oshi skill", "そらのアンコール"],
    ["SP oshi skill", "ドリーミングデイズ"],
    ["keyword", "歌"],
    ["art", "蒼の旋律"],
  ])("shows the source %s name", async (_label, expected) => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountDetailBlocks();
    await nextTick();

    expect(wrapper.text()).toContain(expected);
  });

  /**
   * The bug's exact signature, pinned directly.
   *
   * An unresolved component still renders — as a custom element carrying its props as
   * attributes. Asserting on the *text* above would not have caught it if the element had
   * happened to inherit a slot, so this checks the tag itself is gone. It is the
   * difference between "the data arrived" and "the reader can see it".
   */
  it("resolves to a real element, not an inert custom tag", async () => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountNameBlock();
    await nextTick();

    expect(wrapper.html()).not.toContain("<cardlistoriginaltext");
    expect(wrapper.find("span[lang='ja']").text()).toBe("ときのそら");
  });

  it("stays hidden while the toggle is off", async () => {
    const wrapper = await mountNameBlock();
    await nextTick();

    expect(wrapper.text()).toContain("Tokino Sora");
    expect(wrapper.text()).not.toContain("ときのそら");
  });

  /**
   * `original` carries only the fields that actually differ, so an absent one is the
   * common case — the `ja` locale and every untranslated label at once.
   */
  it("says nothing when a card has no source name to show", async () => {
    useShowOriginal().enabled.value = true;
    const component = (await import("../app/components/card-list/CardDataNameBlock.vue"))
      .default;
    const wrapper = mount(component, {
      props: {
        id: card.id,
        name: "ときのそら",
        number: card.card_number,
        originalName: undefined,
      },
      global: { components: autoImports, stubs, mocks: { $t: translate } },
    });
    await nextTick();

    expect(wrapper.find("span[lang='ja']").exists()).toBe(false);
  });
});
