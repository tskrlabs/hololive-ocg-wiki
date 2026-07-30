<script setup lang="ts">
import { Languages } from "lucide-vue-next";

/**
 * Toggles the source-language text beside every card label.
 *
 * Sits in the header next to the language switcher because it is the same kind of thing
 * — a reading preference that applies to the whole site, not to one card or one deck.
 *
 * Hidden on the `ja` locale: the source language *is* what is being shown, so
 * `card.original` is absent from every response and the button would toggle nothing.
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
    class="hidden sm:inline-flex"
    @click="toggle"
  >
    <Languages class="w-5 h-5" :class="enabled ? '' : 'opacity-40'" />
    <!--
      `title` was the only name here, and it is not a reliable one (#51): several screen
      readers ignore it when computing the accessible name, and it is unreachable on
      touch entirely. It stays for the sighted tooltip; this is the actual name.
    -->
    <span class="sr-only">{{ $t("Show original names") }}</span>
  </Button>
</template>
