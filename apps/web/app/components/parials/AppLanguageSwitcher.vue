<script setup lang="ts">
import { Languages } from "lucide-vue-next";

const { locales } = useI18n();
const switchLocalePath = useSwitchLocalePath();
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button variant="ghost" size="icon">
        <Languages />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent>
      <template v-for="(_locale, index) in locales" :key="index">
        <DropdownMenuItem>
          <a :href="switchLocalePath(_locale.code)">
            {{ _locale.name }}
          </a>
        </DropdownMenuItem>
      </template>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
