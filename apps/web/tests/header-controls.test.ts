/**
 * @vitest-environment happy-dom
 *
 * Header and footer controls that must not be mistaken for one another.
 *
 * Three defects, all of the same shape: a control that *looks* like it does something it
 * does not, which no pure test can see because the evidence is a rendered icon or a
 * rendered absence.
 *
 * - **Density toggled nothing on two of four pages.** `useCardDensity` is read only by
 *   the card grid, which exists on `index` alone, so on the card page and the deck page
 *   the header button flipped `aria-pressed`, swapped its icon, and changed nothing on
 *   screen. A control that visibly responds and has no effect is worse than a missing
 *   one: it teaches that the control is broken.
 * - **Show-original and the language switcher carried the same `Languages` glyph.** #51
 *   gave each an `.sr-only` name, which fixed it for a screen reader and left the visual
 *   collision untouched — a name a mouse user cannot hear does not help them tell two
 *   identical buttons apart.
 * - **The two deck controls read as duplicates.** "Deck" and "Decks" differ by one letter
 *   in English and were *the same string* in `tc` (both 牌組).
 *
 * These mount, because in every case the bug is in what is rendered rather than in what
 * is computed (D24).
 */

import { mount } from "@vue/test-utils";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const translate = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

/** The route the header thinks it is on. Written per test. */
const routeName = ref<string | null>("index");

const stateStore = new Map<string, unknown>();
function useStateShim<T>(key: string, init: () => T) {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()));
  return stateStore.get(key) as ReturnType<typeof ref<T>>;
}

Object.assign(globalThis, {
  ref,
  computed,
  watch,
  onMounted,
  onUnmounted,
  useState: useStateShim,
  useI18n: () => ({ locale: ref("en"), t: translate, locales: ref([]) }),
  useRoute: () => ({ name: routeName.value }),
  useRouteBaseName: () => () => routeName.value,
  useSwitchLocalePath: () => (code: string) => `/${code}/`,
});

vi.mock("vue-sonner", () => ({
  toast: { warning: () => {}, error: () => {}, success: () => {} },
}));

/**
 * Only the two composables the mounted controls actually read.
 *
 * ⚠️ `useDecks` was here and is deliberately gone. Nothing this file mounts uses it — it
 * belongs to `AppFooterDeckButton`, which is not among the controls below — and importing
 * it installed the real deck store, whose module-level `watch` and `onMounted` outlive
 * the test that created them. Vitest shares one `globalThis` per worker, so that watcher
 * then observed state other files were writing, and the suite failed roughly one run in
 * seven with no failure reproducible in isolation. Import what is mounted, nothing more.
 */
const { useCardDensity } = await import("../app/composables/useCardDensity");
const { useShowOriginal } = await import("../app/composables/useShowOriginal");
Object.assign(globalThis, { useCardDensity, useShowOriginal });

/** Which lucide component a button rendered, by the class lucide stamps on its `<svg>`. */
function iconNames(html: string): string[] {
  return [...html.matchAll(/class="[^"]*\blucide-([a-z0-9-]+)\b/g)].map((m) => m[1]!);
}

/**
 * The controls under test, imported statically.
 *
 * A computed path (`import(path)`) cannot be analysed by Vite and resolves at runtime
 * against the wrong root, so the components are listed here and looked up by key.
 */
const CONTROLS = {
  density: () => import("../app/components/parials/AppDensitySwitcher.vue"),
  original: () => import("../app/components/parials/AppOriginalSwitcher.vue"),
  language: () => import("../app/components/parials/AppLanguageSwitcher.vue"),
} as const;

async function mountControl(key: keyof typeof CONTROLS) {
  const component = (await CONTROLS[key]()).default;
  return mount(component, {
    global: {
      stubs: { Button: { template: "<button><slot /></button>" } },
      mocks: { $t: translate },
    },
  });
}

describe("the density switcher renders only where density does something", () => {
  beforeEach(() => {
    stateStore.clear();
    routeName.value = "index";
  });

  it("is present on the card list", async () => {
    const wrapper = await mountControl("density");
    expect(wrapper.find("button").exists()).toBe(true);
  });

  it("is absent on the card page and the deck page", async () => {
    // The two routes where `useCardDensity` has no reader. The deck page is included
    // deliberately: it *has* a compact mode, but a local ref with its own toggle in the
    // page body, which this button never drove.
    for (const name of ["card-set-stem", "deck-code"]) {
      routeName.value = name;
      const wrapper = await mountControl("density");
      expect(wrapper.find("button").exists(), name).toBe(false);
    }
  });

  it("is absent rather than disabled, so nothing invites a click", async () => {
    // A disabled control still says "this page has a density"; an absent one says the
    // page has nothing to set. The latter is true.
    routeName.value = "deck-code";
    const wrapper = await mountControl("density");
    expect(wrapper.html().trim()).toBe("<!--v-if-->");
  });
});

describe("no two adjacent controls share an icon", () => {
  beforeEach(() => {
    stateStore.clear();
    routeName.value = "index";
  });

  it("gives show-original and the language switcher different glyphs", async () => {
    // The regression: both were `Languages`, so the header showed the same icon twice and
    // only a screen reader could tell them apart.
    const original = await mountControl("original");
    const language = await mountControl("language");

    const originalIcons = iconNames(original.html());
    const languageIcons = iconNames(language.html());

    expect(originalIcons.length).toBeGreaterThan(0);
    expect(languageIcons.length).toBeGreaterThan(0);
    for (const icon of originalIcons) {
      expect(languageIcons, `${icon} appears in both`).not.toContain(icon);
    }
  });

  it("keeps Languages on the control that actually switches language", async () => {
    const language = await mountControl("language");
    expect(iconNames(language.html())).toContain("languages");
  });
});
