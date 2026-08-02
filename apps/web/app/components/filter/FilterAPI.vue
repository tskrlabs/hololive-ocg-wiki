<script lang="ts" setup>
import { Funnel, PanelTopClose } from "lucide-vue-next";

/**
 * The filter **sheet**, below `lg` (#36 §1).
 *
 * This was one 563-line component that was both the container and all seven filter
 * groups, so a persistent rail could only have been a second copy of the groups. The
 * groups now live in `FilterPanel` and the commit controls in `FilterActions`; what is
 * left here is the container that can be closed, which is the only thing the rail does
 * not share.
 *
 * `lg:hidden` rather than a `v-if` on a width: the rail is `hidden lg:flex` and this is
 * its complement, so exactly one of the two is present at any width with no JS measuring
 * the viewport and no flash while it decides.
 */
const filter = useFilter();

const isFiltered = computed(() => filter.isFiltered());

/** How many groups hold uncommitted edits — the trigger's summary of the rail's dots. */
const pendingCount = computed(() => filter.pending.value.size);

const isOpen = ref(false);

onMounted(() => {
  filter.initializeDraftFilters();
});

/** Cancel: throw the draft away and start again from what is applied. */
const handleCancel = () => {
  filter.initializeDraftFilters();
  isOpen.value = false;
};
</script>

<template>
  <Sheet v-model:open="isOpen" class="lg:hidden">
    <SheetTrigger as-child>
      <Button size="icon" class="relative lg:hidden" :title="$t('Filter')">
        <!--
          The filtered dot is decorative and purely visual, so the *state* it conveys goes
          into the accessible name instead — a screen-reader user otherwise has no way to
          know filters are active (#51).

          It is `--border-strong` rather than the old hardcoded `bg-red-500`: D4 leaves no
          accent hue, and `--destructive` is reserved for destructive *actions* rather
          than for marking state.
        -->
        <div
          v-if="isFiltered || pendingCount > 0"
          class="absolute left-0 top-0 -translate-2/4 size-2.5 rounded-full bg-border-strong"
        ></div>

        <Funnel aria-hidden="true" />
        <span class="sr-only">
          {{ isFiltered ? $t("Filter (active)") : $t("Filter") }}
        </span>
      </Button>
    </SheetTrigger>

    <!--
      **The cap is on the sheet, not on the groups inside it.**

      `side="top"` is `h-auto` — it takes its height from its content and has no cap of its
      own — so `max-h-[85dvh]` on the inner div capped only the *scrolling part* and the
      footer's height was then added on top of it. Measured before the fix: a 656px sheet
      in a 568px viewport, with Close ending at 639px. Off-screen and unclickable on every
      mobile viewport tested (320→414), not only the small ones.

      That made it a trap rather than a blemish: `side="top"` at this height covers the
      whole screen, so no overlay is exposed to tap outside, and the page behind does not
      scroll (#44). Escape still closes it — but Escape is a keyboard, and this component
      is `lg:hidden`. On a phone the only ways out were to apply the filters or reload.

      `max-h-[85dvh]` here bounds the whole sheet, footer included, and `dvh` is
      deliberate: it tracks mobile browser chrome as it collapses, which `vh` does not.
    -->
    <SheetContent side="top" hide-top-right-close class="max-h-[85dvh]">
      <DialogHeader class="h-0 overflow-hidden">
        <DialogTitle>{{ $t("Filter") }}</DialogTitle>
        <DialogDescription>{{ $t("Filter") }}</DialogDescription>
      </DialogHeader>

      <!--
        The groups scroll; the footer below does not (#44, and D10's rule for the rail).

        `min-h-0` is load-bearing here for the same reason it is everywhere else under a
        flex column: a flex child defaults to `min-height: auto` and refuses to shrink
        below its content, so without it seven filter groups push the footer out of the
        sheet — which is the bug this block previously *contained*, having capped itself
        rather than letting the sheet cap it.

        The cap moved to `SheetContent` (above). It was `max-h-[85dvh]` on this inner div,
        which bounded the scrolling part while the footer was added underneath it; before
        that it was `max-h-[calc(100dvh-96px-16px-16px)]`, where 96px was a hardcoded
        estimate of chrome that is a real 69px — and had no referent either way, since a
        `fixed top-0` sheet does not sit between the header and the footer.
      -->
      <div class="flex min-h-0 grow">
        <ScrollArea class="w-full">
          <div class="w-full p-4">
            <FilterPanel />
          </div>
        </ScrollArea>
      </div>

      <SheetFooter class="pt-0 md:pt-4">
        <div class="flex w-full flex-col gap-2">
          <!--
            Apply closes the sheet; in the rail the same component closes nothing, which
            is the one behavioural difference between the two containers.

            The 44px touch sizing is applied *here* rather than inside `FilterActions`,
            because that component is shared with the desktop rail where a pointer is the
            input and 36px is the house height. The container states the ergonomics of its
            own surface — the same split that lets one set of controls live in two places.
          -->
          <FilterActions
            class="[&_button]:h-11"
            @applied="isOpen = false"
          />

          <!--
            `Close` stays *here* and only here (D10). It is meaningless in a panel that
            never closes, which is why `FilterActions` does not carry it.

            `h-11` (44px), matching `DeckPanel`'s close for the same reason: this is a
            touch-only surface (`lg:hidden`), and the default 36px clears WCAG 2.5.8's
            24px minimum but is under a comfortable target. It is also the *only* way out
            of this sheet on a phone — the sheet covers the screen, so there is no overlay
            to tap, and Escape needs a keyboard.
          -->
          <Button variant="outline" class="h-11" @click="handleCancel">
            <PanelTopClose aria-hidden="true" /> {{ $t("Close") }}
          </Button>
        </div>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
