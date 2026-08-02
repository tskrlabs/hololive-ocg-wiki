<script setup lang="ts">
/**
 * The source-language form of one label, shown beside its translation.
 *
 * Renders nothing when there is no original to show — which is the common case, because
 * `LocalizedCard.original` only carries fields whose source and translation differ. A
 * card whose art name was left in Japanese has nothing to reveal about it, and this
 * component's absence says so without the parent needing a condition.
 *
 * Deliberately not a tooltip. The whole purpose is comparison: a reader checking whether
 * "Shirakami Fubuki" is the card they know as 白上フブキ wants both at once, not one on
 * hover.
 *
 * **The filename is the registered name, and that is load-bearing** (#61). `nuxt.config`
 * sets `pathPrefix: false`, so `card-list/` contributes nothing — this file registered as
 * `OriginalText` while all five call sites asked for `CardListOriginalText`. Vue resolves
 * that to nothing and warns to the console rather than failing, so the source names were
 * invisible on the detail page and in the dialog from the day the feature shipped until
 * #61 renamed the file to what the callers already wrote. Every sibling in this folder is
 * self-prefixed for the same reason; this was the only one that was not.
 */
defineProps<{
  /** The source-language text, or null/undefined when it matches the translation. */
  text?: string | null;
}>();

const { enabled } = useShowOriginal();
</script>

<template>
  <span
    v-if="enabled && text"
    class="text-muted-foreground font-normal text-[0.9em] ml-1.5"
    :lang="'ja'"
  >
    {{ text }}
  </span>
</template>
