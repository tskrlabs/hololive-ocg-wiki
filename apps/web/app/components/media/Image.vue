<script setup lang="ts">
const props = defineProps<{
  src: string;
  imgAttributes?: Record<string, string>;
  width?: string | number;
  height?: string | number;
}>();

const isLoading = ref(true);
const hasError = ref(false);
const shouldLoad = ref(false);
const imageRef = ref(null);

// Only start loading when in viewport or near it
useIntersectionObserver(
  imageRef,
  ([entry]) => {
    if (entry?.isIntersecting && !shouldLoad.value) {
      shouldLoad.value = true;
    }
  },
  {
    threshold: 0.01, // Start loading when even 1% is visible
    rootMargin: "200px", // Start loading when within 200px of viewport
  }
);

const webpSrc = computed(() => {
  // Extract the base name without extension
  const baseName = props.src.substring(0, props.src.lastIndexOf("."));
  return `${baseName}.webp`;
});

const handleImageLoaded = () => {
  isLoading.value = false;
};

const handleImageError = () => {
  isLoading.value = false;
  hasError.value = true;
};

// Expose loading state for testing or parent components
defineExpose({
  isLoading,
  hasError,
  shouldLoad,
});
</script>

<template>
  <div class="relative" ref="imageRef">
    <!-- Skeleton placeholder -->
    <Skeleton
      v-if="isLoading"
      :class="['absolute inset-0 z-0', imgAttributes?.class || '']"
      :style="{
        width: width ? `${width}px` : '100%',
        height: height ? `${height}px` : '100%',
      }"
    />

    <!-- Actual image -->
    <template v-if="shouldLoad">
      <picture
        :class="[
          isLoading ? 'opacity-0' : 'opacity-100',
          'transition-opacity duration-300',
        ]"
      >
        <source :srcset="`${webpSrc}`" type="image/webp" />
        <img
          :src="`${src}`"
          loading="lazy"
          v-bind="imgAttributes || {}"
          @load="handleImageLoaded"
          @error="handleImageError"
        />
      </picture>
    </template>

    <!-- Fallback for error state -->
    <div
      v-if="hasError"
      class="absolute inset-0 flex items-center justify-center bg-gray-200 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
      :style="{
        width: width ? `${width}px` : '100%',
        height: height ? `${height}px` : '100%',
      }"
    >
      <span class="text-sm">Image failed to load</span>
    </div>
  </div>
</template>
