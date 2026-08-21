<script setup lang="ts">
/**
 * The source link, as a header control from `lg` up.
 *
 * **A component rather than markup in `AppHeader`,** for the same reason the four
 * switchers are: `a11y.test.ts` mounts leaves and computes their accessible name, and a
 * control whose name lives inline in the header can only be tested by mounting the header.
 * This is icon-only, so its `.sr-only` span is its *entire* name (#51) — the glyph is
 * `aria-hidden`, deliberately and under test, because it once carried a `<title>` of its
 * own and the audit read "GitHubGitHub 原始碼", two names concatenating.
 *
 * **Icon-only is a width decision, not a preference.** Six inline icon+label destinations
 * cost roughly 960px in `es` against ~880px of usable row at `lg`. GitHub and Discord are
 * the two whose brand mark identifies them without a word, so they are the two that can
 * lose their label; the other four keep theirs and stay in the overflow menu at every
 * width. `title` is here for a sighted mouse user and is not the name.
 */
</script>

<template>
  <Button variant="ghost" size="icon" as-child :title="$t('Source code on GitHub')">
    <a href="https://github.com/tskrlabs/hololive-ocg-wiki" target="_blank" rel="noopener">
      <IconGithub class="size-4" />
      <span class="sr-only">{{ $t("Source code on GitHub") }}</span>
    </a>
  </Button>
</template>
