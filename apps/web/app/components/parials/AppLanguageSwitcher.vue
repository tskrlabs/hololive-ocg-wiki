<script setup lang="ts">
import { Languages } from "lucide-vue-next";

const { locales } = useI18n();
const switchLocalePath = useSwitchLocalePath();
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <!--
        Named, and it needs to be (#51) — a screen reader heard "button" here.
        `Languages` now belongs to this control alone: `AppOriginalSwitcher` beside it
        carried the same glyph, which left the two indistinguishable to a *sighted* user
        no matter how well named they were. It takes `Type` instead; see its own note.
      -->
      <Button variant="ghost" size="icon" :title="$t('Change language')">
        <Languages aria-hidden="true" />
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
