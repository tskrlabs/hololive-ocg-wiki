<script setup lang="ts">
/**
 * The header: four view controls plus an overflow menu (ADR 0009 D21, #48 §2).
 *
 * The Discord link, the status link, the GitHub link and the about dialog moved into
 * `AppHeaderOverflowMenu`. They were `hidden sm:inline-flex` here, which meant a phone
 * silently lost three of them entirely — the menu is what makes them reachable at all
 * widths. What remains are the controls used *repeatedly while browsing*: density,
 * show-original, locale and colour mode.
 *
 * The `/api/info` fetch went with the Discord link. `useAsyncData`'s shared `"info"` key
 * still means the menu and the about dialog resolve one request between them.
 */
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
          Every icon-only control here carries a translated `.sr-only` label (#51).

          Four of the original eight had **no accessible name at all** and two more relied
          on `title`, which is not a reliable one: several screen readers ignore it when
          computing the name, and it is unreachable on touch devices entirely. It is a
          sighted-mouse-user tooltip, so it stays — it just cannot be the only name.

          Nothing here is `hidden sm:` any more. Density is the reason the rule was worth
          stating (#52): on a phone it is the difference between 4 cards per screen and 9,
          so hiding it below `sm` hid the control that matters most exactly where it
          matters most. The same argument retired the other three hides — they became the
          overflow menu rather than staying desktop-only.
        -->
        <AppDensitySwitcher />
        <AppOriginalSwitcher />
        <AppLanguageSwitcher />
        <AppColorModeSwitcher />
        <AppHeaderOverflowMenu />

        <!--
          The dialog only — its own trigger is off, because the menu opens it. It renders
          nothing until then.
        -->
        <AppInfoButton triggerless />
      </div>
    </div>
  </header>
</template>
