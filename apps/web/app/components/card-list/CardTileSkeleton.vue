<script setup lang="ts">
/**
 * A card tile's silhouette, shown while the first page is in flight (#38, D17).
 *
 * **At the real aspect ratio and the real text height**, so the grid does not reflow when
 * the cards arrive — the skeleton's whole job is to make the arrival invisible. It mirrors
 * `CardItem`'s layout for that reason: art at `400/559`, then a name line and a card-number
 * line when density is comfortable.
 *
 * `--muted` and nothing else. D4 leaves the palette no accent hue, and a skeleton is the
 * one element that must not compete with the art it stands in for.
 *
 * The shimmer is a looping animation, which makes it exactly what
 * `prefers-reduced-motion` exists to stop — handled globally in `tailwind.css`, so there
 * is no media query here.
 */
const { density } = useCardDensity();
const showsText = computed(() => density.value === "comfortable");
const { enabled: showOriginal } = useShowOriginal();
</script>

<template>
  <!--
    `aria-hidden`: a screen reader is told the list is loading once, by the live region in
    `CardListViewAPI`. Twenty announcements of "loading placeholder" is noise, not
    information.
  -->
  <div class="flex flex-col" aria-hidden="true">
    <div class="aspect-400/559 w-full animate-pulse rounded-lg bg-muted"></div>

    <div v-if="showsText" class="px-0.5 pt-1.5">
      <div class="h-[18px] w-3/4 animate-pulse rounded bg-muted"></div>
      <div
        v-if="showOriginal"
        class="mt-0.5 h-[18px] w-2/3 animate-pulse rounded bg-muted"
      ></div>
      <div class="mt-0.5 h-4 w-1/2 animate-pulse rounded bg-muted"></div>
    </div>
  </div>
</template>
