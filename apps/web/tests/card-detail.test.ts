/**
 * @vitest-environment happy-dom
 *
 * `CardDetail` is one component with two containers (D15, #39).
 *
 * The extraction it comes from is a **refactor** — the dialog rendered these five blocks
 * before and renders them now — so the property worth pinning is not what the blocks do
 * (they are unchanged and already covered where they live) but that the seam holds:
 *
 * - the dialog still shows the whole card, so nothing was dropped in the move
 * - `CardDetail` carries no container decisions, so the page can place it differently
 *
 * That second one is the reason this test exists at all. The failure it guards against is
 * a width or a scroll region creeping back into the shared component, at which point the
 * card page inherits the dialog's geometry and the two stop being containers around one
 * thing. It is the same class of drift `localize()`'s golden files guard: two renderings
 * of one card that agree today and need a reason to keep agreeing.
 */

import { config, mount } from "@vue/test-utils";
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  onMounted,
  onUnmounted,
  nextTick,
  shallowRef,
  useState: useStateShim,
  useI18n: () => ({ locale: ref("tc"), t: translate }),
  useCardImage: () => (key: string) => `https://img.example/${key}.webp`,
  useCardQuery: () => ({ getCardsByCardNumber: async () => [] }),
});

vi.mock("vue-sonner", () => ({
  toast: { warning: () => {}, error: () => {}, success: () => {} },
}));

const card = {
  id: "1",
  card_number: "hSD01-001",
  card_type_code: "oshiCharacter",
  rarity_code: "OSR",
  image_key: "hSD01/hSD01-001_OSR",
  name: "ときのそら",
  original: { name: "ときのそら" },
} as unknown as Card;

/** The five data blocks, stubbed so this test is about the composition, not their guts. */
const blockStubs = {
  CardDataNameBlock: { template: "<div class='b-name' />" },
  CardDataRowsBlock: { template: "<div class='b-rows' />" },
  CardDataDetailBlocks: { template: "<div class='b-detail' />" },
  CardDataQnaBlocks: { template: "<div class='b-qna' />" },
  CardDataSameNumberBlock: { template: "<div class='b-same' />" },
  Image: { template: "<div class='b-image' />" },
};

async function mountDetail(variant: "dialog" | "page" = "dialog") {
  const component = (await import("../app/components/card-list/CardDetail.vue")).default;
  return mount(component, {
    props: { item: card, variant },
    global: { stubs: blockStubs, mocks: { $t: translate } },
  });
}

async function mountDialog() {
  const component = (
    await import("../app/components/card-list/CardItemDialogContent.vue")
  ).default;
  // `CardDetail` is a Nuxt auto-import in the app; outside Nuxt it must be registered,
  // and it is the *real* component here rather than a stub — the point of this test is
  // that the dialog reaches the blocks through it.
  const CardDetail = (await import("../app/components/card-list/CardDetail.vue")).default;

  return mount(component, {
    props: { item: card },
    global: {
      components: { CardDetail },
      stubs: {
        ...blockStubs,
        DialogContent: { template: "<div><slot /></div>" },
        DialogHeader: { template: "<div><slot /></div>" },
        DialogTitle: { template: "<h2><slot /></h2>" },
        DialogDescription: { template: "<p><slot /></p>" },
        DialogFooter: { template: "<div><slot /></div>" },
        DialogClose: { template: "<div><slot /></div>" },
        ScrollArea: { template: "<div class='scroll'><slot /></div>" },
        Button: { template: "<button><slot /></button>" },
      },
      mocks: { $t: translate },
    },
  });
}

beforeEach(() => {
  stateStore.clear();
  config.global.renderStubDefaultSlot = true;
});

describe("CardDetail is the card, without its container (#39)", () => {
  it("renders all five data blocks plus the art", async () => {
    const wrapper = await mountDetail();

    for (const block of [".b-name", ".b-rows", ".b-detail", ".b-qna", ".b-same"]) {
      expect(wrapper.find(block).exists(), block).toBe(true);
    }
    expect(wrapper.find(".b-image").exists()).toBe(true);
  });

  it("owns no width, no height cap and no scroll region", async () => {
    // The container decides those. If one leaks in here, the card page silently
    // inherits the dialog's geometry — which is exactly what having one shared
    // component was meant to prevent.
    const markup = (await mountDetail()).html().replace(/<!--[\s\S]*?-->/g, "");

    expect(markup).not.toMatch(/max-h-\[|dvh|overflow-y-auto|max-w-(sm|md|lg|xl|\d)/);
  });

  it("renders the same blocks in both containers", async () => {
    // The variant is a behaviour hint for later (the page expands what the dialog keeps
    // behind an accordion), not a different card. Both must show the whole card today.
    const dialog = await mountDetail("dialog");
    const page = await mountDetail("page");

    for (const block of [".b-name", ".b-rows", ".b-detail", ".b-qna", ".b-same"]) {
      expect(page.find(block).exists(), block).toBe(true);
      expect(dialog.find(block).exists(), block).toBe(true);
    }
  });
});

describe("the dialog still shows the whole card after the extraction (#39)", () => {
  it("renders CardDetail rather than its own copy of the blocks", async () => {
    const wrapper = await mountDialog();

    // Every block is present, reached through CardDetail.
    for (const block of [".b-name", ".b-rows", ".b-detail", ".b-qna", ".b-same"]) {
      expect(wrapper.find(block).exists(), block).toBe(true);
    }
  });

  it("keeps the chrome that makes it a dialog", async () => {
    // The half that did *not* move: a name for screen readers, a scroll region, a close
    // affordance, and the link out to the official card list.
    const wrapper = await mountDialog();

    expect(wrapper.find("h2").text()).toBe("ときのそら");
    expect(wrapper.find(".scroll").exists()).toBe(true);
    expect(wrapper.text()).toContain("Close");
    expect(wrapper.find("a[href*='hololive-official-cardgame.com']").exists()).toBe(true);
  });

  it("still caps its own height, which CardDetail must not do", async () => {
    // The complement of the assertion above: the geometry belongs to the container, and
    // this is where it should be.
    const wrapper = await mountDialog();
    expect(wrapper.html()).toMatch(/max-h-\[90dvh\]/);
  });
});
