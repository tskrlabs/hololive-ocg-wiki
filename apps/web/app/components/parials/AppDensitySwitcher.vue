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
 */
const { density, toggle, isCompact } = useCardDensity();
</script>

<template>
  <Button
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
