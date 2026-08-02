<script setup lang="ts">
/**
 * One deck section's cards, with the add/remove controls (ADR 0009 D18).
 *
 * Was `FloatingDeckCardList`, then `DeckDrawerCardList` — renamed each time the surface
 * it belongs to changed, because the name is how a reader finds that surface. Older
 * comments elsewhere still name the v1 file; those are describing history and are left
 * alone.
 *
 * ⚠️ **The column count is fixed, and that is the fix.** This was
 * `grid-cols-4 md:grid-cols-10`, and `md:` reads the *viewport* while the grid lives in a
 * 384px panel — so on any desktop it packed ten columns into ~326px of content and
 * rendered **30px tiles under 32px control buttons**. The panel's width is a constant
 * (D18), not a function of the window, so a responsive prefix here can only ever be
 * wrong. Three columns is what 326px affords: 102×142px, which is enough art to
 * recognise a card by, and leaves the trash button at 31% of the tile rather than 106%.
 *
 * If the panel ever becomes resizable, this becomes a container query — not a breakpoint.
 */
import { CircleMinus, CirclePlus, Trash2 } from "lucide-vue-next";
import type { CardTypeCode } from "~/types/card";

const props = defineProps<{
  cardIds: string[];
}>();

// The count → dedupe → fetch → join pipeline, once (Candidate 04). v1 had it written
// out verbatim here and in DeckDetailCardList, plus a hand-rolled Map variant in the
// compact list — six copies of one derivation across three files.
const { deckCards, isLoading } = useDeckCards(() => props.cardIds);

const decks = useDecks();
const cardImage = useCardImage();

// Optimized action methods with cached context
// Using arrow functions with parameter destructuring for better performance
const add = (cardId: string, cardTypeCode: CardTypeCode) => {
  if (decks.currentDeck.value) {
    decks.addCardToDeck({ cardId, amount: 1, cardTypeCode });
  }
};

const remove = (cardId: string, cardTypeCode: CardTypeCode) => {
  if (decks.currentDeck.value) {
    decks.removeCardFromDeck({ cardId, amount: 1, cardTypeCode });
  }
};

const removeAll = (cardId: string, cardTypeCode: CardTypeCode) => {
  if (decks.currentDeck.value) {
    decks.removeAllCardFromDeck(cardId, cardTypeCode);
  }
};

</script>

<template>
  <div v-if="isLoading" class="p-4 flex justify-center items-center">
    <div
      class="animate-spin h-6 w-6 border-2 border-primary rounded-full border-t-transparent"
    ></div>
  </div>

  <!-- `muted-foreground`, not a hardcoded `text-gray-500`: the palette has a token for
       exactly this and D4 leaves no room for ad-hoc colours. -->
  <div
    v-else-if="deckCards.length === 0"
    class="p-4 text-center text-sm text-muted-foreground"
  >
    {{ $t("No cards to display") }}
  </div>

  <div v-else class="grid grid-cols-3 gap-2">
    <template v-for="{ card, count } in deckCards" :key="card.id">
      <div class="relative flex">
        <Dialog>
          <DialogTrigger class="w-full">
            <Image
              class="aspect-400/559"
              :src="cardImage(card.image_key)"
              :img-attributes="{ class: '' }"
            />
          </DialogTrigger>

          <CardItemDialogContent :item="card" />
        </Dialog>

        <!-- actions -->
        <div class="absolute bottom-0 left-0 w-full flex gap-1 p-1">
          <!--
            The labels were the literal English strings "Add card" / "Remove card" /
            "Remove all cards" — untranslated in seven locales, and identical on every
            tile, so a screen-reader user heard the same three names 40 times with no way
            to tell which card they belonged to (#51's finding, one surface further in).
          -->
          <button
            class="h-6 w-2/4 rounded-sm bg-secondary/95"
            @click.prevent="add(card.id, card.card_type_code)"
            :aria-label="$t('deck.addCopies', { count: 1, name: card.name ?? card.card_number })"
          >
            <div class="flex items-center justify-center text-xs">
              <CirclePlus class="size-4" aria-hidden="true" />
            </div>
          </button>
          <!--
            `--destructive` rather than a hardcoded red (D4): removing a copy is a
            destructive action, which is the one thing that colour is reserved for.
          -->
          <button
            class="h-6 w-2/4 rounded-sm bg-destructive/95 text-destructive-foreground"
            @click.prevent="remove(card.id, card.card_type_code)"
            :aria-label="$t('deck.removeCopy', { name: card.name ?? card.card_number })"
          >
            <div class="flex items-center justify-center text-xs">
              <CircleMinus class="size-4" aria-hidden="true" />
            </div>
          </button>
        </div>

        <div class="absolute top-0 right-0 flex flex-col gap-1 p-1">
          <button
            class="size-7 rounded-sm bg-destructive/90 text-destructive-foreground"
            @click.prevent="removeAll(card.id, card.card_type_code)"
            :aria-label="$t('deck.removeAllCopies', { name: card.name ?? card.card_number })"
          >
            <div class="flex items-center justify-center text-xs">
              <Trash2 class="size-4" aria-hidden="true" />
            </div>
          </button>
        </div>

        <!-- The count comes with the card now; v1 looked it back up by id. -->
        <CardCountBadge :count="count" :size="'small'" />
      </div>
    </template>
    <!-- </TransitionGroup> -->
  </div>
</template>
