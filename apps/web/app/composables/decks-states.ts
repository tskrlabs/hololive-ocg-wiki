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

export const useDecks = () => {
  const decksState = useState<Deck[]>("decks", () => []);
  const currentDeckState = useState<Deck | null>("currentDeck", () => null);
  const isEditingState = useState<boolean>("isEditing", () => false);

  const { t } = useI18n();

  onMounted(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) decksState.value = JSON.parse(stored);
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
    cardId,
    amount,
    cardTypeCode,
  }: {
    cardId: string;
    amount: number;
    cardTypeCode: CardTypeCode;
  }): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;

    const { ids, added } = addToSection(deck, section, cardId, amount);
    if (added > 0) commit(section.field, ids);
    return added;
  };

  const removeCardFromDeck = ({
    cardId,
    amount,
    cardTypeCode,
  }: {
    cardId: string;
    amount: number;
    cardTypeCode: CardTypeCode;
  }): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;

    const { ids, removed } = removeFromSection(deck, section, cardId, amount);
    if (removed > 0) commit(section.field, ids);
    return removed;
  };

  const removeAllCardFromDeck = (
    cardId: string,
    cardTypeCode: CardTypeCode,
  ): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;

    const { ids, removed } = removeFromSection(deck, section, cardId);
    if (removed > 0) commit(section.field, ids);
    return removed;
  };

  const getCardCount = (cardId: string, cardTypeCode: CardTypeCode): number => {
    const deck = currentDeckState.value;
    const section = sectionForCardType(cardTypeCode);
    if (!deck || !section) return 0;
    return copiesOf(deck, section, cardId);
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
