/**
 * @vitest-environment happy-dom
 *
 * The release notes group their entries, and lose none of them (D28).
 *
 * `/changelog` used to render one badge per entry, so v2.0.0 showed eight badges carrying
 * three distinct words. Grouping them means the page no longer renders entries in file
 * order — and *that* is the reason this file exists. The failure mode of a grouping bug is
 * not a badge in the wrong place, which anyone would see; it is an entry silently dropped
 * on the floor, on a page nobody reads closely because they already know what it says.
 *
 * So the load-bearing assertion here is the count and the text of the entries, not the
 * chrome around them. It mounts, because the bug would be in what is rendered rather than
 * in what is computed (D24), and it asserts against the **real** `content/changelog.json`
 * via the `#content` alias rather than a fixture: a fixture would let the page and the
 * file it ships with disagree, which is exactly the state the import is meant to prevent.
 */

import { mount } from "@vue/test-utils";
import { computed, ref } from "vue";
import { describe, expect, it } from "vitest";

import changelog from "#content/changelog.json";

/** `$t` returning the key, so a missing translation is visible as the raw key. */
const translate = (key: string) => key;

Object.assign(globalThis, {
  ref,
  computed,
  useI18n: () => ({ locale: ref("en"), t: translate }),
  useLocalePath: () => (path: string) => `/en${path}`,
  useRuntimeConfig: () => ({ public: { siteUrl: "https://example.test" } }),
  useSeoMeta: () => {},
  useHead: () => {},
});

const stubs = {
  Button: { template: "<button><slot /></button>" },
  NuxtLink: { template: "<a><slot /></a>" },
};

async function renderPage() {
  const component = (await import("../app/pages/changelog.vue")).default;
  return mount(component, { global: { stubs, mocks: { $t: translate } } });
}

/** The kind labels the page rendered, in document order, as bare kinds. */
function renderedKinds(html: string): string[] {
  return [...html.matchAll(/changelog\.kind\.(added|changed|fixed)/g)].map((m) => m[1]!);
}

const releases = changelog.releases as { version: string; changes: { kind: string; text: string }[] }[];

describe("the release notes group their entries by kind", () => {
  it("renders each kind at most once per release", async () => {
    // The regression this replaces: v2.0.0 has eight changes across three kinds and
    // rendered eight badges. Asserted against the file rather than a literal 3, so a
    // release that genuinely uses one kind does not fail here.
    const wrapper = await renderPage();
    const kinds = renderedKinds(wrapper.html());

    const expected = releases.flatMap((release) => [
      ...new Set(release.changes.map((change) => change.kind)),
    ]);

    expect(kinds).toHaveLength(expected.length);
  });

  it("orders the groups Added, Changed, Fixed within every release", async () => {
    const wrapper = await renderPage();
    const kinds = renderedKinds(wrapper.html());

    // Walk the flat list release by release: each release contributes its own distinct
    // kinds, and each of those runs must be in `KIND_ORDER`.
    const order = ["added", "changed", "fixed"];
    let cursor = 0;

    for (const release of releases) {
      const distinct = [...new Set(release.changes.map((change) => change.kind))];
      const actual = kinds.slice(cursor, cursor + distinct.length);
      cursor += distinct.length;

      const sorted = [...actual].sort((a, b) => order.indexOf(a) - order.indexOf(b));
      expect(actual, `v${release.version} groups out of order`).toEqual(sorted);
    }
  });

  it("keeps every entry, which is what a grouping bug would take", async () => {
    // The one that matters. Grouping reorders, and a reorder that drops an entry looks
    // exactly like a release that had fewer things in it.
    const wrapper = await renderPage();
    const text = wrapper.text();

    for (const release of releases) {
      for (const change of release.changes) {
        expect(text, `v${release.version} lost: ${change.text.slice(0, 40)}…`).toContain(
          change.text,
        );
      }
    }
  });

  it("renders one list item per entry", async () => {
    // Belt to the previous test's braces: `toContain` would still pass if two entries were
    // concatenated into one `<li>`, which is a plausible shape for a bad `join`.
    const wrapper = await renderPage();
    const total = releases.reduce((sum, release) => sum + release.changes.length, 0);

    expect(wrapper.findAll("li")).toHaveLength(total);
  });
});
