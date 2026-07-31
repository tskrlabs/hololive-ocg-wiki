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
 * The tile's text block (D14, #37) — and the answer to
 * [#29](https://github.com/tskrlabs/hololive-ocg-wiki/issues/29).
 *
 * The show-original toggle had shipped with **nothing to act on in the card list**,
 * because the list rendered art and nothing else. That is what this block is for.
 */
const { density } = useCardDensity();
const showsText = computed(() => density.value === "comfortable");
const { enabled: showOriginal } = useShowOriginal();

/**
 * The source-language name, when there is one to show.
 *
 * `original` only carries fields whose source and translation *differ*, so this is
 * absent on `ja` and on any card left untranslated — the same contract `OriginalText`
 * relies on. It is a real third line rather than a rarity: **84% of `tc` cards and 93%
 * of `en`/`th` cards** have a name differing from the Japanese.
 */
const originalName = computed(() =>
  showOriginal.value ? (props.item.original?.name ?? "") : "",
);

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
  <!--
    Art on top, text below (D14). The art keeps the printed card's aspect ratio; the text
    block sits outside it, so a name never crops the artwork.

    The height of this whole tile is mirrored by `gridGeometry`'s `itemSize`, because
    `RecycleScroller` positions rows from that number and cannot measure a child. Changing
    the text block here without changing `textBlockHeight()` there overlaps every row.
  -->
  <div class="flex flex-col">
    <div class="relative flex aspect-400/559">
      <Dialog>
        <DialogTrigger class="w-full">
          <!--
            `alt` is the card's name (#38 §3, #48 §7). It was passing none at all, so
            every tile's art was an unlabelled image — 34 of them on the fixture homepage
            alone. It doubles as the fallback text when the image fails to load.
          -->
          <SimpleImage
            class="rounded-lg overflow-hidden"
            :src="cardImage(item.image_key)"
            :alt="item.name ?? item.card_number"
            :img-attributes="{ class: 'w-full' }"
          />
        </DialogTrigger>

        <CardItemDialogContent :item="item" />
      </Dialog>

      <!--
        The add controls. Their visible "10"/"4"/"1" is a quantity, not a name — a screen
        reader announced "button, 10" with no indication of what ten of what would happen
        — so each carries an `.sr-only` label naming the card (#37 §7, the same defect
        #51 fixed in the header).
      -->
      <div
        v-if="isEditing"
        class="absolute bottom-0 left-0 flex gap-1 p-1 w-full"
      >
        <button
          v-for="amount in [10, 4, 1]"
          :key="amount"
          class="bg-secondary/90 rounded-sm md:py-0.5 grow"
          @click="add(amount)"
        >
          <div class="flex items-center gap-1 justify-center text-xs md:text-sm">
            <CirclePlus class="w-3 md:w-4" aria-hidden="true" />
            {{ amount }}
            <span class="sr-only">
              {{ $t("deck.addCopies", { count: amount, name: item.name }) }}
            </span>
          </div>
        </button>
      </div>

      <div
        v-if="isEditing"
        class="absolute top-0 right-0 flex flex-col gap-1 p-1"
      >
        <!--
          The one exception to D4's no-hue rule, and it is deliberate: `--destructive` is
          the single semantic colour in the palette and removal is a destructive *action*,
          which is exactly what it is reserved for. It was a hardcoded `bg-red-500`.
        -->
        <button
          v-if="isEditing && count > 0"
          class="bg-destructive/90 rounded-sm size-7 md:size-8"
          @click="remove(1)"
        >
          <div class="flex items-center justify-center text-xs">
            <CircleMinus
              class="w-3 md:w-4 text-destructive-foreground"
              aria-hidden="true"
            />
            <span class="sr-only">
              {{ $t("deck.removeCopy", { name: item.name }) }}
            </span>
          </div>
        </button>
      </div>

      <CardCountBadge
        v-if="isEditing && count > 0"
        :count="count || 0"
        :size="'normal'"
      />
    </div>

    <!--
      Name, source name, card number — the three lines the grid never had (#29, D14).

      The source name goes on **its own line**, not inline as `OriginalText` does in the
      dialog. That component's reasoning ("the whole purpose is comparison… wants both at
      once") is right and is preserved — but inline does not fit here: measured across all
      2,463 names, **19% of tiles truncate** with the pair inline against **under 1%**
      stacked, and a comparison you cannot read defeats the toggle entirely. The dialog
      keeps inline, where there is horizontal room.

      One line each, with `truncate` and the full name in `title` — safe because overflow
      at the 187px name box is 0.0–0.9% in every locale measured.
    -->
    <div v-if="showsText" class="px-0.5 pt-1.5">
      <div class="truncate text-sm font-medium leading-[18px]" :title="item.name">
        {{ item.name }}
      </div>
      <!--
        `lang="ja"` so a browser picks the Japanese face for this run rather than the
        page's — the same reason `OriginalText` sets it.
      -->
      <div
        v-if="originalName"
        lang="ja"
        class="truncate text-sm leading-[18px] text-muted-foreground"
        :title="originalName"
      >
        {{ originalName }}
      </div>
      <div class="truncate font-mono text-xs leading-4 text-muted-foreground">
        {{ item.card_number }}
      </div>
    </div>
  </div>
</template>
