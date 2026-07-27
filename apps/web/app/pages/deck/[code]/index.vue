<script setup lang="ts">
import { toast } from "vue-sonner";
import type { Deck } from "~/types/deck";
import { Database, Scaling } from "lucide-vue-next";

const { t, locale } = useI18n();
const route = useRoute();
const decks = useDecks();
const deck = ref<Deck | null>(null);

const compactModeState = ref(false);

// SEO meta tags
const title = ref("Deck Detail Page");
const description = ref(
  "View and manage your Hololive OCG deck configuration."
);

onMounted(() => {
  if (!route.params.code) {
    toast.error(t("No deck code provided."));
    return;
  }

  const code = route.params.code as string;

  const checked = decks.checkForDeckCode(code);

  if (checked) {
    deck.value = checked;

    if (checked.name) {
      if (checked.author) {
        title.value = `${checked.name} by ${checked.author}`;
        description.value = t("deck.seo.descriptionWithAuthor", {
          deckName: checked.name,
          author: checked.author,
          mainCount: checked.mainCardIds.length,
          yellCount: checked.yellCardIds.length,
          oshiCount: checked.oshiCardIds.length,
        });
      } else {
        title.value = checked.name;
        description.value = t("deck.seo.description", {
          deckName: checked.name,
          mainCount: checked.mainCardIds.length,
          yellCount: checked.yellCardIds.length,
          oshiCount: checked.oshiCardIds.length,
        });
      }
    }
  } else {
    toast.error(t(`Failed to import shared deck.`), {
      duration: Infinity,
    });
  }
});

useSeoMeta({
  title,
  description,
  robots: "noindex, nofollow", // Don't index dynamic deck pages
  ogTitle: title,
  ogDescription: description,
  ogType: "website",
  twitterCard: "summary",
  twitterTitle: title,
  twitterDescription: description,
});

useHead({
  htmlAttrs: {
    lang: locale.value,
  },
});
</script>

<template>
  <AppHeader>
    <Button class="text-[12px] md:text-sm" @click="$router.push('/')">
      <Database class="size-3 md:size-4" />
      {{ $t("Card List") }}
    </Button>
  </AppHeader>

  <div class="grow p-2 md:p-4">
    <div v-if="deck" class="flex flex-col gap-2 md:gap-4">
      <div class="flex gap-2">
        <div
          class="flex items-center grow border rounded-md px-2 md:px-3 py-1 bg-gray-100/95 dark:bg-gray-800/95"
        >
          <div class="flex items-center gap-2">
            <h1 class="text-md md:text-lg font-semibold">{{ deck.name }}</h1>
            <span
              v-if="deck.author"
              class="text-sm text-gray-500 dark:text-gray-400"
            >
              by {{ deck.author }}
            </span>
          </div>
        </div>

        <div class="flex items-center">
          <Toggle size="lg" variant="outline" v-model="compactModeState">
            <Scaling />
            <span class="hidden md:inline"> {{ $t("Compact Mode") }} </span>
          </Toggle>
        </div>
      </div>

      <!-- <template v-if="compactModeState">
        <DeckDetailCompactModeCardList
          :oshi-card-ids="deck.oshiCardIds"
          :main-card-ids="deck.mainCardIds"
          :yell-card-ids="deck.yellCardIds"
        />
      </template>

      <template v-else> -->
      <div class="border rounded-lg p-2 md:p-3 flex flex-col gap-3">
        <div class="flex items-center gap-2">
          <div class="text-md md:text-lg font-semibold">
            {{ $t("Oshi") }}
          </div>
          <Badge
            class="px-1 text-[8px] md:text-xs"
            :class="
              deck.oshiCardIds.length > 1
                ? 'bg-red-500/15 border-red-500/50 text-red-500'
                : deck.oshiCardIds.length === 1
                ? 'bg-emerald-500/15 border-emerald-500/50 text-emerald-500'
                : 'border-gray-400 dark:border-gray-600 bg-gray-400/20 dark:bg-gray-600/20 text-gray-700 dark:text-gray-400'
            "
            variant="outline"
            size="sm"
          >
            {{ `${deck.oshiCardIds.length}/1` }}
          </Badge>
        </div>

        <DeckDetailCardList
          :card-ids="deck.oshiCardIds"
          :is-compact-mode="compactModeState"
        />
      </div>

      <div class="border rounded-lg p-2 md:p-3 flex flex-col gap-3">
        <div class="flex items-center gap-2">
          <div class="text-md md:text-lg font-semibold">
            {{ $t("Main Deck") }}
          </div>
          <Badge
            class="px-1 text-[8px] md:text-xs"
            :class="
              deck.mainCardIds.length > 50
                ? 'bg-red-500/15 border-red-500/50 text-red-500'
                : deck.mainCardIds.length === 50
                ? 'bg-emerald-500/15 border-emerald-500/50 text-emerald-500'
                : 'border-gray-400 dark:border-gray-600 bg-gray-400/20 dark:bg-gray-600/20 text-gray-700 dark:text-gray-400'
            "
            variant="outline"
            size="sm"
          >
            {{ `${deck.mainCardIds.length}/50` }}
          </Badge>
        </div>

        <DeckDetailCardList
          :card-ids="deck.mainCardIds"
          :is-compact-mode="compactModeState"
        />
      </div>

      <div class="border rounded-lg p-2 md:p-3 flex flex-col gap-3">
        <div class="flex items-center gap-2">
          <div class="text-md md:text-lg font-semibold">
            {{ $t("Yell Deck") }}
          </div>
          <Badge
            class="px-1 text-[8px] md:text-xs"
            :class="
              deck.yellCardIds.length > 20
                ? 'bg-red-500/15 border-red-500/50 text-red-500'
                : deck.yellCardIds.length === 20
                ? 'bg-emerald-500/15 border-emerald-500/50 text-emerald-500'
                : 'border-gray-400 dark:border-gray-600 bg-gray-400/20 dark:bg-gray-600/20 text-gray-700 dark:text-gray-400'
            "
            variant="outline"
            size="sm"
          >
            {{ `${deck.yellCardIds.length}/20` }}
          </Badge>
        </div>

        <DeckDetailCardList
          :card-ids="deck.yellCardIds"
          :is-compact-mode="compactModeState"
        />
      </div>
      <!-- </template> -->
    </div>
  </div>

  <AppFooter>
    <AppFooterDeckDetailStatus />

    <div class="ml-auto flex items-center gap-2">
      <AppFooterDeckDetailOptionsButton />
    </div>
  </AppFooter>
</template>
