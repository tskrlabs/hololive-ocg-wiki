<script setup lang="ts">
import { sectionByKey } from "~/composables/deckSections";
import { toast } from "vue-sonner";
import type { Deck } from "~/types/deck";
import { Database, Scaling } from "lucide-vue-next";

const { t, locale } = useI18n();
const route = useRoute();
const localePath = useLocalePath();
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
    toast.error(t("errors.deck.noCode"));
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
    // `duration: Infinity` was here, which made this the one toast in the app that never
    // goes away — on a page that then renders nothing, so the message sat over an empty
    // screen with the close button as the only exit (#57). The page's own empty state
    // says the same thing and stays put, which is what a permanent condition wants; the
    // toast reports the event and leaves.
    toast.error(t("errors.deck.invalidCode"));
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

  <!--
    The shell is now exactly one viewport tall (#44), so the page no longer scrolls as a
    whole and this region owns its own scrolling. `min-h-0` lets it shrink below its
    content, which is what allows it to scroll rather than pushing the footer away.
  -->
  <main class="grow min-h-0 overflow-y-auto p-2 md:p-4">
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

      <!--
        `DeckDetailCompactModeCardList` was deleted here. It had been commented out at
        this, its only call site — so it was dead code that `make check` still typechecked
        and every reader still had to rule out. Compact mode is not lost: it is the
        `is-compact-mode` prop below, which is what the toggle has actually driven.
      -->
      <div class="border rounded-lg p-2 md:p-3 flex flex-col gap-3">
        <div class="flex items-center gap-2">
          <div class="text-md md:text-lg font-semibold">
            {{ $t("Oshi") }}
          </div>
          <DeckSectionBadge
            :deck="deck"
            :section="sectionByKey('oshi')"
          />
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
          <DeckSectionBadge
            :deck="deck"
            :section="sectionByKey('main')"
          />
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
          <DeckSectionBadge
            :deck="deck"
            :section="sectionByKey('yell')"
          />
        </div>

        <DeckDetailCardList
          :card-ids="deck.yellCardIds"
          :is-compact-mode="compactModeState"
        />
      </div>
    </div>

    <!--
      An undecodable code used to render an empty page under a toast that never expired
      (#57). A deck code that does not decode is permanent, not retryable — so this says
      so and offers the way out, the same shape the card page's 404 uses.
    -->
    <div
      v-else
      class="flex min-h-[50vh] flex-col items-center justify-center text-center"
    >
      <p class="text-xl font-medium">{{ $t("errors.deck.invalidCode") }}</p>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ $t("errors.deck.invalidCodeDetail") }}
      </p>
      <Button variant="outline" size="sm" class="mt-4" as-child>
        <NuxtLink :to="localePath('/')">{{ $t("Card List") }}</NuxtLink>
      </Button>
    </div>
  </main>

  <AppFooter>
    <AppFooterDeckDetailStatus />

    <div class="ml-auto flex items-center gap-2">
      <AppFooterDeckDetailOptionsButton />
    </div>
  </AppFooter>
</template>
