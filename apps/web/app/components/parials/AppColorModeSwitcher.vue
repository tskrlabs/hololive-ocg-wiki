<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { Button } from "@/components/ui/button";

const colorMode = useColorMode();

const toggleColorMode = () => {
  if (colorMode.preference !== "light") {
    colorMode.preference = "light";
  } else {
    colorMode.preference = "dark";
  }
};
</script>

<template>
  <Button variant="ghost" size="icon" @click="toggleColorMode">
    <Icon
      icon="radix-icons:sun"
      class="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0"
    />
    <Icon
      icon="radix-icons:moon"
      class="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100"
    />
    <span class="sr-only">Toggle theme</span>
  </Button>
</template>
