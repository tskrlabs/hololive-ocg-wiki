<script setup lang="ts">
const props = defineProps({
  count: {
    type: Number,
    required: true,
  },
  size: {
    type: String,
    default: "normal",
    validator: (value: string) => ["small", "normal", "large"].includes(value),
  },
});
</script>

<template>
  <span
    class="absolute top-[1px] left-[1px] -translate-1/5 bg-primary/95 rounded-full flex items-center justify-center"
    :class="{
      'size-4.5 md:size-6.5': size === 'small',
      'size-5 md:size-6.5': size === 'normal',
      'size-7 md:size-8': size === 'large',
    }"
  >
    <span
      class="flex items-center justify-center text-white dark:text-black leading-none font-semibold"
      :class="{
        'text-[8px] md:text-sm': size === 'small',
        'text-xs md:text-sm': size === 'normal',
        'text-base md:text-md': size === 'large',
      }"
    >
      {{ count }}
    </span>
  </span>
  <!-- <span
    class="absolute right-0 bottom-0 bg-primary/95 rounded-md flex items-center justify-center border-2 border-white dark:border-secondary"
    :class="{
      'size-4 md:size-4': size === 'small',
      'size-4 md:size-6': size === 'normal',
      'size-7 md:size-8': size === 'large',
    }"
  >
    <span
      class="flex items-center justify-center text-white dark:text-black leading-none font-semibold"
      :class="{
        'text-xs md:text-sm': size === 'small',
        'text-sm md:text-base': size === 'normal',
        'text-base md:text-md': size === 'large',
      }"
    >
      {{ count }}
    </span>
  </span> -->
</template>
