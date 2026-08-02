/**
 * Write the card-metadata golden file.
 *
 * Unlike `golden.py`, which generates from a *Python reference* to pin a TypeScript port
 * against it, there is only one implementation of `cardMetaTags()` — both the Worker and
 * the page import it. So this golden file is not a parity check between two languages; it
 * is a record of what the tag set *is*, so that changing it is a reviewable diff rather
 * than a silent change to what every crawler sees.
 *
 * That distinction matters because the failure mode is invisible in a browser: a
 * developer sees the hydrated tags, a crawler sees the injected ones, and only a fetch
 * with JavaScript disabled shows a difference. A committed golden file puts the change in
 * the pull request instead.
 *
 * Run with `make golden-meta` after a deliberate change, and read the diff.
 */

import { writeFileSync } from "node:fs";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { cardMetaTags } from "../src/cardMeta.ts";
import { localize } from "../src/localize.ts";
import { LOCALES } from "../dist/enums.ts";
import type { Card } from "../dist/card.d.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = join(HERE, "..");
const REPO_ROOT = join(PACKAGE_ROOT, "..", "..");

const SITE_URL = "https://hololive-ocg-wiki.tskrlabs.com";
const IMAGE_BASE = "https://img.hololive-ocg-wiki.tskrlabs.com";

const fixtures = JSON.parse(
  readFileSync(join(REPO_ROOT, "fixtures", "cards.json"), "utf-8"),
) as { cards: Card[] };

const output: Record<string, unknown> = {};
for (const card of fixtures.cards) {
  for (const locale of LOCALES) {
    output[`${card.id}:${locale}`] = cardMetaTags({
      card: localize(card, locale),
      locale,
      siteUrl: SITE_URL,
      imageBaseUrl: IMAGE_BASE,
    });
  }
}

const target = join(PACKAGE_ROOT, "golden", "card-meta.json");
writeFileSync(target, `${JSON.stringify(output, null, 2)}\n`, "utf-8");
console.log(
  `  wrote packages/schema/golden/card-meta.json — ${fixtures.cards.length} cards x ${LOCALES.length} locales`,
);
