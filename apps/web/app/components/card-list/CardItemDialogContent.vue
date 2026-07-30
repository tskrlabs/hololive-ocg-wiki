<script setup lang="ts">
const cardImage = useCardImage();
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
    <DialogHeader class="h-0 overflow-hidden">
      <DialogTitle>{{ item.name || "" }}</DialogTitle>
      <DialogDescription> {{ item.name || "" }} </DialogDescription>
    </DialogHeader>

    <ScrollArea class="py-0 px-4">
      <div class="flex flex-col md:flex-row gap-2 md:gap-4">
        <Image
          class="flex-[0_0_300px] lg:flex-[0_0_400px]"
          :src="cardImage(item.image_key)"
          :img-attributes="{
            class: 'mx-auto w-full max-w-[400px]',
          }"
        />

        <div class="flex flex-col grow gap-2 md:gap-4">
          <CardDataNameBlock
            :name="item.name || ''"
            :id="item.id"
            :number="item.card_number"
            :original-name="item.original?.name"
          />

          <CardDataRowsBlock :item="item" />

          <CardDataDetailBlocks :item="item" />

          <CardDataQnaBlocks :item="item" />

          <CardDataSameNumberBlock :item="item" />

          <!-- links -->
          <!-- <div class="flex justify-between">
            <Button variant="link" class="p-0! text-xs" as-child>
              <a
                :href="`https://hololive-official-cardgame.com/cardlist/?id=${item.id}`"
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center gap-1"
              >
                <ExternalLink /> {{ $t("Official Site") }}
              </a>
            </Button>

            <DialogClose as-child>
              <Button type="button" variant="secondary">
                {{ $t("Close") }}
              </Button>
            </DialogClose>
          </div> -->
        </div>
      </div>
    </ScrollArea>
    <DialogFooter class="px-4 pb-4 md:p-4 md:pt-0">
      <div class="flex gap-2 md:gap-4 grow">
        <div
          class="hidden md:block md:flex-[0_0_300px] lg:flex-[0_0_400px]"
        ></div>
        <div class="flex justify-between grow">
          <Button variant="link" class="p-0! text-xs" as-child>
            <a
              :href="`https://hololive-official-cardgame.com/cardlist/?id=${item.id}`"
              target="_blank"
              rel="noopener noreferrer"
              class="flex items-center gap-1"
            >
              <ExternalLink /> {{ $t("Official Site") }}
            </a>
          </Button>

          <DialogClose as-child>
            <Button type="button" variant="secondary">
              {{ $t("Close") }}
            </Button>
          </DialogClose>
        </div>
      </div>
    </DialogFooter>
  </DialogContent>
</template>

<style lang="postcss" scoped>
/* .badge-text {
  font-size: 0.875rem;
  align-self: start;

  @media (min-width: 80rem) {
    font-size: 1rem;
  }
} */
</style>
