<script setup lang="ts">
/**
 * Placeholder — replaced by the real card list in commit 3 (the port).
 *
 * It exists so commit 2 is verifiable: `nuxt generate` needs at least one route to prove
 * the static build, the i18n prefix strategy and the asset pipeline actually work before
 * ~12k lines of ported code arrive on top of them.
 */
const { locale } = useI18n();
</script>

<template>
  <div class="flex min-h-svh flex-col items-center justify-center gap-2">
    <h1 class="text-2xl font-semibold">Hololive OCG Wiki</h1>
    <p class="text-muted-foreground text-sm">
      Phase 5 scaffold — locale {{ locale }}
    </p>
  </div>
</template>
