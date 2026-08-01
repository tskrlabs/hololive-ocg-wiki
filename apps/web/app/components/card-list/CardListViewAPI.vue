<script setup lang="ts">
import { vResizeObserver } from "@vueuse/components";
import { useDebounceFn } from "@vueuse/core";
import { RotateCcw, TriangleAlert } from "lucide-vue-next";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";

// A pure function rather than an auto-import: it is the arrow-key arithmetic, and
// `tests/roving-focus.test.ts` exercises it over every geometry without a DOM.
import { targetIndex } from "~/composables/useGridRovingFocus";

const { locale, t } = useI18n();
const filter = useFilter();
const cardQuery = useCardQuery();

/**
 * Keyboard focus survives `RecycleScroller` reusing DOM nodes (#48 §6).
 *
 * Verified in Chromium before the fix: focus a tile, scroll 6000px, and focus is gone to
 * `<body>` — so the next Tab restarts from the top of the document. The scroller has no
 * concept of the focused node; it only knows which items are in view.
 */
useScrollerFocus();

/**
 * Where the grid was before a card was opened (#59).
 *
 * The list unmounts when a card URL is pushed (D15), so this survives outside it. See the
 * composable for why the offset is restored rather than the component kept alive.
 */
const scrollMemory = useGridScrollMemory();

/**
 * The grid is one tab stop, and the arrows move within it (#60, #48 §6).
 *
 * Measured before this: the grid was ~40 tab stops, so tabbing past it to the footer was
 * not realistically possible. The list owns the movement because moving focus needs the
 * live column count *and* the scroller — a target tile may not be mounted at all, so it
 * has to be scrolled into existence before it can be focused.
 *
 * The composable is called up here with the other state because `scrollToTop` reads it;
 * the handlers that need `displayedCards` and `gridColCount` are defined further down,
 * after those exist.
 */
const roving = useGridRovingFocus();

// Ref to the virtual scroller
const virtualScroller = ref();

// Scroll position tracking
const scrollPosition = ref(0);
const shouldPreserveScroll = ref(false);

// Pagination state
const pageSize = ref(200); // Increased for virtual scrolling
const currentPage = ref(1);
const hasMore = computed(() => {
  return cardQuery.cards.value.length < cardQuery.total.value;
});

/**
 * Virtual scroller geometry.
 *
 * The rule lives in `gridColumns.ts` — columns follow from a target tile width rather
 * than from a breakpoint ladder, which is what stops the cards shrinking as the window
 * grows (#43). `RecycleScroller` cannot measure its own children, so both axes are
 * computed here and passed as props.
 *
 * ⚠️ **The geometry now depends on two pieces of *state*, not only on width** (#37 §5).
 * Compact mode drops the text block and gains a column on a phone; show-original adds a
 * line to every tile. Both change `itemSize`, which is how the scroller positions rows —
 * so a stale value does not degrade gracefully, it overlaps the whole grid.
 */
const { density } = useCardDensity();
const { enabled: showOriginal } = useShowOriginal();

const geometryOptions = computed(() => ({
  showsText: showsText(density.value),
  showsOriginal: showOriginal.value,
  compactMobileBonus: true,
}));

/** The last width the observer reported, kept so state changes can re-measure. */
const observedWidth = shallowRef(1280);

const gridColCount = shallowRef(gridGeometry(1280, { compactMobileBonus: true }).columns);
const itemSize = shallowRef(gridGeometry(1280, { compactMobileBonus: true }).itemSize);
const itemSecondarySize = shallowRef(
  gridGeometry(1280, { compactMobileBonus: true }).itemSecondarySize,
);

function measure(width: number) {
  const geometry = gridGeometry(width, geometryOptions.value);

  gridColCount.value = geometry.columns;
  itemSecondarySize.value = geometry.itemSecondarySize;
  itemSize.value = geometry.itemSize;
}

function onResizeObserver(entries: ResizeObserverEntry[]) {
  const [entry] = entries;
  if (!entry) return;

  const { width } = entry.contentRect;
  if (!width || width <= 0) return;

  observedWidth.value = width;
  measure(width);
}

/**
 * Re-measure when the mode changes, not only when the width does.
 *
 * Without this the observer is the only path to `itemSize`, and flipping a toggle resizes
 * nothing — so the grid would keep the previous mode's row height until the next window
 * resize. `tests/grid.test.ts` pins the heights themselves; this is the wiring that
 * delivers them, which is the half a pure test cannot see (F-019).
 */
watch(geometryOptions, () => measure(observedWidth.value));

// Debounced filter application - simplified
const applyFilters = useDebounceFn(async () => {
  // Reset pagination first
  currentPage.value = 1;

  // Make the API call directly - the cardStore will handle loading states
  await cardQuery.getFilteredCards(
    filter.filter.value,
    locale.value,
    1,
    pageSize.value
  );
}, 300); // Slightly increased debounce for API calls// Load more cards for infinite scroll with virtual scroller
const loadMore = async () => {
  if (cardQuery.isLoading.value || !hasMore.value) return;

  // Save current scroll position before loading
  if (virtualScroller.value && virtualScroller.value.$el) {
    scrollPosition.value = virtualScroller.value.$el.scrollTop;
    shouldPreserveScroll.value = true;
  }

  currentPage.value++;
  await cardQuery.loadMore(
    filter.filter.value,
    locale.value,
    currentPage.value,
    pageSize.value
  );
};

// Virtual scroller infinite loading with improved scroll handling
const handleScrollEnd = useDebounceFn(() => {
  // Load more when reaching the end of virtual scroller
  if (hasMore.value && !cardQuery.isLoading.value) {
    loadMore();
  }
}, 100); // Debounce to prevent multiple rapid calls

/**
 * Return to the top of the list.
 *
 * A new filter replaces the items but not the scroll offset, so without this the first
 * page of a fresh result set renders under a viewport still scrolled to where the last
 * one was — the user applies a filter and appears to land in the middle of it. Invisible
 * until infinite scroll started working, because there was never a second page to be
 * scrolled into.
 *
 * `shouldPreserveScroll` is cleared alongside: it belongs to the append path, and a
 * pending restore would otherwise scroll us straight back down.
 */
const scrollToTop = () => {
  shouldPreserveScroll.value = false;
  scrollPosition.value = 0;
  // The roving tabindex goes back to the first card with the scroll (#60). Left where it
  // was, it could point past the end of a smaller result set — and then *no* tile would
  // be tabbable, silently dropping the grid out of the tab order.
  roving.activeIndex.value = 0;
  // A remembered offset belongs to the *previous* result set (#59). The count guard in
  // `restore` would usually catch that, but two different filters can match the same
  // number of cards — so the offset is dropped where the intent is known rather than
  // left for a heuristic.
  scrollMemory.forget();
  virtualScroller.value?.scrollToItem?.(0);
};

/**
 * A fresh result set starts at the top; an appended page does not (#38 §4).
 *
 * This replaces a watcher-on-`isLoading` that created a second watcher per filter change,
 * tore it down inside a `nextTick`, and carried a 5-second safety timeout in case it
 * never fired. All of that machinery existed to drive the full-screen overlay, which is
 * gone (D17) — but `scrollToTop` was *inside* it and fixes a real bug, so it moves here.
 *
 * The transition is what matters, not the flag: entering `ready` from `loading` or
 * `refiltering` means new results are in the DOM. An append never passes through either,
 * so scroll position survives it by construction rather than by a flag someone must
 * remember to clear.
 */
watch(
  () => cardQuery.state.value.status,
  (status, previous) => {
    if (status !== "ready" || (previous !== "loading" && previous !== "refiltering")) return;

    // ⚠️ Returning from a card is a `loading → ready` pass that must **not** reset the
    // scroll (#59).
    //
    // Opening a card unmounts this component (D15), so coming back re-runs `onMounted`'s
    // `applyFilters()` — and even though that resolves from `useState` with no request, it
    // still moves the query through `loading` to `ready`. This watcher then read that as
    // "new results are in the DOM" and scrolled to the top, undoing the restore that had
    // already happened. Traced in Chromium: the offset was written correctly and then
    // overwritten a tick later.
    //
    // A pending memory is the signal that this transition is a *return*, not a new result
    // set. `onMounted` consumes it, so this only sees one while the restore is in flight.
    if (scrollMemory.isPending()) return;

    scrollToTop();
  },
);

// Apply filters when filter changes - simplified
watch(
  () => filter.filter.value,
  () => {
    // Reset pagination when filters change
    currentPage.value = 1;
    applyFilters();
  },
  {
    deep: true,
    immediate: false, // Prevent immediate execution on mount
  }
);

// Also update when locale changes
watch(
  () => locale.value,
  () => {
    // Reset pagination when locale changes
    currentPage.value = 1;
    cardQuery.clearCache();
    applyFilters();
  }
);

/**
 * On mount: apply the filters, and put the scroll back if we are returning from a card.
 *
 * Both happen here because both are "the list just appeared". `applyFilters` is debounced
 * and resolves from `useState` when nothing changed, so returning from a card costs no
 * request — measured: closing a card dialog makes **zero** API calls.
 *
 * The restore waits for the scroller to actually exist and have its rows. `nextTick`
 * alone is not enough: `shouldRenderScroller` gates on a measured width, which arrives
 * from a `ResizeObserver` a frame later, so at `nextTick` the element is often still the
 * fallback grid.
 */
onMounted(() => {
  applyFilters();

  // The component instance, not its element: the restore goes through the scroller's own
  // `scrollToPosition`, because assigning `scrollTop` on a scroller that has not laid out
  // its virtual height yet is silently clamped to 0.
  // The element, not the component: `scrollToPosition` reports success without moving
  // anything on a scroller that has not laid out yet, so the restore assigns `scrollTop`
  // and reads it back to see whether it took.
  const restoreScroll = () =>
    scrollMemory.restore(
      virtualScroller.value?.$el as HTMLElement | undefined,
      displayedCards.value.length,
    );

  /**
   * Keep trying until the offset sticks, then stop (#59).
   *
   * A single deferred attempt is not enough and neither is a frame or two. The scroller
   * only exists once `shouldRenderScroller` is true, which waits on a width from a
   * `ResizeObserver`; and even then it renders one viewport of rows before it knows its
   * full height, so an assignment made too early is clamped to 0 and lost. Measured in
   * Chromium, the whole sequence settles within ~200ms of the list remounting.
   *
   * **Giving up must `forget()`**: a memory left behind keeps `isPending()` true, which
   * would suppress the scroll-to-top on every later filter change.
   */
  let attempts = 0;
  const tryRestore = () => {
    if (!scrollMemory.isPending()) return;
    if (restoreScroll()) return;
    if (++attempts > 20) {
      scrollMemory.forget();
      return;
    }
    requestAnimationFrame(tryRestore);
  };
  nextTick(tryRestore);
});

/**
 * What to render (D17, #38).
 *
 * One question, asked once, instead of `isLoading && !cards.length` assembled at four
 * call sites in an order each had to get right.
 */
const state = cardQuery.state;

// Use the filtered cards from the store
const displayedCards = computed(() => cardQuery.cards.value);

const onGridMove = (key: string, from: number) => {
  const next = targetIndex(key, from, gridColCount.value, displayedCards.value.length);
  if (next === null || next === from) return;
  roving.focusIndex(next, virtualScroller.value);
};

/**
 * Never let the tabbable index point past the end of the list.
 *
 * `scrollToTop` covers the filter path, but the result set can also shrink without one —
 * a retry landing on fewer cards, or a locale switch. If the index outran the list, no
 * tile would carry `tabindex="0"` and the grid would drop out of the tab order entirely,
 * which is a worse bug than the one this feature fixes.
 */
watch(() => displayedCards.value.length, roving.clampTo);


/** Ask again. The failed page was never cached, so this is a real retry. */
const retry = () => {
  applyFilters();
};

/** Clear the filters for real, rather than telling the user to (#38 §2). */
const resetFilters = () => {
  filter.clear(undefined, true);
};

/**
 * Roughly one screen of skeletons — enough to fill the viewport, not the whole list.
 *
 * Keyed off the live column count so the placeholder grid matches the real one at every
 * width; a fixed count would be a short row on a wide display and a long scroll on a
 * phone.
 */
const skeletonCount = computed(() => gridColCount.value * 4);

/**
 * What a screen reader is told about the list, once per state change.
 *
 * The skeletons are `aria-hidden` precisely so this can be the single announcement —
 * twenty "loading placeholder"s is noise, and the outcome is the information. D4 leaves
 * the states no colour to signal with, which makes the spoken channel load-bearing rather
 * than a courtesy.
 */
const liveMessage = computed(() => {
  const current = state.value;
  switch (current.status) {
    case "loading":
      return t("Loading cards");
    case "refiltering":
      return t("Applying filters");
    case "ready":
      return t("{total} cards", { total: current.total });
    case "empty":
      return t("No cards found");
    case "error":
      return t(`errors.cards.${current.kind}.title`);
    default:
      return "";
  }
});

// Computed property to check if virtual scroller should be rendered
const shouldRenderScroller = computed(() => {
  return (
    displayedCards.value.length > 0 &&
    itemSize.value > 0 &&
    itemSecondarySize.value > 0 &&
    gridColCount.value > 0
  );
});

// Watch for changes in displayed cards to preserve scroll position
watch(
  () => displayedCards.value.length,
  async (newLength, oldLength) => {
    // Only preserve scroll when cards are added (not when filtering)
    if (newLength > oldLength && shouldPreserveScroll.value) {
      await nextTick();
      if (virtualScroller.value && virtualScroller.value.$el) {
        virtualScroller.value.$el.scrollTop = scrollPosition.value;
        shouldPreserveScroll.value = false;
      }
    }
  }
);
</script>

<template>
  <!--
    A flex column filling the region the shell gives it (#44). The scroller needs a real
    height to inherit; before the shell change there was none to inherit, which is how it
    came to be `height: 100dvh` — a whole viewport, sitting between a sticky header and a
    sticky footer, with ~138px of the list hidden underneath them.
  -->
  <div class="flex h-full flex-col">
    <!--
      A 2px indeterminate bar, and **nothing else** while refiltering (D17, #38 §2).

      What was here was `fixed inset-0 bg-background/80 backdrop-blur-sm` — a full-screen
      blur thrown over the exact results being refined, at the one moment the user most
      wants to see them. With the rail (#36) it would also have covered the filters doing
      the refining.

      `--foreground` at low opacity, not a hue: D4 leaves the palette none, and progress
      is not one of the things `--destructive` is for.
    -->
    <div v-if="state.status === 'refiltering'" class="h-0.5 shrink-0 overflow-hidden">
      <div class="h-full w-1/3 animate-[loading-bar_1.2s_ease-in-out_infinite] bg-foreground/40"></div>
    </div>

    <!--
      One live region for the whole list, so a screen reader hears the outcome once.

      The skeletons are `aria-hidden` precisely because this exists: twenty announcements
      of "loading placeholder" is noise, and the state change is the information.
    -->
    <p class="sr-only" role="status" aria-live="polite">{{ liveMessage }}</p>

    <!--
      First load: skeletons at the real geometry (#38 §2).

      A spinner said "something is happening"; skeletons say *what* is coming and reserve
      the space for it, so the arrival does not reflow the page.
    -->
    <div
      v-if="state.status === 'loading'"
      class="grid min-h-0 grow content-start gap-3 overflow-hidden p-2"
      :style="{ gridTemplateColumns: `repeat(${gridColCount}, minmax(0, 1fr))` }"
    >
      <CardTileSkeleton v-for="n in skeletonCount" :key="n" />
    </div>

    <!-- Virtual Scroller for cards grid -->
    <div
      v-else-if="displayedCards.length > 0"
      class="flex min-h-0 grow flex-col"
    >
      <!--
        Refiltering **dims** the previous results rather than covering them (D17).

        `opacity-60` plus `pointer-events-none`: they stay readable, so a user can see
        what is being narrowed and can tell the new set from the old one when it lands,
        but cannot click a card that is about to be replaced.
      -->
      <div
        class="min-h-0 grow transition-opacity"
        :class="state.status === 'refiltering' ? 'pointer-events-none opacity-60' : ''"
      >
        <!--
          The scroller's key carries **every input to the geometry**, not just the column
          count. `RecycleScroller` caches each item's position from the `itemSize` it was
          constructed with, so a changed row height has to remount it — otherwise rows
          keep the old spacing and overlap. Density and the show-original toggle both
          change that height (#37 §5), and both were missing from this key.
        -->
        <RecycleScroller
          v-if="shouldRenderScroller"
          ref="virtualScroller"
          :key="`scroller-${gridColCount}-${locale}-${density}-${showOriginal}`"
          class="scroller p-2"
          :items="displayedCards"
          :item-size="itemSize"
          :item-secondary-size="itemSecondarySize"
          :grid-items="gridColCount"
          :buffer="600"
          key-field="id"
          :emit-update="true"
          @scroll-end="handleScrollEnd"
          v-resize-observer="onResizeObserver"
        >
          <!--
            No `aspect-400/559` on the tile any more: the tile is art *plus* text now, and
            forcing the card's ratio onto the whole thing would crop the name it exists to
            show. The ratio lives on the art element inside `CardItem`, where it belongs.
          -->
          <!--
            `index` comes from the scroller's own slot, so it is the item's position in
            the result set rather than in the mounted window — which is what the roving
            tabindex has to key on (#60).
          -->
          <template #default="{ item, index }">
            <div class="p-1">
              <CardItem :item="item" :index="index" @move="onGridMove" />
            </div>
          </template>
        </RecycleScroller>

        <!--
          Fallback grid, rendered until the resize observer reports a width.

          This carried its own copy of the breakpoint ladder
          (`xl:grid-cols-8 2xl:grid-cols-10`), so it had the same bug: a *smaller* card at
          1536px than at 1440px. Fixing only the scroller would have left it live here.

          `auto-fill` keys on the minimum track rather than on a target, so it is not
          identical to `columnsForWidth` — it fills to whatever fits above `MIN_TILE`
          instead of aiming at `TARGET_TILE`. What it does share is the property the bug
          was about: columns are derived from width, so the tile can never fall below
          150px and adding a column can never shrink the grid's floor. #43.
        -->
        <div
          v-else
          class="grid h-full grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2 overflow-y-auto p-2"
        >
          <div v-for="item in displayedCards" :key="item.id">
            <CardItem :item="item" />
          </div>
        </div>
      </div>

      <!--
        Loading the next page appends skeletons **below** the results (#38 §2), leaving
        everything already on screen untouched. This is the one loading treatment that
        must not dim anything: the user is reading the rows above it.
      -->
      <div
        v-if="cardQuery.isAppending.value"
        class="grid shrink-0 gap-3 px-2 pb-2"
        :style="{ gridTemplateColumns: `repeat(${gridColCount}, minmax(0, 1fr))` }"
      >
        <CardTileSkeleton v-for="n in gridColCount" :key="`more-${n}`" />
      </div>
    </div>

    <!--
      The fetch failed (#45).

      This has to come *before* the empty state, because both are reached with an empty
      card list and only one of them is about the user's filters. Telling someone whose
      API is unreachable to "try adjusting your filters" sends them to a control that
      cannot possibly help, and reads as "this wiki has no cards".

      No colour and no red icon: `--destructive` is reserved for destructive *actions*,
      not for reporting that a fetch failed (D4, #38 §6). Weight and an icon carry it.
    -->
    <div
      v-else-if="state.status === 'error'"
      class="flex grow justify-center items-center min-h-[200px]"
    >
      <div class="text-center">
        <TriangleAlert class="mx-auto mb-2 size-6" aria-hidden="true" />
        <p class="text-lg font-medium">
          {{ $t(`errors.cards.${state.kind}.title`) }}
        </p>
        <p class="text-sm text-muted-foreground mt-1">
          {{ $t(`errors.cards.${state.kind}.detail`) }}
        </p>
        <Button variant="outline" size="sm" class="mt-4" @click="retry">
          {{ $t("errors.retry") }}
        </Button>
      </div>
    </div>

    <!--
      A genuine zero-result — the only state where the filters really are the answer, and
      the only one that should say so.

      The button *clears* them rather than advising the user to (#38 §2). "Try adjusting
      your filters" beside no control is advice; a Reset button is the adjustment.
    -->
    <div
      v-else-if="state.status === 'empty'"
      class="flex grow justify-center items-center min-h-[200px]"
    >
      <div class="text-center">
        <p class="text-lg font-medium">{{ $t("No cards found") }}</p>
        <p class="text-sm text-muted-foreground mt-1">
          {{ $t("Try adjusting your filters") }}
        </p>
        <Button variant="outline" size="sm" class="mt-4" @click="resetFilters">
          <RotateCcw aria-hidden="true" /> {{ $t("Reset") }}
        </Button>
      </div>
    </div>

    <!--
      Results summary — back in normal flow (#44), and below `lg` only (#36 §4).

      It was `fixed`, and its comment recorded why: *"In flow it sits below a scroller
      that is `height: 100dvh`, so it is never on screen — which is how it came to be
      commented out, and why 'Showing 200 of 2448' went unseen while infinite scroll was
      broken."* That was this bug, diagnosed and worked around rather than fixed. With
      the scroller sized to the space it actually has, below the scroller *is* on screen,
      so the workaround and its `bottom-13 md:bottom-16` guess both go.

      Above `lg` the rail carries the count instead: it is query feedback, and the rail is
      where the query lives. Two live counts on one screen would be one too many, and the
      rail's is the one beside the controls that change it.
    -->
    <div
      v-if="displayedCards.length > 0"
      class="shrink-0 border-t px-2 py-1 text-right text-xs text-muted-foreground lg:hidden"
    >
      {{
        $t("Showing {count} of {total} cards", {
          count: displayedCards.length,
          total: cardQuery.total.value,
        })
      }}
    </div>
  </div>
</template>

<style lang="css" scoped>
/*
 * The scroller fills its parent rather than the viewport (#44).
 *
 * It used to be `height: 100dvh` between a sticky header and a sticky footer, each 69px,
 * so ~138px of the list was permanently hidden underneath the chrome — 17% of the list
 * at an 800px viewport. The commented-out `50vh`/`60vh`/`70vh` ladder below it was an
 * earlier attempt at the same problem by guessing; both are gone now that the shell is a
 * flex column and there is a real height to inherit.
 */
.scroller {
  height: 100%;
}

/*
 * The refiltering bar's sweep (#38 §2).
 *
 * Indeterminate on purpose: the request's duration is unknown, and a bar that pretends to
 * know is worse than one that admits it. It replaces a full-screen backdrop blur, so the
 * results it reports on stay visible throughout.
 *
 * Overridden by the global `prefers-reduced-motion` rule in `tailwind.css`, which is why
 * there is no media query here.
 */
@keyframes loading-bar {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(400%);
  }
}
</style>
