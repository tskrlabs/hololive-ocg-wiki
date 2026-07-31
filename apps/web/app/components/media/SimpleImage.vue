<script setup lang="ts">
/**
 * A card image with a placeholder while it decodes and a fallback when it cannot (#38 §3).
 *
 * The load and error handlers **already existed** here and the template bound neither —
 * no `@load`, no `@error`, no placeholder — so art popped in as it decoded and a broken
 * image rendered as the browser's default glyph. The synthetic fixture card `9000001` is
 * one such image, deliberately, so this is visible in local dev.
 *
 * Two things went with the wiring, both dead:
 *
 * - `shouldLoad` and a commented-out `useIntersectionObserver`. Nothing read the ref, and
 *   `loading="lazy"` is the browser's own version of the same idea.
 * - `webpSrc`, which rebuilt a `.webp` path by string surgery for a `<source>` element —
 *   except `useCardImage()` already returns a WebP URL (D9), so the `<source>` and the
 *   `<img>` resolved to the same file and the `<picture>` chose between one option.
 */
const props = defineProps<{
  src: string;
  /** The card's name. Required by every call site: art with no `alt` is unlabelled. */
  alt?: string;
  imgAttributes?: Record<string, string>;
  width?: string | number;
  height?: string | number;
}>();

const isLoading = ref(true);
const hasError = ref(false);

/**
 * Reset when the source changes.
 *
 * `RecycleScroller` **reuses** this component's DOM node for a different card as you
 * scroll, so without this a tile that once failed would keep showing the fallback for
 * every card that later lands in the same node — and one that had loaded would never show
 * a placeholder again.
 */
watch(
  () => props.src,
  () => {
    isLoading.value = true;
    hasError.value = false;
  },
);

const handleImageLoaded = () => {
  isLoading.value = false;
};

const handleImageError = () => {
  isLoading.value = false;
  hasError.value = true;
};

// Exposed for tests and parent components.
defineExpose({ isLoading, hasError });
</script>

<template>
  <div class="relative">
    <!--
      The placeholder sits *behind* the image at the card's aspect ratio, so there is no
      reflow when the bytes arrive and no flash of empty space before them. `--muted` and
      nothing else — D4 leaves the palette no accent hue.
    -->
    <div
      v-if="isLoading || hasError"
      class="absolute inset-0 flex items-center justify-center rounded-lg bg-muted"
      :class="isLoading && !hasError ? 'animate-pulse' : ''"
    >
      <!--
        A failed image says which card it was. The browser's broken-image glyph says only
        that something is missing, which the empty box already said.
      -->
      <span
        v-if="hasError"
        class="px-1 text-center font-mono text-xs break-all text-muted-foreground"
      >
        {{ alt }}
      </span>
    </div>

    <img
      :src="src"
      :alt="alt ?? ''"
      loading="lazy"
      decoding="async"
      v-bind="imgAttributes || {}"
      :class="[imgAttributes?.class, isLoading || hasError ? 'opacity-0' : '']"
      @load="handleImageLoaded"
      @error="handleImageError"
    />
  </div>
</template>
