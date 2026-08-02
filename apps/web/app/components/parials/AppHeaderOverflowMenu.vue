<script setup lang="ts">
/**
 * Status, GitHub, Discord and About, in one menu (ADR 0009 D21, #48 §2).
 *
 * **This is a mobile bug fix, not a tidy-up.** Those four were `hidden sm:inline-flex`,
 * so a phone silently lost the data-status page, the source link and the Discord invite
 * altogether — they existed on desktop only, with nothing indicating anything was
 * missing. Collapsing them into one menu makes them reachable at every width *and*
 * shrinks the header from eight controls to four plus this.
 *
 * What stays outside the menu is deliberate (#48 §2): density, show-original, locale and
 * colour mode are *view* controls, used repeatedly while browsing. These four are
 * destinations, used once.
 */
import { Database, Ellipsis, Info } from "lucide-vue-next";

// `$fetch<Info>` rather than a bare `$fetch`: without the explicit type argument,
// TypeScript tries to resolve "/api/info" against the generated route table and blows the
// instantiation depth limit on a union of every route in the app.
type Info = { "discord-invite-url"?: string };

const { data: info } = await useAsyncData<Info>(
  "info",
  () => $fetch<Info>("/api/info"),
  { default: () => ({}) },
);

const discordInviteUrl = computed(() => info.value?.["discord-invite-url"] ?? "");

/**
 * The about dialog's open state, shared with `AppInfoButton` (which renders the dialog).
 *
 * A `DialogTrigger` cannot live inside a menu item: choosing it closes the menu, which
 * unmounts the trigger and takes the dialog down with it. Setting shared state instead
 * means the menu closes and the dialog opens, which is what a reader expects.
 */
const infoOpen = useState("infoDialogOpen", () => false);
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button variant="ghost" size="icon" :title="$t('More')">
        <Ellipsis aria-hidden="true" />
        <span class="sr-only">{{ $t("More") }}</span>
      </Button>
    </DropdownMenuTrigger>

    <DropdownMenuContent align="end">
      <DropdownMenuItem as-child>
        <NuxtLink to="/status">
          <Database aria-hidden="true" /> {{ $t("status.title") }}
        </NuxtLink>
      </DropdownMenuItem>

      <DropdownMenuItem as-child>
        <a href="https://github.com/tskrlabs/hololive-ocg-wiki" target="_blank">
          <IconGithub class="size-4" /> {{ $t("Source code on GitHub") }}
        </a>
      </DropdownMenuItem>

      <!--
        Hidden rather than shown-and-dead when `/api/info` has not resolved or carries no
        invite: a menu entry that navigates nowhere is worse than one that is absent.
      -->
      <DropdownMenuItem v-if="discordInviteUrl" as-child>
        <a :href="discordInviteUrl" target="_blank">
          <IconDiscord class="size-4" /> {{ $t("Join the Discord server") }}
        </a>
      </DropdownMenuItem>

      <DropdownMenuSeparator />

      <DropdownMenuItem @click="infoOpen = true">
        <Info aria-hidden="true" /> {{ $t("About this site") }}
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
