<script lang="ts" setup>
import { MessagesSquare, Copy } from "lucide-vue-next";
import type { Card, CardCollection } from "@/types/card";
import { UseClipboard } from "@vueuse/components";

const { locale } = useI18n();
const { getCardsByCardNumbers } = useCardStoreAPI();

const props = defineProps<{
  item: Card;
}>();

// State for managing card dialogs
const selectedCard = ref<Card | null>(null);
const isCardDialogOpen = ref(false);
const isLoadingCard = ref(false);

// Function to handle card number click
const handleCardNumberClick = async (cardNumber: string) => {
  isLoadingCard.value = true;
  try {
    const cards = await getCardsByCardNumbers(
      [cardNumber],
      locale.value as any
    );
    if (cards.length > 0) {
      selectedCard.value = cards[0]!;
      isCardDialogOpen.value = true;
    }
  } catch (error) {
    console.error("Failed to fetch card:", error);
  } finally {
    isLoadingCard.value = false;
  }
};
</script>

<template>
  <div v-if="item?.qa_items?.length" class="">
    <Accordion type="single" collapsible>
      <AccordionItem value="item-1">
        <AccordionTrigger
          class="flex gap-2 p-2 rounded-lg border bg-accent/50 hover:no-underline"
        >
          <div class="flex text-sm gap-2">
            <MessagesSquare class="size-5" /> Q&A
          </div>
        </AccordionTrigger>
        <AccordionContent
          class="pb-0 pt-2 md:pt-4 flex flex-col gap-2 md:gap-4"
        >
          <template v-for="(qaItem, index) in item?.qa_items" :key="index">
            <div
              class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50 ml-2 md:ml-4"
            >
              <div class="font-semibold">
                {{ qaItem.title }}
              </div>

              <div class="grid grid-cols-[auto_1fr] gap-2">
                <div class="">Q:</div>
                <div class="">
                  {{ qaItem.question }}
                </div>
                <div class="">A:</div>
                <div class="">
                  {{ qaItem.answer }}
                </div>
              </div>

              <div class="flex flex-wrap gap-2">
                <template
                  v-for="(cardNumber, cardIndex) in qaItem.related_cards?.card_number"
                  :key="cardIndex"
                >
                  <UseClipboard v-slot="{ copy, copied }" :source="cardNumber">
                    <div class="relative flex gap-1">
                      <!-- Card number badge (clickable to open card) -->
                      <Badge variant="outline" class="p-0 gap-0">
                        <Badge
                          variant="outline"
                          class="cursor-pointer hover:bg-primary/10 transition-colors border-0"
                          :class="{ 'opacity-50': isLoadingCard }"
                          @click="handleCardNumberClick(cardNumber)"
                          :disabled="isLoadingCard"
                        >
                          {{ cardNumber }}
                        </Badge>

                        <!-- Copy button -->
                        <Badge
                          variant="outline"
                          class="cursor-pointer hover:bg-primary/10 transition-colors p-1 border-0"
                          @click="copy()"
                        >
                          <Copy class="w-3 h-3" />
                        </Badge>
                      </Badge>

                      <!-- Copied indicator -->
                      <Transition name="copied">
                        <span
                          v-if="copied"
                          class="absolute bottom-full md:top-auto md:bottom-[calc(100%+0rem)] left-2/4 -translate-x-2/4 -translate-y-1 rounded-lg bg-green-400 text-slate-800 text-xs py-1 px-2 whitespace-nowrap z-10"
                        >
                          {{ $t("Copied") }}
                        </span>
                      </Transition>
                    </div>
                  </UseClipboard>
                </template>
              </div>
            </div>
          </template>
        </AccordionContent>
      </AccordionItem>
    </Accordion>

    <!-- Card Dialog -->
    <Dialog v-model:open="isCardDialogOpen">
      <CardItemDialogContent v-if="selectedCard" :item="selectedCard" />
    </Dialog>
  </div>
</template>
