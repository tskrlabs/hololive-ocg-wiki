<script setup lang="ts">
import { Database } from "lucide-vue-next";

/**
 * The Discord link comes from `/api/info` (D11), and is fetched **once** for the whole
 * app rather than separately here.
 *
 * v1 duplicated the entire fetch-and-parse block from `AppInfoButton` into this file —
 * including a `safeJsonParse` helper for the case where `$fetch` returned a string,
 * which it did because raw.githubusercontent.com serves JSON as text/plain. Reading from
 * our own Worker, the response is already parsed, and `useAsyncData` with a shared key
 * means the header and the info dialog resolve the same request.
 */
type Info = { "discord-invite-url"?: string };

const { data: info } = await useAsyncData<Info>(
  "info",
  () => $fetch<Info>("/api/info"),
  { default: () => ({}) },
);

const discordInviteUrl = computed(() => info.value?.["discord-invite-url"] ?? "");
</script>

<template>
  <!--
    A flex child of the shell, not `sticky` (#44). Nothing scrolls past it now — the
    scroll region is the sibling below — so stickiness bought nothing and cost the
    scroller a reliable height, which is what left ~138px of the card list hidden
    underneath this bar. `shrink-0` keeps it at its natural height when the middle
    region is under pressure.
  -->
  <header class="border-solid shrink-0 z-50 w-full border-b bg-background">
    <div class="p-2 md:p-4 flex items-center gap-2">
      <slot />

      <div class="flex ml-auto">
        <Button
          variant="ghost"
          size="icon"
          as-child
          class="hidden sm:inline-flex"
          :title="$t('status.title')"
        >
          <NuxtLink to="/status">
            <Database class="w-5 h-5" />
          </NuxtLink>
        </Button>
        <AppOriginalSwitcher />
        <AppLanguageSwitcher />
        <AppColorModeSwitcher />
        <Button
          variant="ghost"
          size="icon"
          as-child
          class="hidden sm:inline-flex"
        >
          <a
            href="https://github.com/tskrlabs/hololive-ocg-wiki"
            target="_blank"
          >
            <IconGithub class="w-5 h-5" />
          </a>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          as-child
          class="hidden sm:inline-flex"
        >
          <a :href="discordInviteUrl" target="_blank">
            <IconDiscord />
          </a>
        </Button>
        <AppInfoButton />
      </div>
    </div>
  </header>
</template>
