<script setup lang="ts">
const cardImage = useCardImage();
import { CircleMinus, CirclePlus } from "lucide-vue-next";
import { toast } from "vue-sonner";
import type { Card } from "@/types/card";
import { sectionForCardType } from "@/composables/deckSections";

const props = defineProps<{
  item: Card;
}>();

const decks = useDecks();
const { t } = useI18n();
const isEditing = computed(() => decks.isEditing.value);

/**
 * The section this card belongs to, for naming the full one in a message.
 *
 * `null` for a card whose type routes nowhere, which is also the case where nothing can
 * be added — the store returns 0 and there is no section to name.
 */
const section = computed(() => sectionForCardType(props.item.card_type_code));

/**
 * The section's display name, reusing the strings the deck views already show.
 *
 * These three exist in all seven locales as top-level keys, so a new `deck.sections.*`
 * block would be a second spelling of the same thing — and the one that drifts.
 */
const SECTION_LABEL_KEY = {
  oshi: "Oshi",
  main: "Main Deck",
  yell: "Yell Deck",
} as const;

const sectionLabel = computed(() =>
  section.value ? t(SECTION_LABEL_KEY[section.value.key]) : "",
);

/**
 * Add copies, and say so when fewer land than were asked for (#49).
 *
 * `addCardToDeck` has always returned how many were actually added — its docstring says
 * so explicitly — and this discarded it. Tapping +10 on a deck holding 47 of 50 added
 * three copies with no toast, no message, and nothing to distinguish it from a
 * successful add of ten. The model layer was right; the view threw the report away.
 *
 * A full success stays silent: the count badge already updates, and a toast per add
 * would be noise on the common path.
 */
const add = (amount: number = 1) => {
  if (!isEditing.value) return;

  const added = decks.addCardToDeck({
    cardId: props.item.id,
    amount,
    cardTypeCode: props.item.card_type_code,
  });

  if (added === amount) return;

  if (added === 0) {
    toast.warning(t("deck.sectionFull", { section: sectionLabel.value }));
  } else {
    toast.warning(
      t("deck.addedPartial", {
        added,
        requested: amount,
        section: sectionLabel.value,
      }),
    );
  }
};

/**
 * Remove copies. Same reasoning as `add` — the return value was discarded here too.
 *
 * Removing fewer than asked is far less surprising (the button only shows when at least
 * one copy is present, and a single-copy remove is the common case), so only the
 * nothing-happened case is worth a message.
 */
const remove = (amount: number = 1) => {
  if (!isEditing.value) return;

  const removed = decks.removeCardFromDeck({
    cardId: props.item.id,
    amount,
    cardTypeCode: props.item.card_type_code,
  });

  if (removed === 0) {
    toast.warning(t("deck.nothingToRemove"));
  }
};

const count = computed(() => {
  return decks.getCardCount(props.item.id, props.item.card_type_code);
});
</script>

<template>
  <div class="relative flex aspect-400/559">
    <Dialog>
      <DialogTrigger class="w-full">
        <SimpleImage
          class="rounded-lg overflow-hidden"
          :src="cardImage(item.image_key)"
          :img-attributes="{ class: 'w-full' }"
        />
      </DialogTrigger>

      <CardItemDialogContent :item="item" />
    </Dialog>

    <div
      v-if="isEditing"
      class="absolute bottom-0 left-0 flex gap-1 p-1 w-full"
    >
      <button
        class="bg-secondary/90 rounded-sm md:py-0.5 grow"
        @click="add(10)"
      >
        <div class="flex items-center gap-1 justify-center text-xs md:text-sm">
          <CirclePlus class="w-3 md:w-4" />
          10
        </div>
      </button>
      <button class="bg-secondary/90 rounded-sm md:py-0.5 grow" @click="add(4)">
        <div class="flex items-center gap-1 justify-center text-xs md:text-sm">
          <CirclePlus class="w-3 md:w-4" />
          4
        </div>
      </button>
      <button class="bg-secondary/90 rounded-sm md:py-0.5 grow" @click="add(1)">
        <div class="flex items-center gap-1 justify-center text-xs md:text-sm">
          <CirclePlus class="w-3 md:w-4" />
          1
        </div>
      </button>
    </div>

    <div
      v-if="isEditing"
      class="absolute top-0 right-0 flex flex-col gap-1 p-1"
    >
      <button
        v-if="isEditing && count > 0"
        class="bg-red-500/90 rounded-sm size-7 md:size-8"
        @click="remove(1)"
      >
        <div class="flex items-center justify-center text-xs">
          <CircleMinus class="w-3 md:w-4 text-white" />
        </div>
      </button>
    </div>

    <CardCountBadge
      v-if="isEditing && count > 0"
      :count="count || 0"
      :size="'normal'"
    />
  </div>
</template>
