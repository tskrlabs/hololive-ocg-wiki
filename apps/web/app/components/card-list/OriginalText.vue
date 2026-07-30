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
