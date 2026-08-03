/**
 * Unit tests for the pure modules (ADR 0006, Q5).
 *
 * Deliberately **not** `@nuxt/test-utils` and not a DOM environment. What is tested here
 * is the logic the four refactors extract — the filter shape and its `toApiParams`, the
 * deck's section routing and size limits, the deck-list join, and the deck-code
 * round-trip — all of which are plain functions by design. A component harness would add
 * a large dependency to verify nothing these tests do not already cover.
 *
 * The bug class this exists for is real: v1 shipped
 * `CARD_BLOOM_LEVELS = ["debut","1st","2nd","spot"]` against data that says
 * `first`/`second`, and a `Card` union missing the `HR` rarity that left 24 cards
 * unfilterable in the live UI. Typecheck catches the second; a `toApiParams` test catches
 * the first.
 *
 * **That last paragraph used to say templates were an accepted gap** — verified by running
 * the site, with a component harness declined as a large dependency covering nothing the
 * pure tests missed. F-019 disproved it. `CardListViewAPI` needed one prop
 * (`emit-update`) for `RecycleScroller` to emit `scroll-end`; without it the homepage
 * showed 200 of 2,448 cards and no test could see the difference, because a prop that was
 * never passed lives only in a template. The gap was not that templates are untested — it
 * is that *wiring* was, and wiring is where a component's behaviour actually lives.
 *
 * So `component.test.ts` mounts, with `happy-dom` and `@vue/test-utils`. Two devDeps, no
 * browser: `make check` stays the pre-commit hook, and end-to-end coverage is still
 * declined for the reason originally given.
 */

import vue from "@vitejs/plugin-vue";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Needed only by the component tests, but harmless to the rest: without it Vitest
  // cannot parse an SFC at all.
  plugins: [vue()],
  resolve: {
    alias: {
      "~": fileURLToPath(new URL("./app", import.meta.url)),
      "@": fileURLToPath(new URL("./app", import.meta.url)),
      "@holo/schema/enums": fileURLToPath(
        new URL("../../packages/schema/dist/enums.ts", import.meta.url),
      ),
      // Mirrors the `alias` block in `nuxt.config.ts`, which Vitest does not read. The two
      // must agree: an alias in only one place resolves in the build and fails in the
      // tests, or the reverse — and the reverse is the one that ships broken.
      "#content": fileURLToPath(new URL("../../content", import.meta.url)),
    },
  },
  test: {
    // `node` remains the default — the pure tests are the majority and do not need a DOM.
    // Only the files that mount pay for one, via a `@vitest-environment` docblock.
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
