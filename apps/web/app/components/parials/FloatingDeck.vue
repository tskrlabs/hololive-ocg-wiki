<script setup lang="ts">
import { Expand, Shrink, Eye } from "lucide-vue-next";
import { sectionByKey } from "~/composables/deckSections";
import { toast } from "vue-sonner";

const { t } = useI18n();
const localeRoute = useLocaleRoute();

const decks = useDecks();

const isActive = ref(false);
const toggleFloatingDeck = () => {
  isActive.value = !isActive.value;
};

const isEditing = computed(() => decks.isEditing.value);
const currentDeck = computed(() => decks.currentDeck.value);

watch(
  currentDeck,
  (newDeck, oldDeck) => {
    if (newDeck && newDeck.id !== oldDeck?.id) {
      decks.isEditing.value = true;
      isActive.value = true;
    } else if (!newDeck) {
      decks.isEditing.value = false;
      isActive.value = false;
    }
  },
  { immediate: true }
);

const oshiCardIds = computed(() => {
  return decks.currentDeck.value?.oshiCardIds || [];
});

const mainCardIds = computed(() => {
  return decks.currentDeck.value?.mainCardIds || [];
});

const yellCardIds = computed(() => {
  return decks.currentDeck.value?.yellCardIds || [];
});

// Pre-fetch cards in deck for better performance
// const allDeckCardIds = computed(() => {
//   return [...oshiCardIds.value, ...mainCardIds.value, ...yellCardIds.value];
// });

const goToDetailPage = () => {
  if (!currentDeck.value) {
    toast.warning(t("Please select a deck to continue."));
    return;
  }
  const code = decks.getDeckCode(currentDeck.value.id).code;
  const route = localeRoute({ name: "deck-code", params: { code } });
  if (route) {
    navigateTo(route.fullPath);
  } else {
    toast.error(t("Deck detail page not found."));
  }
};
</script>

<template>
  <Transition name="fade-up">
    <div
      v-show="isEditing"
      class="fixed bottom-13 md:bottom-16 left-0 m-2 md:m-4 z-40"
    >
      <div
        class="rounded-lg shadow-lg border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90"
      >
        <div class="flex p-2 md:p-4">
          <Button
            size="sm"
            class="text-[12px] md:text-sm mr-2"
            @click="toggleFloatingDeck"
          >
            <Expand v-if="!isActive" class="size-3 md:size-4" />
            <Shrink v-else class="size-3 md:size-4" />
            {{ !isActive ? $t("Expand") : $t("Collapse") }}
          </Button>

          <Button
            size="sm"
            variant="outline"
            class="text-[12px] md:text-sm ml-auto"
            @click="goToDetailPage"
          >
            <Eye /> {{ $t("Go to Detail Page") }}
          </Button>
        </div>

        <div class="flex md:pt-0 pb-2 md:pb-4">
          <ScrollArea class="max-h-[40vh]">
            <div class="flex flex-col gap-2 md:gap-4 px-2 md:px-4">
              <div class="border rounded-lg p-2 md:p-3 flex flex-col gap-3">
                <div class="flex items-center gap-2">
                  {{ $t("Oshi") }}
                  <DeckSectionBadge
                    v-if="currentDeck"
                    :deck="currentDeck"
                    :section="sectionByKey('oshi')"
                  />
                </div>

                <FloatingDeckCardList
                  v-show="isActive"
                  :card-ids="oshiCardIds"
                  class="mt-2"
                />
              </div>

              <div class="border rounded-lg p-2 md:p-3 flex flex-col gap-3">
                <div class="flex items-center gap-2">
                  {{ $t("Main Deck") }}
                  <DeckSectionBadge
                    v-if="currentDeck"
                    :deck="currentDeck"
                    :section="sectionByKey('main')"
                  />
                </div>
                <FloatingDeckCardList
                  v-show="isActive"
                  :card-ids="mainCardIds"
                  class="mt-2"
                />
              </div>

              <div class="border rounded-lg p-2 md:p-3 flex flex-col gap-3">
                <div class="flex items-center gap-2">
                  {{ $t("Yell Deck") }}

                  <DeckSectionBadge
                    v-if="currentDeck"
                    :deck="currentDeck"
                    :section="sectionByKey('yell')"
                  />
                </div>
                <FloatingDeckCardList
                  v-show="isActive"
                  :card-ids="yellCardIds"
                  class="mt-2"
                />
              </div>
            </div>
          </ScrollArea>
        </div>
      </div>
    </div>
  </Transition>
</template>
