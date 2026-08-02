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

    <SheetContent side="top" hide-top-right-close>
      <DialogHeader class="h-0 overflow-hidden">
        <DialogTitle>{{ $t("Filter") }}</DialogTitle>
        <DialogDescription>{{ $t("Filter") }}</DialogDescription>
      </DialogHeader>

      <!--
        The sheet caps itself at 85% of the viewport and scrolls inside that (#44).

        It was `max-h-[calc(100dvh-96px-16px-16px)]`, where 96px was a hardcoded estimate
        of chrome that is a real 69px — and the estimate had no referent in any case: the
        sheet is `fixed top-0`, so it does not sit between the header and the footer and
        never needed to subtract them. A fraction states the intent ("leave some page
        visible behind it") without encoding anyone's height.
      -->
      <div class="flex grow">
        <ScrollArea>
          <div class="w-full max-h-[85dvh] p-4">
            <FilterPanel />
          </div>
        </ScrollArea>
      </div>

      <SheetFooter class="pt-0 md:pt-4">
        <div class="flex w-full flex-col gap-2">
          <!--
            Apply closes the sheet; in the rail the same component closes nothing, which
            is the one behavioural difference between the two containers.
          -->
          <FilterActions @applied="isOpen = false" />

          <!--
            `Close` stays *here* and only here (D10). It is meaningless in a panel that
            never closes, which is why `FilterActions` does not carry it.
          -->
          <Button variant="outline" @click="handleCancel">
            <PanelTopClose aria-hidden="true" /> {{ $t("Close") }}
          </Button>
        </div>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
