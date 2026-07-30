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
        <!--
          Every icon-only control below carries a translated `.sr-only` label (#51).

          Four of these eight had **no accessible name at all** and two more relied on
          `title`, which is not a reliable one: several screen readers ignore it when
          computing the name, and it is unreachable on touch devices entirely. It is a
          sighted-mouse-user tooltip, so it stays — it just cannot be the only name.
        -->
        <Button
          variant="ghost"
          size="icon"
          as-child
          class="hidden sm:inline-flex"
          :title="$t('status.title')"
        >
          <NuxtLink to="/status">
            <Database class="w-5 h-5" />
            <span class="sr-only">{{ $t("status.title") }}</span>
          </NuxtLink>
        </Button>
        <AppOriginalSwitcher />
        <AppLanguageSwitcher />
        <AppColorModeSwitcher />
        <!--
          GitHub already had a name, from the `<title>` inside its SVG. Naming it here
          too is deliberate: the icon's own title is not ours to rely on, and it says
          only "GitHub" rather than what the link does.
        -->
        <Button
          variant="ghost"
          size="icon"
          as-child
          class="hidden sm:inline-flex"
          :title="$t('Source code on GitHub')"
        >
          <a
            href="https://github.com/tskrlabs/hololive-ocg-wiki"
            target="_blank"
          >
            <IconGithub class="w-5 h-5" />
            <span class="sr-only">{{ $t("Source code on GitHub") }}</span>
          </a>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          as-child
          class="hidden sm:inline-flex"
          :title="$t('Join the Discord server')"
        >
          <a :href="discordInviteUrl" target="_blank">
            <IconDiscord />
            <span class="sr-only">{{ $t("Join the Discord server") }}</span>
          </a>
        </Button>
        <AppInfoButton />
      </div>
    </div>
  </header>
</template>
