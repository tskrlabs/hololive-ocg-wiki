<script setup lang="ts">
/** ⚠️ PROTOTYPE — throwaway. Card grid with the #36 target-width column rule. */
import type { Card } from "@/types/card";

const props = defineProps<{
  cards: Card[];
  variant: string;
  showNames: boolean;
  target?: number;
}>();

const cardImage = useCardImage();
const { getTranslatedText } = useTranslation();
const el = ref<HTMLElement | null>(null);
const width = ref(1200);

// #36: columns derived from a target tile width, not a hardcoded breakpoint ladder.
const cols = computed(() => {
  const t = props.target ?? 190;
  const inner = Math.max(200, width.value - 16);
  let c = Math.max(2, Math.round(inner / t));
  if (inner / c > 240) c += 1;
  if (inner / c < 150 && c > 2) c -= 1;
  return c;
});
const tileWidth = computed(() => Math.round((width.value - 16) / cols.value));

let ro: ResizeObserver | undefined;
onMounted(() => {
  if (!el.value) return;
  ro = new ResizeObserver(([e]) => { if (e) width.value = e.contentRect.width; });
  ro.observe(el.value);
});
onUnmounted(() => ro?.disconnect());

const nameOf = (c: Card) =>
  (c as any).name ?? getTranslatedText("names", (c as any).name_ja ?? "", (c as any).name_ja ?? "");
</script>

<template>
  <div ref="el" class="w-full">
    <div
      class="grid"
      :class="variant === 'C' ? 'gap-5 p-4' : variant === 'A' ? 'gap-2 p-2' : 'gap-3 p-3'"
      :style="{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }"
    >
      <div v-for="card in cards" :key="card.id" class="group">
        <div
          class="relative overflow-hidden bg-muted transition"
          :class="[
            variant === 'C' ? 'rounded-none' : variant === 'A' ? 'rounded-sm' : 'rounded-lg',
            variant === 'C'
              ? 'ring-0 hover:brightness-105'
              : variant === 'A'
                ? 'ring-1 ring-border hover:ring-primary'
                : 'ring-1 ring-border hover:ring-2 hover:ring-primary shadow-sm hover:shadow-md',
          ]"
        >
          <img
            :src="cardImage(card.image_key)"
            :alt="nameOf(card)"
            loading="lazy"
            class="w-full aspect-400/559 object-cover"
          />
        </div>

        <div v-if="showNames" class="pt-1.5 px-0.5">
          <div
            class="truncate text-foreground"
            :class="variant === 'C' ? 'text-[11px] tracking-wide' : 'text-xs font-medium'"
          >
            {{ nameOf(card) }}
          </div>
          <div
            class="truncate text-muted-foreground"
            :class="variant === 'B' ? 'proto-num text-[10px]' : 'text-[10px]'"
          >
            {{ card.card_number }}
          </div>
        </div>
      </div>
    </div>

    <div class="px-3 pb-6 pt-2 text-[10px] text-muted-foreground">
      {{ cols }} columns · tile ≈{{ tileWidth }}px · grid {{ Math.round(width) }}px
    </div>
  </div>
</template>
