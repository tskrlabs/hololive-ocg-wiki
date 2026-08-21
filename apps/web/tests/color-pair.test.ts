/**
 * @vitest-environment happy-dom
 *
 * How a dual-colour card's colour row renders (ADR 0013, #22).
 *
 * The contract tests assert `COLOR_PAIRS` is well-formed and the API tests assert the
 * filter binds two codes. Neither can see what a reader actually gets, which is the whole
 * point of the change: two full-size badges instead of one blurry composite, under the
 * name the game gives the pair.
 *
 * #22's original defect is *unrepresentable* now rather than fixed — `type_blue_red.webp`
 * was 88x108 where every sibling is 330x410, and the asset is deleted. A regression would
 * have to reintroduce the file, so the guard is asserting no `type_*_*.webp` composite is
 * ever requested.
 */

import { config, mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it } from "vitest";

// The block calls Nuxt auto-imported composables, which do not resolve outside Nuxt.
// Defined on `globalThis` before the component is imported, matching how the component
// suite handles the same problem — the alternative is importing them explicitly in app
// code purely to satisfy a test, which is the tail wagging the dog.
Object.assign(globalThis, {
  useTranslation: () => ({ getTranslatedText: (value: unknown) => value }),
  useGameIcon: () => ({
    color: (code: string) => `/icons/type_${code}.webp`,
    artCost: (code: string) => `/icons/arts_${code}.webp`,
  }),
  useShowOriginal: () => ({ enabled: ref(false) }),
});

const { default: CardDataRowsBlock } = await import(
  "../app/components/card-list/CardDataRowsBlock.vue"
);

config.global.mocks = { $t: (key: string) => key };

/** The parts of a Card this block reads. Everything else renders nothing. */
function card(color_codes: string[]) {
  return {
    id: "1",
    card_number: "hBP08-060",
    locale: "en",
    color_codes,
    image_key: "hBP08/hBP08-060_R",
  };
}

function mountBlock(color_codes: string[]) {
  return mount(CardDataRowsBlock, {
    props: { item: card(color_codes) as never },
    global: {
      stubs: {
        // The block is mostly rows we do not care about; only the colour row is under
        // test, and `Image` is what carries the icon URL.
        CardDataRowsBlockItem: { template: "<div><slot /></div>" },
        Image: {
          props: ["src"],
          template: "<img :src='src' />",
        },
        Badge: { template: "<span><slot /></span>" },
        UseClipboard: { template: "<div><slot /></div>" },
        CardListOriginalText: { template: "<span />" },
      },
    },
  });
}

const icons = (wrapper: ReturnType<typeof mountBlock>) =>
  wrapper.findAll("img").map((img) => img.attributes("src"));

describe("a dual-colour card's colour row", () => {
  it("renders one full-size badge per colour, never a composite asset", () => {
    // The #22 guard. `type_blue_red.webp` was a quarter the size of its siblings and is
    // deleted; any composite name here means it came back.
    const rendered = icons(mountBlock(["blue", "red"]));

    expect(rendered).toEqual(["/icons/type_blue.webp", "/icons/type_red.webp"]);
    for (const src of rendered) {
      expect(src).not.toMatch(/type_[a-z]+_[a-z]+\.webp/);
    }
  });

  it("keeps the printed order rather than sorting", () => {
    // miComet prints red-then-blue where FUWAMOCO prints blue-then-red. Sorting here
    // would silently reorder the badges on one of the two.
    expect(icons(mountBlock(["red", "blue"]))).toEqual([
      "/icons/type_red.webp",
      "/icons/type_blue.webp",
    ]);
  });

  it("labels the pair with the name the game gives it", () => {
    // Two badges, one name: `青赤` is a colour identity, so the row reads "Blue-Red"
    // rather than "Blue, Red". `$t` is mocked to echo its key.
    expect(mountBlock(["blue", "red"]).text()).toContain("colors.blue_red");
    expect(mountBlock(["white", "green"]).text()).toContain("colors.white_green");
  });

  it("names the pair identically whichever way round it is printed", () => {
    expect(mountBlock(["red", "blue"]).text()).toContain("colors.blue_red");
  });
});

describe("a single-colour card's colour row", () => {
  it("renders one badge and names the colour", () => {
    const wrapper = mountBlock(["purple"]);

    expect(icons(wrapper)).toEqual(["/icons/type_purple.webp"]);
    expect(wrapper.text()).toContain("colors.purple");
  });

  it("falls back to listing colours for a pair with no name of its own", () => {
    // Not a combination the game names, and not one that occurs today — but the
    // component must not render a blank label if the data ever grows one.
    const wrapper = mountBlock(["purple", "yellow"]);

    expect(icons(wrapper)).toEqual([
      "/icons/type_purple.webp",
      "/icons/type_yellow.webp",
    ]);
    expect(wrapper.text()).toContain("colors.purple, colors.yellow");
  });
});
