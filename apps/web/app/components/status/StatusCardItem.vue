<script setup lang="ts">
/**
 * One card in the status grid.
 *
 * Takes `imageKey` rather than v1's `imagePath` (D9) — `status.json` stores the key and
 * the URL is composed here, like everywhere else.
 *
 * The `skipped` status is gone: v2's `status.json` has no `skipped[]` list, because
 * validation failures are reported by `holo-data build`'s collect-and-report rather than
 * carried into the seeder's diff (see `~/types/status`).
 */
import type { StatusKind } from "~/types/status";

const props = defineProps<{
  id: string;
  cardNumber: string | null;
  imageKey: string | null;
  name: string | null;
  status: StatusKind;
}>();

const badgeClass: Record<StatusKind, string> = {
  new: "bg-green-500 text-white",
  changed: "bg-blue-500 text-white",
  qaUpdated: "bg-amber-500 text-white",
  removed: "bg-red-500 text-white",
};

const cardImage = useCardImage();

// A removed card is no longer in the database, so there is nothing to open.
const canOpen = computed(() => !!props.imageKey && props.status !== "removed");

const { open, card, loading, openCard } = useCardDetail();

function onClick() {
  if (canOpen.value) openCard(props.id);
}
</script>

<template>
  <div
    class="relative flex aspect-400/559 cursor-pointer group"
    @click="onClick"
  >
    <!-- Card image -->
    <SimpleImage
      v-if="canOpen"
      class="rounded-lg overflow-hidden w-full"
      :src="cardImage(imageKey)"
      :img-attributes="{ class: 'w-full' }"
    />

    <!-- Placeholder for a removed card -->
    <div
      v-else
      class="w-full rounded-lg bg-muted flex flex-col items-center justify-center text-center p-2 gap-1"
    >
      <span
        class="text-[10px] text-muted-foreground font-mono leading-tight break-all"
      >
        {{ cardNumber || id }}
      </span>
    </div>

    <!-- Status badge -->
    <span
      class="absolute top-1 right-1 text-[9px] font-bold px-1 py-0.5 rounded leading-none"
      :class="badgeClass[status]"
    >
      {{ $t(`status.badges.${status}`) }}
    </span>
  </div>

  <!-- Card detail dialog -->
  <Dialog v-if="canOpen" v-model:open="open">
    <DialogContent
      hide-top-right-close
      class="grid-rows-[auto_minmax(0,1fr)_auto] p-0 max-h-[90dvh] sm:max-w-lg md:max-w-2xl lg:max-w-4xl"
    >
      <DialogHeader class="h-0 overflow-hidden">
        <DialogTitle>{{ card?.name || cardNumber || "" }}</DialogTitle>
        <DialogDescription>{{
          card?.name || cardNumber || ""
        }}</DialogDescription>
      </DialogHeader>
      <div v-if="loading" class="flex items-center justify-center h-64">
        <span class="text-muted-foreground text-sm">{{ $t("Loading") }}</span>
      </div>
      <CardItemDialogContent v-else-if="card" :item="card" />
    </DialogContent>
  </Dialog>
</template>
