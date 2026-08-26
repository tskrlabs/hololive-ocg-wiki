<script setup lang="ts">
/**
 * A deck slot that names no card (ADR 0014).
 *
 * Two ways to arrive here, and they deserve different copy:
 *
 * - **The reference is an `image_key`** the API returned nothing for — a card withdrawn
 *   from the official list since the deck was saved. The key still carries a card number
 *   (`hEB01/hBP01-051_UR_02` → `hBP01-051`), so the slot can say *which* card is missing
 *   and link to its set.
 * - **The reference is a bare legacy id** the snapshot does not cover — hand-edited
 *   storage, or a code from some other tool. There is nothing to extract, so the slot says
 *   plainly that the card cannot be identified rather than inventing a suggestion.
 *
 * **It occupies the slot rather than vanishing.** Dropping it would make a missing card in
 * a 50-card deck invisible, and the user is the only one who knows what was meant.
 *
 * The link is `?set_code=`, the one filter with a URL (ADR 0010). Not a search link:
 * filter state is otherwise in-memory only, so a `?q=` would need query-param plumbing
 * that ADR deliberately scoped out. The card number is rendered as selectable text either
 * way, so it can be copied into the search box when the link is not enough.
 */
import type { UnresolvedDeckCard } from "~/composables/useDeckCards";

const props = defineProps<{ item: UnresolvedDeckCard }>();

const localePath = useLocalePath();
const decks = useDecks();
const { isEditing } = decks;

/**
 * Take the slot out of the deck.
 *
 * The only way to remove one: every other control routes through
 * `sectionForCardType`, which needs a `Card`, and an unresolved slot has none. Without
 * this a withdrawn card is stuck in the deck permanently — visible, unremovable, and
 * keeping the deck off its 50-card limit.
 *
 * Editing-gated like the add and remove buttons on a real tile: outside edit mode the
 * deck is being read, not changed.
 */
const remove = () => {
  if (!isEditing.value) return;
  decks.removeRefFromDeck(props.item.ref);
};
</script>

<template>
  <div
    class="relative flex aspect-400/559 flex-col items-center justify-center gap-1.5 rounded-sm border border-dashed border-muted-foreground/40 bg-muted/30 p-2 text-center"
  >
    <Icon name="lucide:help-circle" class="size-5 text-muted-foreground" />

    <p class="text-xs font-medium text-muted-foreground">
      {{ $t("deck.migration.unresolvedTitle") }}
    </p>

    <!-- Nameable: say which card, and offer its set. -->
    <template v-if="item.cardNumber">
      <p class="text-[11px] font-medium tabular-nums select-all">
        {{ item.cardNumber }}
      </p>
      <p class="text-[10px] leading-tight text-muted-foreground/80">
        {{ $t("deck.migration.unresolvedDetail") }}
      </p>
      <NuxtLink
        v-if="item.setCode"
        :to="{ path: localePath('/'), query: { set_code: item.setCode } }"
        class="rounded-sm bg-secondary px-2 py-1 text-[10px] hover:bg-secondary/80"
      >
        {{ $t("deck.migration.unresolvedBrowseSet", { set: item.setCode }) }}
      </NuxtLink>
    </template>

    <!-- Not nameable: no card number exists, so no suggestion is possible. -->
    <p v-else class="text-[10px] leading-tight text-muted-foreground/80">
      {{ $t("deck.migration.unresolvedUnknown") }}
    </p>

    <span v-if="item.count > 1" class="text-[10px] text-muted-foreground/80">
      ×{{ item.count }}
    </span>

    <!--
      Removal, only while editing. Labelled with the card number where there is one, so a
      screen reader hears which slot is being removed rather than the same string on every
      tile (#51's finding).
    -->
    <button
      v-if="isEditing"
      class="mt-0.5 rounded-sm bg-secondary/95 px-2 py-1 text-[10px] hover:bg-destructive hover:text-destructive-foreground"
      :aria-label="
        item.cardNumber
          ? $t('deck.removeAllCopies', { name: item.cardNumber })
          : $t('deck.migration.unresolvedRemove')
      "
      @click.prevent="remove"
    >
      {{ $t("deck.migration.unresolvedRemove") }}
    </button>
  </div>
</template>
