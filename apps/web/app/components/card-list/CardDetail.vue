<script setup lang="ts">
/**
 * Everything a card *is* — the five data blocks, with no container decisions (D15, #39).
 *
 * The dialog and the card page are two **containers** around this, not two
 * implementations. That distinction is the whole point: a card rendered in a dialog and
 * the same card rendered at its own URL must show the same facts, or the page a crawler
 * indexes is not the page a user sees.
 *
 * The extraction is cheap because the five blocks were already reusable — each takes
 * `item` and nothing else. What lived in `CardItemDialogContent` was the composition plus
 * the dialog's own chrome; only the composition moves here.
 *
 * This component owns **no** width, no scrolling and no close affordance. Its parent
 * places it. That is what lets the dialog cap itself at `90dvh` and scroll inside, while
 * the page lets the document scroll — the same content, two layouts.
 */
import type { Card } from "@/types/card";

const cardImage = useCardImage();

withDefaults(
  defineProps<{
    item: Card;
    /**
     * Which container this is inside.
     *
     * `dialog` is the space-constrained one: variants stay behind a lazy accordion,
     * because the extra request is real and the room is not. `page` is permanent and
     * indexed, where an accordion would be a needless second interaction *and* content
     * a crawler never expands — 86% of cards have a variant sibling, so that is most of
     * the set.
     *
     * Commit 8 introduces the distinction and both values currently render identically;
     * the page's expanded behaviour arrives with the page itself. Naming it now means
     * the container difference is a prop rather than a fork discovered later.
     */
    variant?: "dialog" | "page";
  }>(),
  { variant: "dialog" },
);
</script>

<template>
  <div class="flex flex-col md:flex-row gap-2 md:gap-4">
    <!--
      `Image`, not `SimpleImage`: this is the full-size art and the one place a card's
      picture is the subject rather than a thumbnail.
    -->
    <Image
      class="flex-[0_0_300px] lg:flex-[0_0_400px]"
      :src="cardImage(item.image_key)"
      :img-attributes="{ class: 'mx-auto w-full max-w-[400px]' }"
    />

    <div class="flex flex-col grow gap-2 md:gap-4">
      <CardDataNameBlock
        :id="item.id"
        :name="item.name || ''"
        :number="item.card_number"
        :original-name="item.original?.name"
      />

      <CardDataRowsBlock :item="item" />

      <CardDataDetailBlocks :item="item" />

      <CardDataQnaBlocks :item="item" />

      <CardDataSameNumberBlock :item="item" />
    </div>
  </div>
</template>
