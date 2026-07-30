<script setup lang="ts">
/**
 * ⚠️ PROTOTYPE — throwaway. Delete once #35 is decided.
 *
 * The three directions differ structurally, not just chromatically:
 *   A "Archive"  — dense reference tool. Rail with labelled sections, tight grid,
 *                  serif headings, names always on. Feels like a catalogue.
 *   B "Console"  — the deck-builder's instrument. Rail as a control panel with live
 *                  counts, mono numerics, medium density, strong focus states.
 *   C "Gallery"  — the art leads. Wide gutters, no chrome on tiles, uppercase micro-
 *                  labels, names off by default. Feels like a print portfolio.
 */
import type { Card } from "@/types/card";
import { Funnel, Moon, RotateCcw, Search, Sun } from "lucide-vue-next";

const colorMode = useColorMode();
function toggleMode() {
  colorMode.preference = colorMode.value === "dark" ? "light" : "dark";
}

const props = defineProps<{ variant: string; cards: Card[]; total: number }>();

const showNames = computed(() => props.variant !== "C");
const target = computed(() => (props.variant === "A" ? 155 : props.variant === "C" ? 235 : 190));

/** D inherits B's structure — every layout branch below treats them the same. */
const structure = computed(() =>
  props.variant === "D" || props.variant === "E" ? "B" : props.variant,
);

const COLORS = ["white", "green", "red", "blue", "yellow", "purple"];
const icon = useGameIcon();
const picked = ref<Record<string, boolean>>({});
const pendingCount = computed(() => Object.values(picked.value).filter(Boolean).length);

const railWidth = computed(() => (structure.value === "C" ? "w-64" : "w-[280px]"));
</script>

<template>
  <div class="proto-root flex h-dvh flex-col bg-background text-foreground">
    <!-- header: flex child, NOT sticky (#44) -->
    <header
      class="flex shrink-0 items-center gap-3 border-b bg-background"
      :class="structure === 'C' ? 'px-6 py-4' : 'px-4 py-3'"
    >
      <div
        class="proto-display"
        :class="structure === 'C' ? 'text-xs' : structure === 'A' ? 'text-lg' : 'text-base'"
      >
        <template v-if="structure === 'C'">HOLOLIVE OCG</template>
        <template v-else>Hololive OCG Wiki</template>
      </div>
      <div class="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
        <span :class="structure === 'B' ? 'proto-num' : ''">{{ total }} cards</span>
        <button
          class="flex size-8 items-center justify-center border"
          :class="structure === 'C' ? 'rounded-none' : 'rounded-md'"
          title="Toggle light/dark"
          @click="toggleMode"
        >
          <Moon v-if="colorMode.value !== 'dark'" class="size-4" />
          <Sun v-else class="size-4" />
        </button>
      </div>
    </header>

    <div class="flex min-h-0 flex-1">
      <!-- rail (#36: 280px, own scroll region, pinned footer) -->
      <aside
        class="hidden shrink-0 flex-col border-r bg-background lg:flex"
        :class="railWidth"
      >
        <div class="min-h-0 flex-1 overflow-y-auto" :class="structure === 'C' ? 'p-5' : 'p-4'">
          <!-- search lives in the rail on desktop (#36) -->
          <div class="relative mb-5">
            <Search class="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              :placeholder="structure === 'C' ? 'SEARCH' : 'Search cards…'"
              class="w-full border bg-background py-2 pl-8 pr-2 text-xs outline-none focus:ring-2 focus:ring-ring"
              :class="structure === 'C' ? 'rounded-none tracking-widest' : 'rounded-md'"
            />
          </div>

          <div
            class="mb-2 text-muted-foreground"
            :class="structure === 'C' ? 'proto-display text-[10px]' : 'text-[11px] font-semibold uppercase tracking-wide'"
          >
            {{ structure === "C" ? "COLOUR" : "Colour" }}
          </div>
          <div class="mb-6 flex flex-wrap gap-1.5">
            <button
              v-for="c in COLORS"
              :key="c"
              class="flex items-center gap-1.5 border px-2 py-1.5 text-[11px] transition"
              :class="[
                structure === 'C' ? 'rounded-none' : 'rounded-md',
                picked[c]
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border hover:border-foreground/40',
              ]"
              @click="picked[c] = !picked[c]"
            >
              <img :src="icon.color(c)" class="size-3.5" :alt="c" />
              {{ c }}
            </button>
          </div>

          <div
            class="mb-2 text-muted-foreground"
            :class="structure === 'C' ? 'proto-display text-[10px]' : 'text-[11px] font-semibold uppercase tracking-wide'"
          >
            {{ structure === "C" ? "RARITY" : "Rarity" }}
          </div>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="r in ['C', 'U', 'R', 'RR', 'SR', 'UR', 'OSR']"
              :key="r"
              class="border px-2 py-1 text-[11px] hover:border-foreground/40"
              :class="[structure === 'C' ? 'rounded-none' : 'rounded-md', structure === 'B' ? 'proto-num' : '']"
            >
              {{ r }}
            </button>
          </div>
        </div>

        <!-- pinned Apply footer (#32 keeps draft→apply; #36 drops "Close") -->
        <div class="shrink-0 border-t p-3">
          <button
            class="mb-2 flex w-full items-center justify-center gap-2 bg-primary px-3 py-2 text-xs font-medium text-primary-foreground disabled:opacity-40"
            :class="structure === 'C' ? 'rounded-none tracking-widest' : 'rounded-md'"
            :disabled="pendingCount === 0"
          >
            <Funnel class="size-3.5" />
            {{ pendingCount ? `Apply (${pendingCount})` : "No changes" }}
          </button>
          <button
            class="flex w-full items-center justify-center gap-2 border px-3 py-2 text-xs"
            :class="structure === 'C' ? 'rounded-none' : 'rounded-md'"
            @click="picked = {}"
          >
            <RotateCcw class="size-3.5" /> Reset
          </button>
        </div>
      </aside>

      <!-- grid: flex-1 min-h-0, real remaining height (#44) -->
      <main class="min-h-0 flex-1 overflow-y-auto">
        <ProtoGrid :cards="cards" :variant="structure" :show-names="showNames" :target="target" />
      </main>
    </div>
  </div>
</template>
