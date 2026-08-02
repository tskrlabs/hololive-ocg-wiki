<script setup lang="ts">
const { t, locale } = useI18n();
const { siteUrl } = useRuntimeConfig().public;

/**
 * Which container renders the deck, and whether it pushes (D18, amended).
 *
 * The page reads it because *it* owns the two containers — the panel's contents are the
 * same either way, so `DeckPanel` has no reason to know.
 */
const panel = useDeckPanel();

/**
 * `?set_code=hBP03` (ADR 0010) — read once on load, then kept in step.
 *
 * Here rather than in the rail or the search box because both of those are rendered
 * twice (mobile header and desktop rail), and a URL sync running in two places would
 * race itself. The page is the one thing that exists once.
 */
const setCodeUrl = useSetCodeUrl();
setCodeUrl.applyFromUrl();
setCodeUrl.syncToUrl();

// SEO Meta tags for the main page
useSeoMeta({
  title: t("Card List"),
  description: t("nuxtSiteConfig.description"),
  author: "Hololive OCG Wiki Contributors",
  ogTitle: t("Card List"),
  ogDescription: t("nuxtSiteConfig.description"),
  ogType: "website",
  ogUrl: siteUrl,
  ogImage: `${siteUrl}/icon.png`,
  ogSiteName: t("Card List"),
  twitterCard: "summary_large_image",
  twitterTitle: t("Card List"),
  twitterDescription: t("nuxtSiteConfig.description"),
  twitterImage: `${siteUrl}/icon.png`,
});

useHead({
  // The body must not scroll: the shell is exactly one viewport tall and the card
  // scroller does the scrolling inside it (#44). Without this, iOS Safari still
  // rubber-bands the whole document over a page that has nowhere to go.
  bodyAttrs: {
    class: "overflow-hidden",
  },
  htmlAttrs: {
    lang: locale.value,
  },
});
</script>

<template>
  <AppHeader>
    <!--
      Both are `lg:hidden`, because both move into the rail above that width (#36 §4).
      The filter trigger has no panel to open once the rail is permanent, and search
      belongs with the other query controls rather than in a header that was already
      eight icon buttons wide.
    -->
    <FilterAPI />

    <div class="grow lg:hidden">
      <SearchInputAPI />
    </div>
  </AppHeader>

  <!--
    Two columns from `lg`: the rail, then the grid (D10, #36).

    `min-h-0` on this row is load-bearing, as everywhere under the flex-column shell — a
    flex child defaults to `min-height: auto` and refuses to shrink below its content, so
    without it the region would grow to fit 2,448 cards and push the footer off-screen
    (#44).
  -->
  <div class="flex min-h-0 grow">
    <FilterRail />

    <!--
      The card list takes whatever the rail, the deck panel and the chrome leave. The
      scroller itself does the scrolling — this is `overflow-hidden` so nothing can scroll
      twice. See #44.

      When the deck panel opens beside it, this shrinks and the grid re-derives its
      columns from the width it has left. That needs no code: `CardListViewAPI` already
      observes its own width, and #43's rule turns a narrower box into fewer columns
      rather than smaller cards.
    -->
    <main class="relative min-w-0 grow min-h-0 overflow-hidden">
      <CardListViewAPI />
    </main>

    <!--
      The deck panel, **pushed** (D18, amended).

      A plain flex sibling — not a portal, not a dialog, no overlay and no focus trap — so
      the grid beside it stays visible *and* clickable. That is what makes "the panel is
      open" mean "I am building a deck": you pick cards from a live grid with the deck
      beside it, rather than opening a surface to check what you just added.

      Only from `xl`. Below that the rail and a 384px panel would leave the grid under two
      columns, so the sheet below takes over — `useDeckPanel` states the arithmetic.

      `v-if` rather than a hidden element: an `<aside>` that is only `hidden` still exists
      for the accessibility tree and for `useDeckCards`, which would fetch the deck's cards
      into a surface nobody can see.
    -->
    <aside
      v-if="panel.isOpen.value && panel.isPushed.value"
      id="deck-panel"
      class="hidden w-96 shrink-0 border-l bg-background xl:flex"
      :aria-label="$t('Deck')"
    >
      <DeckPanel />
    </aside>
  </div>

  <!--
    The same panel, **modal**, below `xl` (D18, amended).

    Here it does occlude the grid, so it is a real dialog and `useDeckPanel` stops
    coupling it to editing. One `DeckPanel`, two containers — D15's pattern, for the same
    reason: the containers differ in how they present the surface, not in what it is.
  -->
  <Sheet
    v-if="!panel.isPushed.value"
    :open="panel.isOpen.value"
    @update:open="panel.setOpen"
  >
    <SheetContent side="right" class="flex w-full flex-col gap-0 p-0 sm:max-w-md">
      <SheetHeader class="sr-only">
        <SheetTitle>{{ $t("Deck") }}</SheetTitle>
      </SheetHeader>

      <DeckPanel />
    </SheetContent>
  </Sheet>

  <AppFooter>
    <AppFooterCurrentDeck />
    <div class="ml-auto flex items-center gap-2">
      <AppFooterOptionsButton />
      <AppFooterDeckPanelButton />
      <AppFooterDeckButton />
    </div>
  </AppFooter>
</template>
