<script setup lang="ts">
/**
 * Status, GitHub, Discord, About and Ko-fi, in one menu (ADR 0009 D21, D27, #48 §2).
 *
 * **This is a mobile bug fix, not a tidy-up.** Those four were `hidden sm:inline-flex`,
 * so a phone silently lost the data-status page, the source link and the Discord invite
 * altogether — they existed on desktop only, with nothing indicating anything was
 * missing. Collapsing them into one menu makes them reachable at every width *and*
 * shrinks the header from eight controls to four plus this.
 *
 * What stays outside the menu is deliberate (#48 §2): density, show-original, locale and
 * colour mode are *view* controls, used repeatedly while browsing. These are destinations,
 * used once.
 *
 * **Ko-fi is here rather than in the header (D27).** The support link is a destination
 * like the rest, and D21's whole point was cutting the header from eight controls to five
 * — re-adding one for a monetisation ask would reverse that on the surface D21 was about.
 * It is last, under the separator, so it reads as an aside rather than an interruption.
 */
import { Database, Ellipsis, Heart, Info, Sparkles } from "lucide-vue-next";

const localePath = useLocalePath();

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
      <!--
        `localePath`, not a bare `/status`. `strategy: "prefix"` gives every locale its own
        prefixed route, so the unprefixed path this used to carry is not a route in any
        locale — it left the reader's language on a link that looks like navigation.
      -->
      <DropdownMenuItem as-child>
        <NuxtLink :to="localePath('/status')">
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

      <!--
        A link now, not a dialog trigger (D27).

        This item used to set shared state that `AppInfoButton` watched, because a
        `DialogTrigger` cannot survive inside a menu item — choosing it closes the menu,
        which unmounts the trigger and takes the dialog with it. `/about` is a page, so the
        indirection and the state key both go: a destination is a link.
      -->
      <DropdownMenuItem as-child>
        <NuxtLink :to="localePath('/about')">
          <Info aria-hidden="true" /> {{ $t("About this site") }}
        </NuxtLink>
      </DropdownMenuItem>

      <!--
        Beside About rather than in the header: a destination, read once, which is the line
        D21 drew. It is here at all because a rebuilt site owes a returning reader an
        explanation of why it looks different, and nothing else on the site gives one.
      -->
      <DropdownMenuItem as-child>
        <NuxtLink :to="localePath('/changelog')">
          <Sparkles aria-hidden="true" /> {{ $t("changelog.title") }}
        </NuxtLink>
      </DropdownMenuItem>

      <DropdownMenuItem as-child>
        <a href="https://ko-fi.com/lichingchester" target="_blank" rel="noopener">
          <Heart aria-hidden="true" /> {{ $t("about.supportKofi") }}
        </a>
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
