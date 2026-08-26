export type Deck = {
  // 1
  oshiCardIds: string[];

  // 50
  mainCardIds: string[];

  // 20
  yellCardIds: string[];

  id: string;
  name?: string;
  author?: string;
  version: string;

  /**
   * Which identifier the three `*CardIds` arrays are written in (ADR 0014).
   *
   * Absent means `"id"` — the legacy form, written by v1 and by v2 before #83. Decks in
   * that form are migrated at load; shared deck codes in that form are translated on
   * decode and never rewritten, since they live in messages we do not control.
   *
   * Separate from `version` on purpose: that one is an app release marker, and reusing it
   * would make an ordinary release bump read as a format change.
   */
  cardRefFormat?: "id" | "image-key";
};

export type DeckCollection = Deck[];
