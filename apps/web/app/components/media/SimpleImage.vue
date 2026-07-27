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
// useIntersectionObserver(
//   imageRef,
//   ([{ isIntersecting }]) => {
//     if (isIntersecting && !shouldLoad.value) {
//       shouldLoad.value = true;
//     }
//   },
//   {
//     threshold: 0.01, // Start loading when even 1% is visible
//     rootMargin: "200px", // Start loading when within 200px of viewport
//   }
// );

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
    <picture>
      <source :srcset="`${webpSrc}`" type="image/webp" />
      <img :src="`${src}`" loading="lazy" v-bind="imgAttributes || {}" />
    </picture>
  </div>
</template>
