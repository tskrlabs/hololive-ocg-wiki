<script setup lang="ts">
/**
 * The status page's table view (the default).
 *
 * No `skipped` column: v2's `status.json` carries no `skipped[]` list — validation
 * failures are reported by `holo-data build`, not the seeder (see `~/types/status`).
 */
import { Eye } from "lucide-vue-next";
import type { StatusEntry, StatusKind } from "~/types/status";

const props = defineProps<{
  items: StatusEntry[];
  status: StatusKind;
}>();

const { t } = useI18n();

const badgeClass: Record<StatusKind, string> = {
  new: "bg-green-500 text-white",
  changed: "bg-blue-500 text-white",
  qaUpdated: "bg-amber-500 text-white",
  removed: "bg-red-500 text-white",
};

const { open, card, loading, openCard } = useCardDetail();

function canOpen(item: StatusEntry) {
  return (
    !!item.image_key && props.status !== "removed"
  );
}
</script>

<template>
  <div class="rounded-md border overflow-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b bg-muted/50">
          <th class="px-4 py-2 text-left font-medium text-muted-foreground w-8">
            #
          </th>
          <th class="px-4 py-2 text-left font-medium text-muted-foreground">
            {{ $t("fields.name") }}
          </th>
          <th
            class="px-4 py-2 text-left font-medium text-muted-foreground hidden sm:table-cell"
          >
            ID
          </th>
          <th class="px-4 py-2 text-left font-medium text-muted-foreground">
            {{ $t("status.sort.label") }}
          </th>
          <th class="px-2 py-2 w-8" />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(item, idx) in items"
          :key="item.id"
          class="border-b last:border-0 hover:bg-muted/30 transition-colors"
        >
          <td class="px-4 py-2 text-muted-foreground tabular-nums">
            {{ idx + 1 }}
          </td>
          <td class="px-4 py-2">
            <div class="flex flex-col gap-0.5">
              <span class="font-mono text-xs text-muted-foreground">{{
                item.card_number || `#${item.id}`
              }}</span>
              <span v-if="item.name" class="truncate max-w-[200px]">{{
                item.name
              }}</span>
            </div>
          </td>
          <td
            class="px-4 py-2 text-muted-foreground font-mono text-xs hidden sm:table-cell"
          >
            {{ item.id }}
          </td>
          <td class="px-4 py-2">
            <span
              class="text-[10px] font-bold px-1.5 py-0.5 rounded leading-none"
              :class="badgeClass[status]"
            >
              {{ $t(`status.badges.${status}`) }}
            </span>
          </td>
          <td class="px-2 py-2">
            <button
              v-if="canOpen(item)"
              class="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              :title="$t('status.viewDetail')"
              @click="openCard(item.id)"
            >
              <Eye class="w-4 h-4" />
            </button>
          </td>
        </tr>
      </tbody>
    </table>
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
