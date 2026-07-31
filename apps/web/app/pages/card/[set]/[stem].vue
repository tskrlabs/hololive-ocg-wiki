<script setup lang="ts">
/**
 * A card's own page (ADR 0009 D6, D15; #33, #39).
 *
 * `/{locale}/card/{set}/{stem}` — the two segments are `image_key` verbatim. This is the
 * page a link, a refresh or a crawler lands on; clicking a tile in the grid opens the
 * dialog instead and pushes this URL, so the two are the same card in two containers.
 *
 * **This is what Phase 8 exists for.** Before it, a card had no URL at all: the only way
 * to share one was to describe it, and the back gesture on mobile exited the list
 * entirely rather than closing the dialog. Launch is a one-time SEO event and 2,463 card
 * URLs cannot be retrofitted without a second crawl.
 */
import type { Card, Locales } from "@/types/card";
import { cardDescription, cardTitle, cardImageUrl } from "@holo/schema/card-meta";

const route = useRoute();
const { locale, t } = useI18n();
const localePath = useLocalePath();
const cardQuery = useCardQuery();
const { siteUrl, imageBaseUrl } = useRuntimeConfig().public;

/**
 * When the same card is already showing as a dialog over the list, this page renders
 * nothing (D15, #39).
 *
 * The URL is one thing and has two presentations: reached by clicking a tile it is an
 * overlay; opened cold it is this page. Both mount — vue-router has already swapped to
 * this route by the time the dialog appears — so exactly one of them must draw.
 */
const { isOverlay } = useCardRoute();

const set = computed(() => String(route.params.set ?? ""));
const stem = computed(() => String(route.params.stem ?? ""));

const card = ref<Card | null>(null);
/**
 * Three outcomes, not two (#38 §5).
 *
 * A card that does not exist is **permanent** and a fetch that failed is **retryable**,
 * and they need different words: "this card doesn't exist" beside a Retry button is
 * nonsense, and "something went wrong" for a mistyped URL sends someone to reload a page
 * that will never work.
 */
const status = ref<"loading" | "ready" | "notFound" | "error">("loading");

async function load() {
  // The dialog is already fetching and showing this card; a second request and a second
  // rendering would be pure duplication.
  if (isOverlay.value) return;

  status.value = "loading";
  try {
    const found = await cardQuery.getCardByKey(
      set.value,
      stem.value,
      locale.value as Locales,
    );
    card.value = found ?? null;
    status.value = found ? "ready" : "notFound";
  } catch {
    card.value = null;
    status.value = "error";
  }
}

await load();

// The key is in the path and the locale switches in place, so both are navigations that
// keep this component mounted — without this, switching language would leave the previous
// locale's card on screen.
watch([set, stem, locale], load);

/**
 * The page's `<head>`, from the same function the Worker injects with (D8).
 *
 * This is the half that runs after hydration. unhead *adopts* the Worker's tags rather
 * than duplicating them — it keys existing `<head>` children by `dedupeKey` on mount — so
 * these update those elements in place, **provided both sides emit the same values**. A
 * mismatch would be cloaking, which is why neither side writes its own tag list.
 */
watchEffect(() => {
  if (isOverlay.value) return;

  if (!card.value) {
    useSeoMeta({ title: t("Card not found") });
    return;
  }

  const description = cardDescription(card.value);
  const image = cardImageUrl(card.value.image_key, imageBaseUrl);
  // `cardTitle()` already ends in "| Hololive OCG Wiki", and `nuxt-seo-utils` appends
  // the site name to any `title` it is given — which produced it twice. `titleTemplate`
  // opts this page out, because the shared function has to own the whole string: the
  // Worker injects a `<title>` with no template to apply.
  const title = cardTitle(card.value);

  useSeoMeta({
    title,
    titleTemplate: "%s",
    description,
    ogType: "article",
    ogTitle: title,
    ogDescription: description,
    ogUrl: `${siteUrl}/${locale.value}/card/${card.value.image_key}`,
    ogImage: image,
    ogSiteName: "Hololive OCG Wiki",
    twitterCard: "summary_large_image",
    twitterTitle: title,
    twitterDescription: description,
    twitterImage: image,
  });
});
</script>

<template>
  <!--
    Nothing at all when the dialog is already showing this card (D15). Both this route
    and the dialog are mounted after a tile click; exactly one of them draws.
  -->
  <template v-if="isOverlay" />

  <template v-else>
  <AppHeader>
    <Button variant="ghost" size="sm" as-child>
      <NuxtLink :to="localePath('/')">{{ $t("Card List") }}</NuxtLink>
    </Button>
  </AppHeader>

  <!--
    The page scrolls its own region, as every page must under the flex-column shell
    (#44, P3). `min-h-0` is load-bearing: a flex child refuses to shrink below its content
    without it, which would push the footer off-screen.
  -->
  <main class="min-h-0 grow overflow-y-auto">
    <div class="mx-auto w-full max-w-5xl p-4">
      <!-- Loading: a detail-shaped skeleton, since there is no grid behind this to dim. -->
      <div v-if="status === 'loading'" class="flex flex-col gap-4 md:flex-row">
        <div
          class="aspect-400/559 w-full animate-pulse rounded-lg bg-muted md:w-[300px] md:shrink-0 lg:w-[400px]"
        ></div>
        <div class="flex grow flex-col gap-3">
          <div class="h-8 w-2/3 animate-pulse rounded bg-muted"></div>
          <div v-for="n in 5" :key="n" class="h-10 animate-pulse rounded bg-muted"></div>
        </div>
      </div>

      <!--
        Permanent, not retryable (#38 §5). The Worker serves this body with a real 404
        status (commit 10) so a crawler reads it as gone rather than as a soft 200.
      -->
      <div
        v-else-if="status === 'notFound'"
        class="flex min-h-[50vh] flex-col items-center justify-center text-center"
      >
        <p class="text-xl font-medium">{{ $t("Card not found") }}</p>
        <p class="mt-1 text-sm text-muted-foreground">
          {{ $t("errors.card.notFound.detail") }}
        </p>
        <Button variant="outline" size="sm" class="mt-4" as-child>
          <NuxtLink :to="localePath('/')">{{ $t("Card List") }}</NuxtLink>
        </Button>
      </div>

      <!-- Retryable, and never red — D4 reserves `--destructive` for destructive actions. -->
      <div
        v-else-if="status === 'error'"
        class="flex min-h-[50vh] flex-col items-center justify-center text-center"
      >
        <p class="text-xl font-medium">{{ $t("errors.cards.offline.title") }}</p>
        <p class="mt-1 text-sm text-muted-foreground">
          {{ $t("errors.cards.offline.detail") }}
        </p>
        <Button variant="outline" size="sm" class="mt-4" @click="load">
          {{ $t("errors.retry") }}
        </Button>
      </div>

      <!--
        The same component the dialog renders (D15). `variant="page"` is what will expand
        the variants accordion here, where an extra interaction hides content from a
        crawler on the 86% of cards that have a sibling.
      -->
      <CardDetail v-else-if="card" :item="card" variant="page" />
    </div>
  </main>

  <AppFooter>
    <AppFooterCurrentDeck />
    <div class="ml-auto flex items-center gap-2">
      <AppFooterOptionsButton />
      <AppFooterDeckButton />
    </div>
  </AppFooter>
  </template>
</template>
