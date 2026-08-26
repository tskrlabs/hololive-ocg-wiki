/**
 * Deck state (architecture review Candidate 03).
 *
 * v1's version was 488 lines in which every mutation forked three ways — `addCardToDeck`,
 * `removeCardFromDeck`, `removeAllCardFromDeck` and `getCardCount` each contained the
 * same branch written out once per section, twelve near-identical blocks. It also
 * enforced no limits: `addCardToDeck` pushed unconditionally, and 1 oshi / 50 main /
 * 20 yell existed only as numbers typed into templates.
 *
 * The rules now live in `deckSections.ts` and the serialisation in `deckCode.ts`, both
 * pure and both tested. What remains here is the genuinely stateful part: which decks
 * exist, which is being edited, and persistence.
 *
 * **The stored shape is unchanged** (ADR 0006, Q11). Sections are how the deck is
 * reasoned about; `oshiCardIds` / `mainCardIds` / `yellCardIds` remain exactly what goes
 * into `localStorage` and into every shared deck-code URL — neither of which we control.
 */

import type { Deck } from "~/types/deck";
import type { CardTypeCode } from "~/types/card";
import { APP_VERSION } from "~/constants/app";
import * as deckCode from "~/composables/deckCode";
import { migrateDecks } from "~/composables/cardRefs";
import { toast } from "vue-sonner";
import {
  SECTIONS,
  addToSection,
  copiesOf,
  removeFromSection,
  sectionForCardType,
  type SectionField,
} from "~/composables/deckSections";
import { useTimestamp } from "@vueuse/core";

/** The v1 key. Changing it would orphan every saved deck (Q11). */
const STORAGE_KEY = "hololive-ocg-wiki-decks";

/**
 * The pre-migration snapshot, written once before decks are first converted to
 * `image_key` (ADR 0014).
 *
 * The migration is eager and touches every saved deck in one pass, which is the thing
 * worth insuring against: a bug here hits all of a user's decks at once, and the data it
 * overwrites is theirs, not ours. Written only if absent, so a later mount cannot
 * overwrite the original with already-migrated data.
 */
const BACKUP_KEY = "hololive-ocg-wiki-decks.pre-image-key";

/** `vue-sonner` de-dupes by id, so a remount cannot stack a second copy (see #57). */
const MIGRATION_TOAST_ID = "deck-refs-migrated";

export const useDecks = () => {
  const decksState = useState<Deck[]>("decks", () => []);
  const currentDeckState = useState<Deck | null>("currentDeck", () => null);
  const isEditingState = useState<boolean>("isEditing", () => false);

  const { t } = useI18n();

  onMounted(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return;

      const loaded = JSON.parse(stored) as Deck[];
      const { decks, convertedCount } = migrateDecks(loaded);
      decksState.value = decks;

      // Nothing to migrate is the common case after the first load, and it must not
      // write, back up, or toast.
      if (convertedCount === 0) return;

      // Back up before the first mutation, and only if nothing is there — a second mount
      // must not overwrite the original with data this migration already touched.
      if (localStorage.getItem(BACKUP_KEY) === null) {
        localStorage.setItem(BACKUP_KEY, stored);
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(decks));

      // Transparency, not approval (ADR 0014). The mapping is exact, so there is nothing
      // to confirm and no card list worth reading: after this the deck holds the cards it
      // always meant to. A stable id keeps a remount from stacking toasts.
      // A named parameter, not `t(key, count)`: that second form is vue-i18n's
      // plural-choice syntax and no message in this app uses `|` branches.
      toast.info(t("deck.migration.updated", { count: convertedCount }), {
        id: MIGRATION_TOAST_ID,
      });
    } catch (error) {
      console.error("Failed to load decks from localStorage:", error);
    }
  });

  const saveDecks = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(decksState.value));
    } catch (error) {
      console.error("Failed to save decks to localStorage:", error);
    }
  };

  const createNewDeck = (name: string, author: string): Deck => ({
    id: `${name}-${useTimestamp({ offset: 0 }).value.toString()}`,
    name,
    author,
    oshiCardIds: [],
    mainCardIds: [],
    yellCardIds: [],
    version: APP_VERSION,
    // Without this a freshly created deck reads as legacy and would be "migrated" on the
    // next mount, turning its image_keys into unresolved markers.
    cardRefFormat: "image-key",
  });

  const addDeck = (deck: Deck) => {
    decksState.value.push(deck);
    saveDecks();
    return deck;
  };

  const updateDeck = (deckId: string, updates: Partial<Deck>) => {
    const index = decksState.value.findIndex((deck) => deck.id === deckId);
    if (index === -1) return null;

    // The findIndex guard proves this element exists; noUncheckedIndexedAccess cannot
    // see that.
    decksState.value[index] = { ...decksState.value[index]!, ...updates };
    saveDecks();
    return decksState.value[index];
  };

  const setCurrentDeck = (deck: Deck | null) => {
    currentDeckState.value = deck;
  };

  const deleteDeck = (deckId: string) => {
    const index = decksState.value.findIndex((deck) => deck.id === deckId);
    if (index !== -1) decksState.value.splice(index, 1);
    saveDecks();
    setCurrentDeck(null);
  };

  const toggleEditing = () => {
    isEditingState.value = !isEditingState.value;
  };

  /** Write one section back to the current deck and persist. */
  const commit = (field: SectionField, ids: string[]) => {
    const deck = currentDeckState.value;
    if (!deck) return;
    deck[field] = ids;
    if (deck.id) updateDeck(deck.id, { [field]: ids });
  };

  /**
   * Add copies of a card to whichever section its type belongs to.
   *
   * One implementation, not three. The section is chosen by card type and the limit is
   * enforced by the module — v1 did neither, so a 60-card main deck was reachable and
   * only the badge turned red.
   *
   * Returns how many were actually added, which may be fewer than asked for.
   */
  const addCardToDeck = ({
    cardRef,
    amount,
    cardTypeCode,
  }: {
    /** The card's `image_key`, not its id (ADR 0014). */
    cardRef: string;
    amount: number;
    cardTypeCode: CardTypeCode;
  }): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;

    const { ids, added } = addToSection(deck, section, cardRef, amount);
    if (added > 0) commit(section.field, ids);
    return added;
  };

  const removeCardFromDeck = ({
    cardRef,
    amount,
    cardTypeCode,
  }: {
    /** The card's `image_key`, not its id (ADR 0014). */
    cardRef: string;
    amount: number;
    cardTypeCode: CardTypeCode;
  }): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;

    const { ids, removed } = removeFromSection(deck, section, cardRef, amount);
    if (removed > 0) commit(section.field, ids);
    return removed;
  };

  const removeAllCardFromDeck = (
    cardRef: string,
    cardTypeCode: CardTypeCode,
  ): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;

    const { ids, removed } = removeFromSection(deck, section, cardRef);
    if (removed > 0) commit(section.field, ids);
    return removed;
  };

  /**
   * Remove every copy of a reference, without knowing its card type (ADR 0014).
   *
   * The other mutations route through `sectionForCardType`, which needs a `Card`. An
   * unresolved slot has none — that is what makes it unresolved — so this searches all
   * three sections instead. It is the only way a user can get a card they cannot see out
   * of their deck, and without it a withdrawn card is stuck there permanently.
   *
   * Safe to run across sections: a reference appears in exactly one, because the section
   * was chosen by card type when it was added.
   */
  const removeRefFromDeck = (cardRef: string): number => {
    const deck = currentDeckState.value;
    if (!deck) return 0;

    let total = 0;
    for (const section of SECTIONS) {
      const { ids, removed } = removeFromSection(deck, section, cardRef);
      if (removed > 0) {
        commit(section.field, ids);
        total += removed;
      }
    }
    return total;
  };

  const getCardCount = (cardRef: string, cardTypeCode: CardTypeCode): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;
    return copiesOf(deck, section, cardRef);
  };

  // --- Sharing -------------------------------------------------------------
  //
  // The transform itself is in `deckCode.ts` — pure, and therefore testable without
  // `window`, `localStorage` or `useI18n`, all three of which v1's version needed.

  const getDeckCode = (deckId: string) => {
    const deck = decksState.value.find((d) => d.id === deckId);
    if (!deck) return { code: "", localePath: "", fullUrl: "" };

    const code = deckCode.encode(deck);
    const path = useLocalePath()({ name: "deck-code", params: { code } });
    return { code, localePath: path, fullUrl: `${window.location.origin}${path}` };
  };

  /** Decode a shared code. `false` rather than `null` — v1's callers test for it. */
  const checkForDeckCode = (code: string): Deck | false =>
    deckCode.decode(code) ?? false;

  const importDeckByCode = (code: string): { status: boolean; message: string } => {
    const decoded = deckCode.decode(code);
    if (!decoded) return { status: false, message: t("Invalid deck code") };

    const index = decksState.value.findIndex((deck) => deck.id === decoded.id);
    if (index !== -1) {
      decksState.value[index] = decoded;
      saveDecks();
      return { status: true, message: t("Deck updated successfully") };
    }

    decksState.value.push(decoded);
    saveDecks();
    return { status: true, message: t("Deck imported successfully") };
  };

  const exportDecks = (): string => JSON.stringify(decksState.value);

  const importDecks = (jsonData: string): boolean => {
    try {
      const imported = JSON.parse(jsonData) as Deck[];
      if (!Array.isArray(imported)) {
        console.error("Invalid deck data format");
        return false;
      }
      decksState.value = imported;
      saveDecks();
      return true;
    } catch (error) {
      console.error("Failed to import decks:", error);
      return false;
    }
  };

  return {
    decks: decksState,
    currentDeck: currentDeckState,
    isEditing: isEditingState,

    toggleEditing,
    addDeck,
    updateDeck,
    deleteDeck,
    setCurrentDeck,
    saveDecks,
    createNewDeck,

    addCardToDeck,
    removeCardFromDeck,
    removeAllCardFromDeck,
    removeRefFromDeck,
    getCardCount,

    /** The section rules, for views that render limits and status badges. */
    sections: SECTIONS,

    getDeckCode,
    exportDecks,
    importDecks,
    checkForDeckCode,
    importDeckByCode,
  };
};
