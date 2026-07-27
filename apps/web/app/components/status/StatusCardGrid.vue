<script setup lang="ts">
// `StatusEntry` used to be declared *in this file* and imported by its three siblings —
// a component exporting the type its peers depend on. It lives in `~/types/status` now,
// beside the artifact it describes.
import type { StatusEntry, StatusKind } from "~/types/status";

defineProps<{
  items: StatusEntry[];
  status: StatusKind;
}>();
</script>

<template>
  <div
    class="grid gap-2"
    style="grid-template-columns: repeat(3, minmax(0, 1fr))"
    :class="[
      'sm:grid-cols-4',
      'md:grid-cols-5',
      'lg:grid-cols-6',
      'xl:grid-cols-8',
      '2xl:grid-cols-10',
    ]"
  >
    <StatusCardItem
      v-for="item in items"
      :key="item.id"
      :id="item.id"
      :card-number="item.card_number ?? null"
      :image-key="item.image_key ?? null"
      :name="item.name ?? null"
      :status="status"
    />
  </div>
</template>
