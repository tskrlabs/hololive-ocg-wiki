import type { Deck } from "~/types/deck";
import type { Card, CardTypeCode } from "~/types/card";
// The three deck sections come from the contract, not a hand-maintained constants file.
// v1's copy omitted `supportStaff`, so a card of that type routed to no section at all.
import {
  OSHI_CARD_TYPES as CARD_TYPE_OSHI,
  MAIN_CARD_TYPES as CARD_TYPE_MAIN,
  YELL_CARD_TYPES as CARD_TYPE_YELL,
} from "@holo/schema/enums";
import { APP_VERSION } from "~/constants/app";
import { useTimestamp } from "@vueuse/core";

// Comprehensive deck management with localStorage
export const useDecks = () => {
  const decksState = useState<Deck[]>("decks", () => []);
  const currentDeckState = useState<Deck | null>("currentDeck", () => null);
  const isEditingState = useState<boolean>("isEditing", () => false);
  const localStorageKey = "hololive-ocg-wiki-decks";

  const { t } = useI18n();

  // Load decks from localStorage on init
  onMounted(() => {
    try {
      const storedDecks = localStorage.getItem(localStorageKey);
      if (storedDecks) {
        decksState.value = JSON.parse(storedDecks);
      }
    } catch (error) {
      console.error("Failed to load decks from localStorage:", error);
    }
  });

  // Make new deck
  const createNewDeck = (name: string, author: string): Deck => {
    const newDeck: Deck = {
      id: `${name}-${useTimestamp({ offset: 0 }).value.toString()}`,
      name,
      author,
      oshiCardIds: [],
      mainCardIds: [],
      yellCardIds: [],
      version: APP_VERSION, // Set initial version
    };

    return newDeck;
  };

  // Save decks to localStorage
  const saveDecks = () => {
    try {
      localStorage.setItem(localStorageKey, JSON.stringify(decksState.value));
    } catch (error) {
      console.error("Failed to save decks to localStorage:", error);
    }
  };

  // Add a new deck
  const addDeck = (deck: Deck) => {
    decksState.value.push(deck);
    saveDecks();
    return deck;
  };

  // Update an existing deck
  const updateDeck = (deckId: string, updates: Partial<Deck>) => {
    const deckIndex = decksState.value.findIndex((deck) => deck.id === deckId);
    if (deckIndex !== -1) {
      decksState.value[deckIndex] = {
        // The `findIndex !== -1` guard above proves this element exists;
        // `noUncheckedIndexedAccess` cannot see that.
        ...decksState.value[deckIndex]!,
        ...updates,
      };
      saveDecks();
      return decksState.value[deckIndex];
    }
    return null;
  };

  // Delete a deck
  const deleteDeck = (deckId: string) => {
    const deckIndex = decksState.value.findIndex((deck) => deck.id === deckId);
    if (deckIndex !== -1) {
      decksState.value.splice(deckIndex, 1);
    }
    saveDecks();

    setCurrentDeck(null); // Clear current deck if deleted
    // console.log(
    //   `Deck with ID ${deckId} deleted. currentDeckState.value:`,
    //   currentDeckState.value
    // );
  };

  // Set current deck
  const setCurrentDeck = (deck: Deck | null) => {
    currentDeckState.value = deck;
  };

  const toggleEditing = () => {
    isEditingState.value = !isEditingState.value;
  };

  // Add a card to the current deck with optimized caching
  const addCardToDeck = ({
    cardId,
    amount,
    cardTypeCode,
  }: {
    cardId: string;
    amount: number;
    cardTypeCode: CardTypeCode;
  }) => {
    // Get card from store instead of direct JSON import
    // const card = cardStore.getCardById(cardId);
    // const cardTypeCode = card?.card_type_code;

    if (!cardTypeCode || !currentDeckState.value) return;

    // Use a local flag to track if updates were made
    let updated = false;

    if (CARD_TYPE_OSHI.includes(cardTypeCode)) {
      for (let i = 0; i < amount; i++) {
        currentDeckState.value.oshiCardIds.push(cardId);
        updated = true;
      }
    }

    if (CARD_TYPE_MAIN.includes(cardTypeCode)) {
      for (let i = 0; i < amount; i++) {
        currentDeckState.value.mainCardIds.push(cardId);
        updated = true;
      }
    }

    if (CARD_TYPE_YELL.includes(cardTypeCode)) {
      for (let i = 0; i < amount; i++) {
        currentDeckState.value.yellCardIds.push(cardId);
        updated = true;
      }
    }

    // Only update if changes were made
    if (updated && currentDeckState.value.id) {
      updateDeck(currentDeckState.value.id, {
        ...currentDeckState.value,
      });
    }
  };

  // Remove a card from the current deck with performance optimization
  const removeCardFromDeck = ({
    cardId,
    amount,
    cardTypeCode,
  }: {
    cardId: string;
    amount: number;
    cardTypeCode: CardTypeCode;
  }) => {
    // Get card from store instead of direct JSON import
    // const card = cardStore.getCardById(cardId);
    // const cardTypeCode = card?.card_type_code;

    if (!cardTypeCode || !currentDeckState.value) return;

    // Use a local flag to track if updates were made
    let updated = false;
    let remainingToRemove = amount;

    if (CARD_TYPE_OSHI.includes(cardTypeCode) && remainingToRemove > 0) {
      // Find all indices to remove at once for better performance
      const indices = [];
      for (
        let i = 0;
        i < currentDeckState.value.oshiCardIds.length && remainingToRemove > 0;
        i++
      ) {
        if (currentDeckState.value.oshiCardIds[i] === cardId) {
          indices.push(i);
          remainingToRemove--;
        }
      }

      // Remove in reverse order to avoid index shifting problems
      for (let i = indices.length - 1; i >= 0; i--) {
        currentDeckState.value.oshiCardIds.splice(indices[i]!, 1);
        updated = true;
      }
    }

    remainingToRemove = amount - (amount - remainingToRemove);

    if (CARD_TYPE_MAIN.includes(cardTypeCode) && remainingToRemove > 0) {
      // Find all indices to remove at once
      const indices = [];
      for (
        let i = 0;
        i < currentDeckState.value.mainCardIds.length && remainingToRemove > 0;
        i++
      ) {
        if (currentDeckState.value.mainCardIds[i] === cardId) {
          indices.push(i);
          remainingToRemove--;
        }
      }

      // Remove in reverse order
      for (let i = indices.length - 1; i >= 0; i--) {
        currentDeckState.value.mainCardIds.splice(indices[i]!, 1);
        updated = true;
      }
    }

    remainingToRemove = amount - (amount - remainingToRemove);

    if (CARD_TYPE_YELL.includes(cardTypeCode) && remainingToRemove > 0) {
      // Find all indices to remove at once
      const indices = [];
      for (
        let i = 0;
        i < currentDeckState.value.yellCardIds.length && remainingToRemove > 0;
        i++
      ) {
        if (currentDeckState.value.yellCardIds[i] === cardId) {
          indices.push(i);
          remainingToRemove--;
        }
      }

      // Remove in reverse order
      for (let i = indices.length - 1; i >= 0; i--) {
        currentDeckState.value.yellCardIds.splice(indices[i]!, 1);
        updated = true;
      }
    }

    // Only update if changes were made
    if (updated && currentDeckState.value.id) {
      updateDeck(currentDeckState.value.id, {
        ...currentDeckState.value,
      });
    }
  };

  // Remove all instances of a card from the current deck with performance optimization
  const removeAllCardFromDeck = (cardId: string, cardTypeCode: CardTypeCode) => {
    // Get card from store instead of direct JSON import
    // const card = cardStore.getCardById(cardId);
    // const cardTypeCode = card?.card_type_code;

    if (!cardTypeCode || !currentDeckState.value) return;

    // Use a local flag to track if updates were made
    let updated = false;

    // Use filter which is more efficient than multiple splice operations
    if (CARD_TYPE_OSHI.includes(cardTypeCode)) {
      const originalLength = currentDeckState.value.oshiCardIds.length;
      currentDeckState.value.oshiCardIds =
        currentDeckState.value.oshiCardIds.filter((id) => id !== cardId);
      updated = originalLength !== currentDeckState.value.oshiCardIds.length;
    } else if (CARD_TYPE_MAIN.includes(cardTypeCode)) {
      const originalLength = currentDeckState.value.mainCardIds.length;
      currentDeckState.value.mainCardIds =
        currentDeckState.value.mainCardIds.filter((id) => id !== cardId);
      updated = originalLength !== currentDeckState.value.mainCardIds.length;
    } else if (CARD_TYPE_YELL.includes(cardTypeCode)) {
      const originalLength = currentDeckState.value.yellCardIds.length;
      currentDeckState.value.yellCardIds =
        currentDeckState.value.yellCardIds.filter((id) => id !== cardId);
      updated = originalLength !== currentDeckState.value.yellCardIds.length;
    }

    // Only update if changes were made
    if (updated && currentDeckState.value.id) {
      updateDeck(currentDeckState.value.id, {
        ...currentDeckState.value,
      });
    }
  };

  const getCardCount = (cardId: string, cardTypeCode: CardTypeCode) => {
    // Get card from store instead of direct JSON import
    // const card = cardStore.getCardById(cardId);
    // const cardTypeCode = card?.card_type_code;

    if (!currentDeckState.value || !cardTypeCode) return 0;

    // Use a more efficient counting method
    let count = 0;

    if (CARD_TYPE_OSHI.includes(cardTypeCode)) {
      // Use a single pass through the array for better performance
      for (let i = 0; i < currentDeckState.value.oshiCardIds.length; i++) {
        if (currentDeckState.value.oshiCardIds[i] === cardId) {
          count++;
        }
      }
    } else if (CARD_TYPE_MAIN.includes(cardTypeCode)) {
      for (let i = 0; i < currentDeckState.value.mainCardIds.length; i++) {
        if (currentDeckState.value.mainCardIds[i] === cardId) {
          count++;
        }
      }
    } else if (CARD_TYPE_YELL.includes(cardTypeCode)) {
      for (let i = 0; i < currentDeckState.value.yellCardIds.length; i++) {
        if (currentDeckState.value.yellCardIds[i] === cardId) {
          count++;
        }
      }
    }

    return count;
  };

  // Get the deck code for sharing
  const getDeckCode = (
    deckId: string
  ): { code: string; localePath: string; fullUrl: string } => {
    const deck = decksState.value.find((d) => d.id === deckId);
    if (!deck) return { code: "", localePath: "", fullUrl: "" };

    // Create a compressed version of the deck
    const compressedDeck = {
      id: deck.id,
      name: deck.name,
      // Convert arrays of duplicate IDs to map of {id: count}
      oshiCards: compressCardIds(deck.oshiCardIds),
      mainCards: compressCardIds(deck.mainCardIds),
      yellCards: compressCardIds(deck.yellCardIds),
    };

    // Encode the compressed deck data as base64
    const encodedDeck = btoa(
      encodeURIComponent(JSON.stringify(compressedDeck))
    );

    // Create the URL with the encoded deck data
    const localePath = useLocalePath();
    const baseUrl = window.location.origin;

    const path = localePath({
      name: "deck-code",
      params: { code: encodedDeck },
    });

    const fullUrl = `${baseUrl}${path}`;

    return {
      code: encodedDeck,
      localePath: path,
      fullUrl: fullUrl,
    };
  };

  // Helper function to compress arrays of card IDs into {id: count} format
  const compressCardIds = (cardIds: string[]): Record<string, number> => {
    return cardIds.reduce((acc, id) => {
      acc[id] = (acc[id] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
  };

  // Helper function to expand compressed cards format back to arrays
  const expandCompressedCards = (
    compressed: Record<string, number>
  ): string[] => {
    const expanded: string[] = [];
    Object.entries(compressed).forEach(([id, count]) => {
      for (let i = 0; i < count; i++) {
        expanded.push(id);
      }
    });
    return expanded;
  };

  // Import decks from JSON
  const importDecks = (jsonData: string): boolean => {
    try {
      const importedDecks = JSON.parse(jsonData) as Deck[];

      // Validate that the imported data is an array of decks
      if (!Array.isArray(importedDecks)) {
        console.error("Invalid deck data format");
        return false;
      }

      // Replace existing decks with imported ones
      decksState.value = importedDecks;
      saveDecks();
      return true;
    } catch (error) {
      console.error("Failed to import decks:", error);
      return false;
    }
  };

  // Import deck by code
  const importDeckByCode = (
    code: string
  ): { status: boolean; message: string } => {
    try {
      const decodedDeck = checkForDeckCode(code);

      if (!decodedDeck) {
        return { status: false, message: t("Invalid deck code") };
      }

      // Check if a deck with this ID already exists
      const existingDeckIndex = decksState.value.findIndex(
        (d) => d.id === decodedDeck.id
      );

      if (existingDeckIndex !== -1) {
        // Update existing deck
        decksState.value[existingDeckIndex] = decodedDeck;

        saveDecks();
        return { status: true, message: t("Deck updated successfully") };
      } else {
        // Add as a new deck
        decksState.value.push(decodedDeck);

        saveDecks();
        return { status: true, message: t("Deck imported successfully") };
      }
    } catch (error) {
      return { status: false, message: t("Failed to import deck from code") };
    }
  };

  // Check for shared deck code
  const checkForDeckCode = (code: string): Deck | false => {
    try {
      // Decode the base64 encoded deck
      const compressedDeck = JSON.parse(decodeURIComponent(atob(code)));

      // Convert compressed format back to full deck
      const decodedDeck: Deck = {
        id: compressedDeck.id,
        name: compressedDeck.name,
        author: compressedDeck.author,
        oshiCardIds: expandCompressedCards(compressedDeck.oshiCards),
        mainCardIds: expandCompressedCards(compressedDeck.mainCards),
        yellCardIds: expandCompressedCards(compressedDeck.yellCards),
        version: compressedDeck.version,
      };

      return decodedDeck;
    } catch (error) {
      console.error("Invalid deck code format:", error);
      return false;
    }
  };

  // Export all decks as JSON
  const exportDecks = (): string => {
    return JSON.stringify(decksState.value);
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
    addCardToDeck,
    removeCardFromDeck,
    removeAllCardFromDeck,
    getCardCount,

    createNewDeck,

    // Add new functions to the returned object
    getDeckCode,
    exportDecks,
    importDecks,
    checkForDeckCode,
    importDeckByCode,
  };
};
