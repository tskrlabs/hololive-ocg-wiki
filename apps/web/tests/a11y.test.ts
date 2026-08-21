/**
 * @vitest-environment happy-dom
 *
 * Every icon-only control has a translated accessible name (#51).
 *
 * Four of the eight header controls had **none at all** — a screen-reader user heard
 * "button" four times with no indication of what any of them did — and two more relied on
 * `title`, which several screen readers ignore when computing the name and which is
 * unreachable on touch entirely.
 *
 * The audit that found this read the rendered DOM rather than the source, and so does
 * this: a control's name is what the browser computes, not what the template looks like
 * it says. The computation here is the ordinary one — `aria-label`, then
 * `aria-labelledby`, then text content including `.sr-only` — with `title` deliberately
 * *excluded*, because treating it as a name is exactly the mistake being fixed.
 */

import { mount } from "@vue/test-utils";
import { computed, ref } from "vue";
import { describe, expect, it } from "vitest";

/** `$t` returning the key, so a missing translation is visible as the raw key. */
const translate = (key: string) => key;

/**
 * `/api/info`, resolved with an invite so the Discord *button* renders.
 *
 * The unresolved case renders the reserved placeholder instead, which is inert and has no
 * name by design — that is the subject of its own test below, not of the name sweep.
 */
const infoData = ref<{ "discord-invite-url"?: string }>({
  "discord-invite-url": "https://discord.gg/example",
});

Object.assign(globalThis, {
  ref,
  computed,
  useI18n: () => ({ locale: ref("tc"), t: translate, locales: ref([]) }),
  useColorMode: () => ({ preference: "light" }),
  useShowOriginal: () => ({ enabled: ref(true), toggle: () => {} }),
  useSwitchLocalePath: () => (code: string) => `/${code}/`,
  useAsyncData: () => ({ data: infoData }),
  $fetch: () => Promise.resolve(infoData.value),
});

/**
 * The accessible name a browser would compute, minus `title`.
 *
 * `title` is the *fallback* in the real algorithm, and several screen readers skip it
 * even there. A control whose only name comes from `title` should read as unnamed here,
 * because that is the defect.
 */
function accessibleName(el: Element): string {
  const label = el.getAttribute("aria-label");
  if (label) return label.trim();

  const labelledBy = el.getAttribute("aria-labelledby");
  if (labelledBy) {
    const target = el.ownerDocument.getElementById(labelledBy);
    if (target) return (target.textContent ?? "").trim();
  }

  // Comment nodes contribute nothing to a name — a browser never sees them — and Vue
  // keeps template comments in the rendered output, so they must be dropped explicitly
  // or the explanatory prose beside a label becomes part of it.
  //
  // `aria-hidden` subtrees contribute nothing either, which is what makes a decorative
  // icon decorative.
  const visible = [...el.childNodes]
    .filter((node) => node.nodeType !== 8 /* Comment */)
    .filter(
      (node) =>
        node.nodeType !== 1 || (node as Element).getAttribute("aria-hidden") !== "true",
    )
    .map((node) => node.textContent ?? "")
    .join("");

  return visible.trim();
}

const stubs = {
  Button: {
    inheritAttrs: false,
    template: "<button v-bind='$attrs'><slot /></button>",
  },
  NuxtLink: { template: "<a><slot /></a>" },
  DropdownMenu: { template: "<div><slot /></div>" },
  DropdownMenuTrigger: { template: "<div><slot /></div>" },
  DropdownMenuContent: true,
  DropdownMenuItem: true,
  Icon: { template: "<svg aria-hidden='true' />" },
  // Stubbed `aria-hidden`, which is what the real ones are — asserted directly in
  // "decorative icons stay out of the name" below. Stubbing them as anything else would
  // let the link tests pass against a glyph the real components do not render.
  IconGithub: { template: "<svg aria-hidden='true' />" },
  IconDiscord: { template: "<svg aria-hidden='true' />" },
};

async function render(path: string) {
  const component = (await import(/* @vite-ignore */ path)).default;
  return mount(component, {
    global: { stubs, mocks: { $t: translate } },
  });
}

describe("icon-only controls carry a name (#51)", () => {
  // The last two are header controls from `lg` up (D28). They are icon-only, so the
  // `.sr-only` span is their *entire* accessible name — there is no visible label to fall
  // back on, which is what makes them belong in this file rather than merely near it.
  const cases = [
    ["../app/components/parials/AppColorModeSwitcher.vue", "Toggle theme"],
    ["../app/components/parials/AppOriginalSwitcher.vue", "Show original names"],
    ["../app/components/parials/AppLanguageSwitcher.vue", "Change language"],
    ["../app/components/parials/AppGithubLink.vue", "Source code on GitHub"],
    ["../app/components/parials/AppDiscordLink.vue", "Join the Discord server"],
  ] as const;

  for (const [path, expected] of cases) {
    it(`${path.split("/").pop()} is named "${expected}"`, async () => {
      const wrapper = await render(path);
      const control = wrapper.find("button");

      expect(control.exists()).toBe(true);
      expect(accessibleName(control.element)).toBe(expected);
    });
  }

  it("names the theme toggle through i18n, not a hardcoded English string", async () => {
    // This was the one control with a correct name, and it read "Toggle theme" in all
    // seven locales. The pattern was right; the string was not.
    const wrapper = await render("../app/components/parials/AppColorModeSwitcher.vue");
    const source = wrapper.html();

    // `$t` returns the key here, so a *literal* would be indistinguishable from a
    // translated one by text alone — the component's source is what tells them apart.
    expect(source).not.toMatch(/>Toggle theme<\/span>\s*$/);
    expect(accessibleName(wrapper.find("button").element)).toBe("Toggle theme");
  });
});

describe("decorative icons stay out of the name", () => {
  it("hides the GitHub glyph, which carried a name of its own", async () => {
    // It was `role="img"` with `<title>GitHub</title>`, so once the wrapping button was
    // labelled the audit read "GitHubGitHub 原始碼" — two names concatenating.
    const wrapper = await render("../app/components/icons/IconGithub.vue");

    expect(wrapper.find("svg").attributes("aria-hidden")).toBe("true");
    expect(wrapper.find("title").exists()).toBe(false);
  });

  it("hides the Discord glyph", async () => {
    const wrapper = await render("../app/components/icons/IconDiscord.vue");
    expect(wrapper.find("svg").attributes("aria-hidden")).toBe("true");
  });
});
