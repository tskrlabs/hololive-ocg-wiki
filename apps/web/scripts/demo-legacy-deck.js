/**
 * Plant a pre-ADR-0014 deck in `localStorage`, so the migration has something to migrate.
 *
 * The migration only runs against a deck that is already stored in the legacy (id-keyed)
 * form, and there is no way to create one through the UI any more — new decks are written
 * as `image-key` from the start. So a demo needs a deck seeded by hand.
 *
 * Usage: `make dev`, open http://localhost:3000, paste this whole file into the browser
 * console, then reload. Do **not** run it against the production site: it overwrites the
 * decks in whatever origin's `localStorage` you run it in.
 *
 * What it plants, chosen to exercise all three paths at once:
 *
 *   - id 1, 13, 14  — ordinary cards whose ids never moved. These prove the common case
 *                     still resolves after translation.
 *   - id 2582       — a *renumbered* card. Before the 2026-08-26 shift this id meant
 *                     `hBP01-051_UR_02`; the official site has since handed it to
 *                     `hEB01-007_SR`. This is the silent corruption the whole change
 *                     exists to prevent: without the migration it resolves to the wrong
 *                     card, with no error.
 *   - id 2582       — doubles as the *withdrawn card* case locally: the fixture set has no
 *                     hEB01, so this key resolves to nothing and renders the nameable
 *                     placeholder — "hBP01-051", with a link to browse hBP01.
 *   - id 999999     — an id in no snapshot at all, so it cannot be translated and carries
 *                     no card number. It must keep its slot and say plainly that the card
 *                     cannot be identified, rather than vanishing or inventing a guess.
 *
 * Note that 2582 and 999999 will not render as *cards* against the local fixture database
 * (34 cards, none of them hEB01), so both appear as unresolved placeholders locally. That
 * is expected: what the local demo proves is the migration, the toast, the backup key and
 * the placeholder. Proving 2582 resolves to the right card needs the real dataset.
 */
const STORAGE_KEY = "hololive-ocg-wiki-decks";
const BACKUP_KEY = "hololive-ocg-wiki-decks.pre-image-key";

const legacyDeck = {
  id: "demo-legacy-1750000000000",
  name: "レガシーデッキ (demo)",
  author: "demo",
  // Card ids, as every deck stored before ADR 0014 holds them. No `cardRefFormat`, which
  // is exactly what marks this as legacy.
  oshiCardIds: ["1"],
  mainCardIds: ["13", "13", "14", "2582", "999999"],
  yellCardIds: ["20", "20"],
  version: "0.9.0",
};

// Clear any previous run's backup, or the migration will decline to overwrite it and the
// demo will look like it did nothing the second time.
localStorage.removeItem(BACKUP_KEY);
localStorage.setItem(STORAGE_KEY, JSON.stringify([legacyDeck]));

console.log("planted a legacy deck:", legacyDeck);
console.log("now reload the page — expect:");
console.log("  1. a toast: 'Updated 1 deck(s) to the latest card numbering.'");
console.log(`  2. ${BACKUP_KEY} to hold the original, id-keyed copy`);
console.log("  3. the stored deck to hold image_keys, and cardRefFormat 'image-key'");
console.log("  4. two kinds of placeholder tile, not silently missing cards:");
console.log("     - id 2582  -> names 'hBP01-051' and links to browse hBP01");
console.log("     - id 999999 -> says the card cannot be identified (no number to show)");
console.log("  5. the SAME tiles on the deck detail page, not only in the panel");
console.log("");
console.log("the point of the whole change, in one line — after reloading, compare:");
console.log("  what the deck MEANT by id 2582:  hEB01/hBP01-051_UR_02");
console.log("  what id 2582 means in new data:  hEB01/hEB01-007_SR");
console.log("the migration writes the first. Without it the deck silently shows the");
console.log("second, with no error and nothing to notice.");
