<script setup lang="ts"></script>

<template>
  <footer
    class="border-solid sticky bottom-0 z-50 w-full border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90"
  >
    <div class="p-2 md:p-4 flex items-center">
      <slot />
    </div>
  </footer>
</template>
