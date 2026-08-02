<script setup lang="ts">
import { Type } from "lucide-vue-next";

/**
 * Toggles the source-language text beside every card label.
 *
 * Sits in the header next to the language switcher because it is the same kind of thing
 * — a reading preference that applies to the whole site, not to one card or one deck.
 *
 * ⚠️ **`Type`, not `Languages`** — the two sit side by side and `Languages` belongs to the
 * one that actually switches locale. Carrying the same glyph made them indistinguishable
 * to a sighted user, which #51 had already noted and fixed only for screen readers by
 * giving each an `.sr-only` name. That left the visual collision standing, and a name a
 * mouse user cannot hear does not help them tell two identical buttons apart.
 *
 * `Type` is a letterform: this toggle reveals the source-language *text* beside a name.
 * It is about showing more typography, not about changing language — which is precisely
 * the distinction the shared icon destroyed.
 *
 * Hidden on the `ja` locale: the source language *is* what is being shown, so
 * `card.original` is absent from every response and the button would toggle nothing.
 *
 * **No longer `hidden sm:inline-flex`.** It was one of the four controls #51 found
 * unreachable on a phone, and the reason to restore it is now stronger than symmetry:
 * [#29](https://github.com/tskrlabs/hololive-ocg-wiki/issues/29) was that this toggle had
 * nothing to act on in the card list, and the tile's name line is what fixes that. Hiding
 * the control on mobile would re-open the issue exactly where the screen is smallest and
 * a familiar name is most useful.
 */
const { enabled, toggle } = useShowOriginal();
const { locale } = useI18n();

const isSourceLocale = computed(() => locale.value === "ja");
</script>

<template>
  <Button
    v-if="!isSourceLocale"
    variant="ghost"
    size="icon"
    :title="$t('Show original names')"
    :aria-pressed="enabled"
    @click="toggle"
  >
    <Type class="w-5 h-5" :class="enabled ? '' : 'opacity-40'" aria-hidden="true" />
    <!--
      `title` was the only name here, and it is not a reliable one (#51): several screen
      readers ignore it when computing the accessible name, and it is unreachable on
      touch entirely. It stays for the sighted tooltip; this is the actual name.
    -->
    <span class="sr-only">{{ $t("Show original names") }}</span>
  </Button>
</template>
