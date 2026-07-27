<script setup lang="ts">
import { toast } from "vue-sonner";

const { t } = useI18n();

const route = useRoute();
const getRouteBaseName = useRouteBaseName();

const decks = useDecks();

const isEditing = computed(() => decks.isEditing.value);
const currentDeck = computed(() => decks.currentDeck.value);

const toggleEditing = () => {
  if (decks.currentDeck.value === null) {
    toast.warning(t("Please select a deck to continue."));
    return;
  }

  decks.toggleEditing();
};
</script>

<template>
  <div
    v-if="getRouteBaseName(route) === 'index'"
    class="flex items-center gap-2 md:gap-4"
  >
    <button @click="toggleEditing">
      <Badge
        variant="outline"
        class="text-xs md:text-sm"
        :class="
          isEditing
            ? 'bg-emerald-500/15 border-emerald-500'
            : 'bg-gray-500/15 border-gray-500'
        "
      >
        <span class="relative flex size-1.5 mr-1">
          <span
            class="absolute inline-flex h-full w-full rounded-full opacity-75"
            :class="isEditing ? 'animate-ping bg-emerald-400' : 'bg-gray-400'"
          ></span>
          <span
            class="relative inline-flex size-1.5 rounded-full"
            :class="isEditing ? 'bg-emerald-500' : 'bg-gray-500'"
          ></span>
        </span>
        {{ $t("Edit") }}
      </Badge>
    </button>

    <span class="text-sm md:text-lg">
      {{ currentDeck?.name || $t("Select one deck to edit") }}
    </span>
  </div>
</template>
