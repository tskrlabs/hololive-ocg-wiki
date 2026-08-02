/**
 * @vitest-environment happy-dom
 *
 * `/status`, and specifically the sentence it chooses (ADR 0009 D26).
 *
 * The page's whole job is to keep two vocabularies apart: what *our database* did and
 * what the *official card list* did. Before D26 it had only the first, so after the
 * translation rework it reported `changed: 2463` and a reader could only conclude the
 * game had reissued every card it prints.
 *
 * These mount rather than test a pure function, because the failure is in what is
 * rendered (D24). `reseedNote` returning the right key proves nothing if the template
 * renders it under a heading that contradicts it, and the cap is only a bug once a list
 * is on screen claiming to be complete.
 */

import { flushPromises, mount } from "@vue/test-utils";
import { computed, defineComponent, h, ref, Suspense } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StatusReport } from "../app/types/status";

const translate = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

/** What `/api/status` returns for the test being run. Written per test. */
let payload: StatusReport | null = null;

Object.assign(globalThis, {
  ref,
  computed,
  useI18n: () => ({ locale: ref("en"), t: translate }),
  useSeoMeta: () => {},
  useHead: () => {},
  useLocalePath: () => (path: string) => `/en${path}`,
  useAsyncData: async (_key: string, handler: () => Promise<unknown>) => ({
    data: ref(await handler()),
    error: ref(null),
  }),
});

Object.assign(globalThis, {
  $fetch: () => Promise.resolve(payload),
});

/** A report with everything quiet, which each test then edits into its own case. */
function report(overrides: Partial<StatusReport> = {}): StatusReport {
  return {
    generated_at: "2026-08-02T00:00:00Z",
    built_at: "2026-08-01T00:00:00Z",
    mode: "diff",
    counts: {
      total: 2463,
      new: 0,
      changed: 0,
      qa_updated: 0,
      unchanged: 2463,
      removed: 0,
      missing_from_build: 0,
      source_added: 0,
      source_changed: 0,
      faq_changed: 0,
    },
    list_cap: 100,
    new: [],
    changed: [],
    qa_updated: [],
    source_added: [],
    source_changed: [],
    faq_changed: [],
    removed: [],
    ...overrides,
  };
}

/** `count` entries that look like real cards, so links can be asserted on. */
function cards(count: number, from = 1) {
  return Array.from({ length: count }, (_, i) => ({
    id: String(from + i),
    card_number: `hSD01-${String(from + i).padStart(3, "0")}`,
    image_key: `hSD01/hSD01-${String(from + i).padStart(3, "0")}_C`,
    name: `Card ${from + i}`,
  }));
}

/**
 * Mount the page inside `<Suspense>`.
 *
 * The page awaits `useAsyncData` at the top level of `<script setup>`, which makes its
 * setup async — mounting it directly renders the empty placeholder and every assertion
 * reads `''`. Suspense plus a `flushPromises` is what actually gets the resolved markup.
 */
async function mountStatus() {
  const page = (await import("../app/pages/status.vue")).default;
  const wrapper = mount(
    defineComponent({
      render: () => h(Suspense, null, { default: () => h(page) }),
    }),
    {
      global: {
        stubs: {
          Button: { template: "<button><slot /></button>" },
          NuxtLink: {
            props: ["to"],
            template: `<a :href="to"><slot /></a>`,
          },
        },
        mocks: { $t: translate },
      },
    },
  );
  await flushPromises();
  return wrapper;
}

describe("the page separates what we did from what the source did", () => {
  beforeEach(() => {
    payload = null;
    vi.resetModules();
  });

  it("says the rebuild was ours when rows churned and the source did not", async () => {
    // The translation rework, exactly: every card rewritten, nothing published.
    payload = report({
      counts: { ...report().counts, changed: 2463, unchanged: 0 },
      changed: cards(100),
    });

    const wrapper = await mountStatus();
    const html = wrapper.html();

    expect(html).toContain("status.reseed.ours");
    expect(html).toContain("status.source.quiet");
    // The number is told, not hidden — that is the point of saying it at all.
    expect(html).toContain("2,463");
    // ...but never as a source change.
    expect(html).not.toContain("status.source.edited");
  });

  it("leads with the source when the official list published something", async () => {
    payload = report({
      counts: {
        ...report().counts,
        new: 3,
        changed: 5,
        unchanged: 2455,
        source_added: 3,
        source_changed: 5,
        faq_changed: 2,
      },
      source_added: cards(3),
      source_changed: cards(5, 10),
      faq_changed: cards(2, 20),
    });

    const wrapper = await mountStatus();
    const html = wrapper.html();

    expect(html).toContain("status.source.added");
    expect(html).toContain("status.source.edited");
    expect(html).toContain("status.source.faq");
    expect(html).not.toContain("status.source.quiet");
    // Mixed, not "ours": the source did move, so we cannot claim the rebuild was only us.
    expect(html).toContain("status.reseed.mixed");
  });

  it("hides a group the source did not touch", async () => {
    payload = report({
      counts: { ...report().counts, new: 4, unchanged: 2459, source_added: 4 },
      source_added: cards(4),
    });

    const wrapper = await mountStatus();
    const html = wrapper.html();

    expect(html).toContain("status.source.added");
    // An "0 cards edited" row is noise: a group with nothing in it is not a fact.
    expect(html).not.toContain("status.source.edited");
    expect(html).not.toContain("status.source.faq");
  });

  it("links every listed card to its own page", async () => {
    payload = report({
      counts: { ...report().counts, new: 2, unchanged: 2461, source_added: 2 },
      source_added: cards(2),
    });

    const wrapper = await mountStatus();
    const links = wrapper.findAll("a").map((a) => a.attributes("href"));

    // `image_key` *is* the URL's {set}/{stem} (D6), so no lookup is needed to build it.
    expect(links).toContain("/en/card/hSD01/hSD01-001_C");
    expect(links).toContain("/en/card/hSD01/hSD01-002_C");
  });

  it("renders a card with no image key as text, not a dead link", async () => {
    payload = report({
      counts: { ...report().counts, new: 1, unchanged: 2462, source_added: 1 },
      source_added: [
        { id: "9", card_number: "hSD01-009", image_key: null, name: "Keyless" },
      ],
    });

    const wrapper = await mountStatus();

    expect(wrapper.html()).toContain("Keyless");
    expect(wrapper.findAll("a").map((a) => a.attributes("href"))).not.toContain(
      "/en/card/null",
    );
  });
});

describe("a capped list says so", () => {
  beforeEach(() => {
    payload = null;
    vi.resetModules();
  });

  it("reports the cards it is not showing", async () => {
    // A large set release: 600 cards changed at the source, 100 in the artifact.
    payload = report({
      counts: { ...report().counts, changed: 600, unchanged: 1863, source_changed: 600 },
      source_changed: cards(100),
    });

    const wrapper = await mountStatus();
    const html = wrapper.html();

    // The count is the truth; the list is a sample. Reading the total off the list's
    // length is the bug the cap would otherwise introduce.
    expect(html).toContain("600");
    expect(html).toContain("status.source.more");
    expect(html).toContain('{"count":"500"}');
  });

  it("stays silent about a list that fits", async () => {
    payload = report({
      counts: { ...report().counts, changed: 3, unchanged: 2460, source_changed: 3 },
      source_changed: cards(3),
    });

    expect((await mountStatus()).html()).not.toContain("status.source.more");
  });
});

describe("an artifact written before D26", () => {
  beforeEach(() => {
    payload = null;
    vi.resetModules();
  });

  it("renders as a quiet update rather than throwing", async () => {
    // No `source_*` anywhere — the shape `seed` wrote before this decision existed. The
    // page cannot know what the source did, and "quiet" is the honest rendering of that.
    const legacy = report();
    delete legacy.counts.source_added;
    delete legacy.counts.source_changed;
    delete legacy.counts.faq_changed;
    delete legacy.source_added;
    delete legacy.source_changed;
    delete legacy.faq_changed;
    payload = legacy;

    const wrapper = await mountStatus();

    expect(wrapper.html()).toContain("status.source.quiet");
    expect(wrapper.html()).toContain("status.validInDB");
  });
});
