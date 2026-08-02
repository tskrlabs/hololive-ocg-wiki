<!--
  The app shell.

  **A fixed-height flex column, not a `min-h` page that grows** (#44). The distinction is
  the whole fix: while the shell could grow, the card scroller had no height to inherit
  and was given `height: 100dvh` — a full viewport, *between* a sticky header and a
  sticky footer, so ~138px of the list sat permanently underneath the chrome (17% of an
  800px viewport).

  Now the shell is exactly one viewport tall and the chrome are ordinary flex children.
  They stay put because nothing scrolls past them, not because they are `sticky`, and the
  space left between them is a real number the middle region can inherit with `h-full`.
  No `calc()` and no magic offsets, and it re-derives itself if the chrome height ever
  changes.

  The consequence for every page using this layout: the page no longer scrolls, so each
  one owns its own scroll region and must mark it `min-h-0 overflow-y-auto`. `min-h-0` is
  not optional — a flex child's default `min-height: auto` refuses to shrink below its
  content, which would push the footer off-screen and restore the bug in a new place.
-->
<template>
  <div class="relative flex h-dvh flex-col overflow-hidden bg-background">
    <slot />
  </div>
</template>
