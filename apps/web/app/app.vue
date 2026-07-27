<script setup lang="ts">
// TODO(commit 3): restore `import { Toaster } from "@/components/ui/sonner"` and the
// <Toaster /> mount below once the shadcn components are ported. Held back so the
// scaffold builds on its own — see nuxt.config.ts.
import "vue-sonner/style.css"; // vue-sonner v2 requires this import

const { locale } = useI18n();
const route = useRoute();
const { siteUrl } = useRuntimeConfig().public;

useHead({
  htmlAttrs: { lang: locale },
  link: [
    // The canonical origin comes from config, not a literal. v1 hardcoded
    // `hololive-ocg-wiki.lichingchester.dev` here and in four other files, which is why
    // changing domains is a chore at all (nuxt.config.ts, SITE_URL).
    { rel: "canonical", href: () => `${siteUrl}${route.path}` },
  ],
});
</script>

<template>
  <!-- <Toaster rich-colors close-button position="top-center" /> — restored in commit 3 -->

  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
