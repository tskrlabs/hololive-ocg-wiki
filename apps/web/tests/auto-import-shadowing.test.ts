/**
 * A local binding must not shadow a Vue auto-import.
 *
 * **The bug this exists for shipped past a green `make check` twice.** `useDeckCards.ts`
 * had `for (const ref of cardRefs())`. Nuxt's auto-import scanner skips any identifier it
 * finds bound in scope, so it injected `computed` and `watch` but **not** `ref` — and the
 * deck panel died the moment it opened:
 *
 *     ReferenceError: ref is not defined
 *
 * Nothing in the fast path could see it:
 *
 * - `vue-tsc` resolves auto-imports from Nuxt's generated `.d.ts`, where `ref` is declared
 *   globally. It typechecks whether or not the runtime import is emitted.
 * - The unit tests `Object.assign(globalThis, { ref, computed, watch, … })` to run
 *   composables outside a Nuxt app, which supplies exactly the binding that is missing in
 *   the browser. `deck-panel.test.ts` mounted the component and passed.
 *
 * So the only two things that would catch it are a browser and `make check-site`, and the
 * latter is deliberately outside `make check` to keep the pre-commit hook fast
 * (ADR 0009 D24). Hence this guard.
 *
 * Scoped to the names that actually bite: the reactivity primitives a composable cannot
 * run without. Shadowing `computed` in a template-only `.vue` file is far less likely to
 * be silent, but the cost of including them is zero.
 */

import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const APP_DIR = [
  resolve(process.cwd(), "app"),
  resolve(process.cwd(), "apps/web/app"),
].find((path) => {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
});

/**
 * Strip comments before scanning.
 *
 * Not optional: the docstring in `useDeckCards.ts` explains this very bug and quotes
 * `for (const ref of …)`, so a scanner that reads comments reports the explanation as the
 * defect. Crude, and it does not need to be careful — a `//` inside a string literal would
 * over-strip, which can only cause a false *pass* on a line that is not a binding anyway.
 */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

function sourceFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) found.push(...sourceFiles(path));
    else if (path.endsWith(".ts") || path.endsWith(".vue")) found.push(path);
  }
  return found;
}

/** The Vue names whose absence breaks a composable at runtime rather than at build. */
const AUTO_IMPORTED = ["ref", "computed", "watch", "reactive", "shallowRef"];

/**
 * A binding of `name`: `const name`, `let name`, `for (const name of`, or a destructure
 * like `({ name, count })` / `([name, count])`.
 *
 * Deliberately not a parser. The failure is textual — the scanner Nuxt runs is itself
 * looking at identifiers — and a regex that over-reports is fine here: every hit is
 * something worth renaming anyway.
 */
function shadowPattern(name: string): RegExp {
  return new RegExp(
    [
      `\\b(?:const|let|var)\\s+${name}\\b(?!\\s*[,}])`,
      `\\bfor\\s*\\(\\s*(?:const|let|var)\\s+${name}\\b`,
      // A destructured arrow parameter: `({ ref, count }) =>`. The `)` sits between the
      // closing brace and the arrow, which an adjacent-token pattern misses.
      `[({\\[][^)\\n]*?\\b${name}\\s*[,}\\]][^)\\n]*?\\)?\\s*=>`,
    ].join("|"),
  );
}

describe("auto-import shadowing", () => {
  it("scans a real directory", () => {
    expect(APP_DIR).toBeDefined();
    expect(sourceFiles(APP_DIR!).length).toBeGreaterThan(20);
  });

  it("no file binds a name Vue auto-imports", () => {
    const offenders: string[] = [];

    for (const path of sourceFiles(APP_DIR!)) {
      const source = stripComments(readFileSync(path, "utf8"));
      for (const name of AUTO_IMPORTED) {
        // An explicit `import { ref } from "vue"` is a real binding and perfectly safe —
        // the module then does not rely on the auto-import at all.
        if (new RegExp(`import\\s*\\{[^}]*\\b${name}\\b[^}]*\\}\\s*from\\s*["']vue["']`).test(source)) {
          continue;
        }
        if (shadowPattern(name).test(source)) {
          offenders.push(`${path.replace(APP_DIR!, "app")} shadows \`${name}\``);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it("would catch the bug that caused this", () => {
    // The exact line from `useDeckCards.ts`, pinned so a regex that quietly stopped
    // matching cannot leave the scan above passing on everything.
    expect(shadowPattern("ref").test("for (const ref of cardRefs()) {")).toBe(true);
    expect(shadowPattern("ref").test("const ref = 1;")).toBe(true);
    expect(shadowPattern("ref").test("counted.map(({ ref, count }) => ref)")).toBe(true);

    // Things that are not bindings, and must not be reported — including the shapes the
    // fixed `useDeckCards.ts` actually uses, so the guard cannot flag the fix itself.
    expect(shadowPattern("ref").test("const isLoading = ref(true);")).toBe(false);
    expect(shadowPattern("ref").test("item.ref")).toBe(false);
    expect(shadowPattern("ref").test("{ ref: cardRef }")).toBe(false);
    expect(
      shadowPattern("ref").test("counted.value.flatMap(({ cardRef, count }) => {"),
    ).toBe(false);
    expect(
      shadowPattern("ref").test(".filter((cardRef) => !isUnresolved(cardRef));"),
    ).toBe(false);
  });
});
