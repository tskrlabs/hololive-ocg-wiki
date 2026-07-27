<script setup lang="ts">
/**
 * The status page's list view.
 *
 * Reads `image_key` (D9) and has no `skipped` branch — v2's `status.json` carries no
 * `skipped[]` list; validation failures are reported by `holo-data build`, not the
 * seeder (see `~/types/status`).
 */
import { Eye } from "lucide-vue-next";
import type { StatusEntry, StatusKind } from "~/types/status";

defineProps<{
  items: StatusEntry[];
  status: StatusKind;
}>();

const badgeClass: Record<StatusKind, string> = {
  new: "bg-green-500 text-white",
  changed: "bg-blue-500 text-white",
  qaUpdated: "bg-amber-500 text-white",
  removed: "bg-red-500 text-white",
};

const cardImage = useCardImage();
const { open, card, loading, openCard } = useCardDetail();

// A removed card is gone from the database, so there is nothing to open.
function canOpen(item: StatusEntry, status: StatusKind) {
  return !!item.image_key && status !== "removed";
}
</script>

<template>
  <div class="flex flex-col gap-1">
    <div
      v-for="item in items"
      :key="item.id"
      class="flex items-center gap-3 rounded-md border px-3 py-2 hover:bg-muted/50 transition-colors"
    >
      <!-- Thumbnail -->
      <div class="flex-shrink-0 w-10 h-14 rounded overflow-hidden bg-muted">
        <SimpleImage
          v-if="canOpen(item, status)"
          :src="cardImage(item.image_key)"
          :img-attributes="{ class: 'w-full h-full object-cover' }"
        />
        <div
          v-else
          class="w-full h-full flex items-center justify-center text-[8px] text-muted-foreground font-mono p-0.5 text-center break-all leading-tight"
        >
          {{ item.card_number?.slice(-3) || item.id }}
        </div>
      </div>

      <!-- Info -->
      <div class="flex flex-col gap-0.5 min-w-0 grow">
        <span class="text-sm font-mono text-muted-foreground">{{
          item.card_number || `#${item.id}`
        }}</span>
        <span v-if="item.name" class="text-sm truncate">{{ item.name }}</span>
      </div>

      <!-- Badge -->
      <span
        class="flex-shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded leading-none"
        :class="badgeClass[status]"
      >
        {{ $t(`status.badges.${status}`) }}
      </span>

      <!-- View detail button -->
      <button
        v-if="canOpen(item, status)"
        class="flex-shrink-0 p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        :title="$t('status.viewDetail')"
        @click="openCard(item.id)"
      >
        <Eye class="w-4 h-4" />
      </button>
    </div>
  </div>

  <!-- Shared card detail dialog -->
  <Dialog v-model:open="open">
    <DialogContent
      hide-top-right-close
      class="grid-rows-[auto_minmax(0,1fr)_auto] p-0 max-h-[90dvh] sm:max-w-lg md:max-w-2xl lg:max-w-4xl"
    >
      <DialogHeader class="h-0 overflow-hidden">
        <DialogTitle>{{ card?.name || "" }}</DialogTitle>
        <DialogDescription>{{ card?.name || "" }}</DialogDescription>
      </DialogHeader>
      <div v-if="loading" class="flex items-center justify-center h-64">
        <span class="text-muted-foreground text-sm">{{ $t("Loading") }}</span>
      </div>
      <CardItemDialogContent v-else-if="card" :item="card" />
    </DialogContent>
  </Dialog>
</template>
