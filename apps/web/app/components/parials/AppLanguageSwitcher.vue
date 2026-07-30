<script setup lang="ts">
import { Languages } from "lucide-vue-next";

const { locales } = useI18n();
const switchLocalePath = useSwitchLocalePath();
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <!--
        Named, and it needs to be (#51). This carries the *same* Languages icon as
        `AppOriginalSwitcher` next to it, so without names the two are indistinguishable
        even to a sighted user — and a screen reader heard "button" for both.
      -->
      <Button variant="ghost" size="icon" :title="$t('Change language')">
        <Languages />
        <span class="sr-only">{{ $t("Change language") }}</span>
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
