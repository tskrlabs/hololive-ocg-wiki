/**
 * App code must not use import attributes (`with { type: "json" }`).
 *
 * **This is a real bug that shipped past a green `make check`.** `cardRefs.ts` imported the
 * card-id snapshot with the attribute, which is valid TypeScript and which both `vue-tsc`
 * and Vitest accept — so typecheck passed and 269 tests passed. The dev server then died on
 * the first page load with:
 *
 *     SyntaxError: Strict mode code may not include a with statement
 *
 * and `nuxt generate` failed with `[PARSE_ERROR] Expected '(' but found '{'`. The parser
 * that handles app modules reads `with` as the (forbidden) `with` statement.
 *
 * The attribute is fine in two places, and both are excluded below: `nuxt.config.ts` runs
 * through Vite's node pipeline, and tests run through Vitest. Only `app/` is affected.
 *
 * A test rather than a lint rule because this repo has no linter, and `make check` runs
 * unit tests. `make check-site` does catch it — it actually builds — but it is deliberately
 * outside `make check` to keep the pre-commit hook fast (ADR 0009 D24), so the fast path
 * needs its own guard.
 *
 * The fix is to drop the attribute: `import x from "…json"`, exactly as
 * `changelog.vue` imports `#content/changelog.json`.
 */

import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

// `process.cwd()` is `apps/web` under `npm test --workspace`, but the repo root when
// vitest is invoked with `--root`. Try both rather than depending on how it was started —
// `original-text.test.ts` can assume the workspace cwd; a guard that silently scans
// nothing would be worse than useless.
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

/** Every `.ts` and `.vue` file under `app/`, recursively. */
function sourceFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
    } else if (path.endsWith(".ts") || path.endsWith(".vue")) {
      found.push(path);
    }
  }
  return found;
}

// `with`/`assert` between a module specifier and the statement's end. Deliberately loose:
// the failure is a parser rejecting the token, so spotting the token is the whole job.
const IMPORT_ATTRIBUTE = /\bfrom\s+["'][^"']+["']\s*(with|assert)\s*\{/;

describe("import attributes in app code", () => {
  it("scans a real directory", () => {
    // Without this, a wrong cwd makes the guard below pass on an empty file list — the
    // exact silent-green failure it exists to prevent.
    expect(APP_DIR).toBeDefined();
    expect(sourceFiles(APP_DIR!).length).toBeGreaterThan(20);
  });

  it("appear nowhere under app/", () => {
    const offenders = sourceFiles(APP_DIR!).filter((path) => {
      const source = readFileSync(path, "utf8");
      return IMPORT_ATTRIBUTE.test(source);
    });

    expect(offenders.map((path) => path.replace(APP_DIR!, "app"))).toEqual([]);
  });

  it("would be caught if one were added", () => {
    // Pins the pattern itself, so a regex that silently stopped matching cannot leave the
    // test above passing on every input.
    expect(
      IMPORT_ATTRIBUTE.test('import x from "a.json" with { type: "json" };'),
    ).toBe(true);
    expect(IMPORT_ATTRIBUTE.test('import x from "a.json";')).toBe(false);
  });
});
