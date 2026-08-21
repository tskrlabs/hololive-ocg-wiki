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
 * The `/api/info` fetch went with the Discord link, and stays in the menu for the Discord
 * invite. The about *dialog* is gone — `/about` is a page now, so the menu links to it.
 *
 * **From `lg`, GitHub and Discord come back out of the menu** (D28). At that width the row
 * has ~880px free — both slot children are `lg:hidden` on the home page and search has
 * moved to the rail — so the two destinations whose brand mark needs no label sit inline,
 * behind a divider that keeps D21's view-control/destination line visible. The menu stays
 * at every width for the four that need their labels: six inline icon+label destinations
 * do not fit at `lg` in `es`, `ja` or `th`.
 *
 * **The wordmark is the header's own, not the slot's.** The slot holds per-page
 * navigation — a back link on the card and deck pages — and on the home page both of its
 * children are `lg:hidden`, so from `lg` up the slot rendered nothing and `ml-auto` pushed
 * the controls against an empty corner. Naming the site is not a page's decision to
 * remember, so it does not live at three call sites.
 */
const localePath = useLocalePath();
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
      <!--
        The wordmark (D27).

        Text, not the crest: `icon.png` is saturated lilac, and D3 gives card art the only
        saturated pixels on screen. Set at the body weight the palette already uses —
        D4 leaves no accent hue, so identity here is type and spacing.

        `hidden lg:block`, which is the complement of the two slot children the home page
        passes. Below `lg` the search field owns this row and a wordmark would take the
        width it needs; from `lg` search moves into the rail and this fills the corner it
        leaves. So exactly one thing occupies the left at every width.

        Not a `<h1>`: pages own their heading, and a site name repeated as the top heading
        of every page displaces the one that describes the page.
      -->
      <NuxtLink
        :to="localePath('/')"
        class="hidden shrink-0 text-sm font-medium tracking-tight lg:block"
      >
        Hololive OCG Wiki
      </NuxtLink>

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

        <!--
          **The two destinations that fit, from `lg` up (D28).**

          This is `hidden lg:` where the header used to have `hidden sm:`, and the two are
          not the same move. The old hides made status, GitHub and Discord *unreachable* on
          a phone — they existed on desktop only, with nothing indicating anything was
          missing. Here the overflow menu still holds every destination below `lg`, so
          nothing is ever lost; an item is on the shelf at one width and in the drawer at
          another. D21's fix was reachability, and reachability is intact.

          Only these two, because only these two fit. Six inline icon+label destinations
          cost ~960px in `es` against ~880px of usable row at `lg`, and these are the two
          carrying a brand mark that identifies itself without a word. The other four need
          their labels and stay in the menu, which is therefore still here at every width.

          The divider is what survives of D21's real criterion. The line was never a count
          — it is a kind test, *view controls used repeatedly while browsing* on the left of
          it, *destinations used once* on the right — and the menu used to draw that line by
          being a separate surface. Inline, spacing has to draw it.
        -->
        <div class="hidden items-center lg:flex">
          <div class="mx-1 h-5 w-px shrink-0 bg-border" aria-hidden="true" />
          <AppGithubLink />
          <AppDiscordLink />
        </div>

        <AppHeaderOverflowMenu />
      </div>
    </div>
  </header>
</template>
