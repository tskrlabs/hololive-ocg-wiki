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

/**
 * Tags, which are the one label that does *not* go through `CardListOriginalText` (#62).
 *
 * `original.tags` shipped in the payload for a month and no component read it — a quieter
 * version of the same failure as #61: the data arrives, the reader never sees it. It is
 * not a rare field either, so it is worth a test rather than an eyeball: **16 of 34 golden
 * fixture cards (~47%)** carry it in `en`/`es`/`id`/`ko`/`th`, 15 of 34 in `tc`.
 *
 * These mount the real block rather than asserting on the composable, because the whole
 * class of bug here is markup that is never reached.
 */
const tagCard = {
  ...card,
  tags: ["#JP", "#0th Gen", "#Singing"],
  original: { ...card.original, tags: ["#JP", "#0期生", "#歌"] },
} as unknown as Card;

async function mountRowsBlock(item: Card) {
  const component = (await import("../app/components/card-list/CardDataRowsBlock.vue"))
    .default;
  return mount(component, {
    props: { item },
    global: {
      components: autoImports,
      stubs: {
        ...stubs,
        // `UseClipboard` is a renderless component from `@vueuse/components`: it calls its
        // default slot with `{ copy, copied }`. Stubbed with those bound, so the tag
        // buttons render — without it the whole row is empty and every assertion below
        // would pass or fail for the wrong reason.
        UseClipboard: {
          template: "<div><slot :copy=\"() => {}\" :copied=\"false\" /></div>",
        },
      },
      mocks: { $t: translate },
    },
  });
}

describe("the source tag list renders as its own line (#62)", () => {
  it("shows every source tag when the toggle is on", async () => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountRowsBlock(tagCard);
    await nextTick();

    const source = wrapper.find("div[lang='ja']");
    expect(source.exists()).toBe(true);
    for (const tag of ["#JP", "#0期生", "#歌"]) {
      expect(source.text()).toContain(tag);
    }
  });

  /**
   * The contract, asserted rather than assumed: `localize()` emits the **whole** source
   * list or none of it, because a partially-shown tag list reads as a data error. So the
   * two rows are index-aligned and the same length, and `#JP` appearing on both sides is
   * correct output rather than a duplicate to suppress — 39% of tag pairs in `en` and 60%
   * in `tc` are identical, which is why this renders stacked instead of inline.
   */
  it("renders the source list at full length, including tags identical to their translation", async () => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountRowsBlock(tagCard);
    await nextTick();

    const source = wrapper.find("div[lang='ja']");
    expect(source.findAll("span")).toHaveLength(tagCard.original!.tags!.length);
    expect(source.text()).toContain("#JP");
  });

  it("stays hidden while the toggle is off", async () => {
    const wrapper = await mountRowsBlock(tagCard);
    await nextTick();

    expect(wrapper.text()).toContain("#0th Gen");
    expect(wrapper.find("div[lang='ja']").exists()).toBe(false);
  });

  /**
   * `original.tags` is `[]` — not absent — when the source and translation lists match,
   * which is what `localize()` emits for a card whose tags need no translating. An empty
   * row would draw a blank line under the tags for those cards.
   */
  it("draws nothing when the tags did not differ", async () => {
    useShowOriginal().enabled.value = true;
    const wrapper = await mountRowsBlock({
      ...tagCard,
      original: { ...tagCard.original, tags: [] },
    } as unknown as Card);
    await nextTick();

    expect(wrapper.find("div[lang='ja']").exists()).toBe(false);
  });
});
