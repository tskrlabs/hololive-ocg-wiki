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
 * **It is shaped exactly like a card tile**, and that is load-bearing rather than
 * cosmetic. A real tile is one `aspect-400/559` image with its controls positioned
 * *absolutely* on top, so it contributes only that ratio to the grid row. The first
 * version of this stacked its text and buttons in normal flow, so it grew taller than the
 * cards beside it and stretched the whole row — the deck read as broken rather than as a
 * deck with one card missing.
 *
 * The link is `?set_code=`, the one filter with a URL (ADR 0010). Not a search link:
 * filter state is otherwise in-memory only, so a `?q=` would need query-param plumbing
 * that ADR deliberately scoped out. The card number is rendered as selectable text either
 * way, so it can be copied into the search box when the link is not enough.
 */
import { Trash2 } from "lucide-vue-next";
import type { UnresolvedDeckCard } from "~/composables/useDeckCards";

const props = defineProps<{
  item: UnresolvedDeckCard;
  /** `small` in the deck panel, `large` on the detail page — matches `CardCountBadge`. */
  size?: "small" | "large";
}>();

const localePath = useLocalePath();
const decks = useDecks();
const { isEditing } = decks;

/**
 * Take the slot out of the deck.
 *
 * The only way to remove one: every other control routes through `sectionForCardType`,
 * which needs a `Card`, and an unresolved slot has none. Without this a withdrawn card is
 * stuck in the deck permanently — visible, unremovable, and keeping the deck off its
 * 50-card limit.
 *
 * Not gated on edit mode. The add and remove buttons on a real tile are, because they
 * change a deck the user can still read correctly; this slot is already wrong, and making
 * the fix reachable only from edit mode hides the repair behind a mode the user has no
 * reason to think they need.
 */
const remove = () => decks.removeRefFromDeck(props.item.ref);
</script>

<template>
  <div class="relative flex">
    <!--
      The same `aspect-400/559` box a card image occupies, so the grid row keeps its
      height. Everything else is layered on top of it, exactly as a real tile does.
    -->
    <div
      class="aspect-400/559 w-full rounded-sm border border-dashed border-muted-foreground/40 bg-muted/30"
    >
      <div
        class="flex h-full flex-col items-center justify-center gap-1 overflow-hidden p-1.5 text-center"
      >
        <Icon name="lucide:help-circle" class="size-4 shrink-0 text-muted-foreground" />

        <p class="text-[10px] leading-tight font-medium text-muted-foreground">
          {{ $t("deck.migration.unresolvedTitle") }}
        </p>

        <!-- Nameable: say which card, and offer its set. -->
        <template v-if="item.cardNumber">
          <p class="text-[11px] leading-none font-semibold tabular-nums select-all">
            {{ item.cardNumber }}
          </p>
          <NuxtLink
            v-if="item.setCode"
            :to="{ path: localePath('/'), query: { set_code: item.setCode } }"
            class="max-w-full truncate rounded-sm bg-secondary px-1.5 py-0.5 text-[10px] hover:bg-secondary/80"
          >
            {{ $t("deck.migration.unresolvedBrowseSet", { set: item.setCode }) }}
          </NuxtLink>
        </template>

        <!-- Not nameable: no card number exists, so no suggestion is possible. -->
        <p
          v-else
          class="line-clamp-3 text-[9px] leading-tight text-muted-foreground/80"
        >
          {{ $t("deck.migration.unresolvedUnknown") }}
        </p>
      </div>
    </div>

    <!--
      Removal, in the same corner and the same shape as a real tile's "remove all", so it
      reads as the same control rather than a new one.
    -->
    <div class="absolute top-0 right-0 flex flex-col gap-1 p-1">
      <button
        class="size-7 rounded-sm bg-destructive/90 text-destructive-foreground"
        :aria-label="
          item.cardNumber
            ? $t('deck.removeAllCopies', { name: item.cardNumber })
            : $t('deck.migration.unresolvedRemove')
        "
        :title="$t('deck.migration.unresolvedRemove')"
        @click.prevent="remove"
      >
        <div class="flex items-center justify-center text-xs">
          <Trash2 class="size-4" aria-hidden="true" />
        </div>
      </button>
    </div>

    <CardCountBadge :count="item.count" :size="size ?? 'small'" />
  </div>
</template>
