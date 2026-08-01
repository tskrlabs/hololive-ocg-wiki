<script setup lang="ts">
import { Rows3, Grid3x3 } from "lucide-vue-next";

/**
 * Switches the card grid between art + name + number and art alone (D14, #37, #52).
 *
 * **In the header, and visible at every width** — unlike the four controls #51 found
 * hidden behind `sm:`. #37 put this in the filter rail, where a view preference sits
 * naturally beside the other view controls; #52 then measured 375×812 and moved it,
 * because on a phone density stops being a preference: comfortable shows **4 cards per
 * screen** against compact's **9**. A control that changes what you are looking at rather
 * than what you are filtering does not belong in a filter panel the phone hides anyway.
 *
 * The icon reports the *current* mode rather than the destination, matching
 * `AppColorModeSwitcher` beside it; `aria-pressed` carries the state for a screen reader,
 * which is the part D4 leaves no colour to say.
 *
 * ⚠️ **The card list is the only thing density controls, so this renders only there.**
 * `useCardDensity` is read by `CardListViewAPI`, `CardItem` and `CardTileSkeleton` —
 * every one of them inside the grid, which exists on `index` alone. On the card page and
 * the deck page the button sat in the header and toggled a value nothing on screen read:
 * a control that visibly changes state and changes nothing, which is worse than an absent
 * one because it teaches that the control does not work.
 *
 * The deck page is included deliberately. It *has* a compact mode, but a local
 * `compactModeState` ref with its own toggle in the page body — unrelated to this
 * composable, so this button never drove it there either. Unifying the two is a separate
 * question about whether one preference should span both surfaces; this only stops the
 * header claiming to own something it does not.
 *
 * The guard is `useRouteBaseName`, the same mechanism `AppFooterCurrentDeck` uses to keep
 * the Edit badge off the detail pages — one way of asking "which page is this", not two.
 */
const { density, toggle, isCompact } = useCardDensity();

const route = useRoute();
const getRouteBaseName = useRouteBaseName();

/** The card grid's page, and so the only page this control acts on. */
const isCardList = computed(() => getRouteBaseName(route) === "index");
</script>

<template>
  <Button
    v-if="isCardList"
    variant="ghost"
    size="icon"
    :title="$t('density.label')"
    :aria-pressed="isCompact"
    @click="toggle"
  >
    <Grid3x3 v-if="isCompact" class="w-5 h-5" aria-hidden="true" />
    <Rows3 v-else class="w-5 h-5" aria-hidden="true" />
    <!--
      The name states the mode, not just the control: "Card density" alone leaves a
      screen-reader user unable to tell which of the two they are in, and D4 denies the
      button a colour to say it with.
    -->
    <span class="sr-only">
      {{ $t("density.label") }} — {{ $t(`density.${density}`) }}
    </span>
  </Button>
</template>
