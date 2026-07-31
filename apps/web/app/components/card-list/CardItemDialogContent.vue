<script setup lang="ts">
/**
 * The dialog **container** around `CardDetail` (D15, #39).
 *
 * What is left here is only what makes this a dialog: the width ladder, the `90dvh` cap,
 * the scroll region, the title a dialog must announce, and the close affordance. The card
 * itself moved to `CardDetail`, so the page at `/{locale}/card/{set}/{stem}` can show the
 * same facts without this chrome — which is what stops the indexed page and the dialog
 * drifting into two descriptions of one card.
 *
 * No behaviour change in this commit. The dialog still opens from a tile, still scrolls
 * inside itself, and still does not touch the URL; pushing history is commit 9's job.
 */
import { ExternalLink } from "lucide-vue-next";
import type { Card } from "@/types/card";

import { ScrollArea } from "@/components/ui/scroll-area";

defineProps<{
  item: Card;
}>();
</script>

<template>
  <DialogContent
    hide-top-right-close
    class="grid-rows-[auto_minmax(0,1fr)_auto] p-0 max-h-[90dvh] sm:max-w-lg md:max-w-2xl lg:max-w-4xl"
  >
    <!--
      Visually collapsed, but present: a `Dialog` without a title is unnamed to a screen
      reader, and reka-ui warns about a missing `DialogDescription`. The card's name is
      the honest name for it.
    -->
    <DialogHeader class="h-0 overflow-hidden">
      <DialogTitle>{{ item.name || "" }}</DialogTitle>
      <DialogDescription>{{ item.name || "" }}</DialogDescription>
    </DialogHeader>

    <ScrollArea class="py-0 px-4">
      <CardDetail :item="item" variant="dialog" />
    </ScrollArea>

    <DialogFooter class="px-4 pb-4 md:p-4 md:pt-0">
      <div class="flex gap-2 md:gap-4 grow">
        <!-- Aligns the footer's controls under the text column, past the art. -->
        <div class="hidden md:block md:flex-[0_0_300px] lg:flex-[0_0_400px]"></div>
        <div class="flex justify-between grow">
          <Button variant="link" class="p-0! text-xs" as-child>
            <a
              :href="`https://hololive-official-cardgame.com/cardlist/?id=${item.id}`"
              target="_blank"
              rel="noopener noreferrer"
              class="flex items-center gap-1"
            >
              <ExternalLink aria-hidden="true" /> {{ $t("Official Site") }}
            </a>
          </Button>

          <DialogClose as-child>
            <Button type="button" variant="secondary">{{ $t("Close") }}</Button>
          </DialogClose>
        </div>
      </div>
    </DialogFooter>
  </DialogContent>
</template>
