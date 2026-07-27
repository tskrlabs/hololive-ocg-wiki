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
 * No template is asserted to render — a known, accepted gap. Templates are verified by
 * running the site (`make dev`), and end-to-end coverage was weighed and declined:
 * `make check` is the pre-commit hook, and a browser is the most brittle thing that
 * could live in it.
 */

import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "~": fileURLToPath(new URL("./app", import.meta.url)),
      "@": fileURLToPath(new URL("./app", import.meta.url)),
      "@holo/schema/enums": fileURLToPath(
        new URL("../../packages/schema/dist/enums.ts", import.meta.url),
      ),
    },
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
