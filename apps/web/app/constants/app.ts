/**
 * App-level constants.
 *
 * v1 also exported `LOCALES` (a hand-written list that omitted `es`, which the site does
 * serve) and `APP_BASE_URL_NAME` — both unreferenced. The locale list now comes from
 * `@holo/schema/enums`, which is generated from the same models as the database.
 *
 * `constants/card-data.ts` is **deleted**. It was the colour / card-type / rarity /
 * bloom-level enums written out a second time, and it had drifted from the data: no `HR`
 * rarity (24 cards unfilterable in the live UI), no `supportStaff` or `unknown` card
 * type, and `["debut","1st","2nd","spot"]` where the data says `first`/`second`. Import
 * from `@holo/schema/enums` instead — that is the point of generating the contract once.
 */

/**
 * Stamped into every saved deck as `Deck.version`.
 *
 * Part of the **frozen** persistence format (ADR 0006, Q11): decks live in
 * `localStorage` and inside shared deck-code URLs, neither of which we control. Changing
 * the field's meaning would strand data already in the wild.
 */
export const APP_VERSION = "0.9.0";
