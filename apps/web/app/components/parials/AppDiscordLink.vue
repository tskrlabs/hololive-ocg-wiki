<script setup lang="ts">
/**
 * The Discord invite, as a header control from `lg` up.
 *
 * **The invite URL comes from `/api/info`, so this control does not exist until a fetch
 * resolves** — and that is a different problem in the header than it was in the menu.
 * Inside a portalled dropdown, an item that appears late is unobserved: the menu is shut
 * when the fetch lands. In the header row it pops into existence mid-load and shifts every
 * control left of it, which is layout shift on the one element visible on every page.
 *
 * So the slot is reserved: a `size-9` placeholder holds the same 36px the button will
 * occupy, and the button replaces it in place. The placeholder is inert — not a button,
 * not focusable, `aria-hidden` — so the "hidden rather than shown-and-dead" rule the
 * overflow menu states still holds. Nothing invites a click on a link that goes nowhere;
 * the space simply stops moving.
 *
 * The `useAsyncData` key is shared with `AppHeaderOverflowMenu` deliberately. Nuxt
 * de-duplicates by key, so the menu and this control are one request, and the menu keeps
 * its own copy below `lg` where this is hidden.
 *
 * Icon-only, so the `.sr-only` span is the whole accessible name (#51); the glyph is
 * `aria-hidden` under test.
 */
type Info = { "discord-invite-url"?: string };

// **Not awaited**, unlike the identical call in `AppHeaderOverflowMenu`. A top-level
// `await` makes this a Suspense boundary, and the header renders on every page — blocking
// it on a network call to decide whether one 36px slot is a link would delay the whole row
// for the control least worth waiting on. The placeholder *is* the pending state, so the
// fetch can land whenever it lands. Same key, so it is still one request.
const { data: info } = useAsyncData<Info>(
  "info",
  () => $fetch<Info>("/api/info"),
  { default: () => ({}) },
);

const discordInviteUrl = computed(() => info.value?.["discord-invite-url"] ?? "");
</script>

<template>
  <Button
    v-if="discordInviteUrl"
    variant="ghost"
    size="icon"
    as-child
    :title="$t('Join the Discord server')"
  >
    <a :href="discordInviteUrl" target="_blank" rel="noopener">
      <IconDiscord class="size-4" />
      <span class="sr-only">{{ $t("Join the Discord server") }}</span>
    </a>
  </Button>

  <!-- The reserved slot. Inert: no name, no focus, no pointer target. -->
  <div v-else class="size-9 shrink-0" aria-hidden="true" />
</template>
