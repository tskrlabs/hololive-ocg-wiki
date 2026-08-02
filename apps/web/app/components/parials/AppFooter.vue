<script setup lang="ts"></script>

<template>
  <!-- A flex child of the shell rather than `sticky`; see AppHeader and #44. -->
  <footer
    class="border-solid shrink-0 z-50 w-full border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90"
  >
    <div class="p-2 md:p-4 flex items-center">
      <slot />
    </div>
  </footer>
</template>
