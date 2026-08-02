<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { ScrollAreaScrollbar, type ScrollAreaScrollbarProps, ScrollAreaThumb } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = withDefaults(defineProps<ScrollAreaScrollbarProps & { class?: HTMLAttributes['class'] }>(), {
  orientation: 'vertical',
})

const delegatedProps = reactiveOmit(props, 'class')
</script>

<template>
  <ScrollAreaScrollbar
    data-slot="scroll-area-scrollbar"
    v-bind="delegatedProps"
    :class="
      cn('flex touch-none p-px transition-colors select-none',
         orientation === 'vertical'
           && 'h-full w-2.5 border-l border-l-transparent',
         orientation === 'horizontal'
           && 'h-2.5 flex-col border-t border-t-transparent',
         props.class)"
  >
    <!--
      `bg-border-strong`, not the scaffold's `bg-border`.

      A scrollbar reports position within a scroll region, which makes it a UI component
      conveying state — and D5 is explicit that `--border` at 1.23:1 cannot carry that
      (WCAG 1.4.11 wants 3:1). `--border-strong` measures 3.10–4.13 across every surface
      these appear on.

      It is also what the native scrollbars use, set once in `tailwind.css`. The site has
      both systems — this one on five surfaces, plain `overflow-y-auto` everywhere else —
      and a user moving between the card dialog and the card grid should not be able to
      tell which is which.
    -->
    <ScrollAreaThumb
      data-slot="scroll-area-thumb"
      class="bg-border-strong relative flex-1 rounded-full"
    />
  </ScrollAreaScrollbar>
</template>
