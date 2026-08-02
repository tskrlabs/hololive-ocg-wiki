<script lang="ts" setup>
import { Funnel, RotateCcw } from "lucide-vue-next";

/**
 * Apply and Reset — the draft → apply commit, shared by the rail and the sheet (#32, D16).
 *
 * **`Close` is deliberately absent** (D10). It made sense in a sheet that covered the
 * screen; in a panel that never closes it is a button with nothing to do. The sheet keeps
 * its own close affordance in `FilterAPI`, where the container that can be closed lives.
 *
 * The draft → apply flow itself stays on every breakpoint, and that is a costed decision
 * rather than a habit: instant filtering was measured at **265%** of the 5M/day read tier
 * against Apply's 66% (#32).
 */
const emit = defineEmits<{ applied: [] }>();

const filter = useFilter();
const hasPendingChanges = computed(() => filter.hasPendingChanges.value);
const isApplying = ref(false);

const apply = async () => {
  if (!hasPendingChanges.value) return;

  isApplying.value = true;
  try {
    await filter.applyFilters();
    emit("applied");
  } finally {
    isApplying.value = false;
  }
};

/** Blank the draft. The applied filters stay until Apply is pressed. */
const resetAll = () => filter.clear();
</script>

<template>
  <div class="flex w-full flex-col gap-2">
    <Button
      class="w-full"
      :disabled="isApplying || !hasPendingChanges"
      @click="apply"
    >
      <Funnel aria-hidden="true" />
      <template v-if="hasPendingChanges">{{ $t("Apply Filters") }}</template>
      <template v-else>{{ $t("No Changes") }}</template>
    </Button>

    <Button class="w-full" variant="outline" @click="resetAll">
      <RotateCcw aria-hidden="true" /> {{ $t("Reset") }}
    </Button>
  </div>
</template>
