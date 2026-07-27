<script setup lang="ts">
import { Database } from "lucide-vue-next";

const { t, locale } = useI18n();
const { siteUrl } = useRuntimeConfig().public;

useSeoMeta({
  title: t("howToUse.title"),
  description: t("howToUse.description"),
  ogTitle: t("howToUse.title"),
  ogDescription: t("howToUse.description"),
  ogType: "article",
  twitterCard: "summary",
  twitterTitle: t("howToUse.title"),
  twitterDescription: t("howToUse.description"),
});

useHead({
  bodyAttrs: {
    class: "bg-background",
  },
  htmlAttrs: {
    lang: locale.value,
  },
  script: [
    {
      type: "application/ld+json",
      innerHTML: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "HowTo",
        name: "How to Use Hololive OCG Wiki",
        description:
          "Complete guide on how to use the Hololive OCG Wiki for searching cards, building decks, and more.",
        image: `${siteUrl}/icon.png`,
        totalTime: "PT10M",
        estimatedCost: {
          "@type": "MonetaryAmount",
          currency: "USD",
          value: "0",
        },
        supply: [
          {
            "@type": "HowToSupply",
            name: "Web Browser",
          },
          {
            "@type": "HowToSupply",
            name: "Internet Connection",
          },
        ],
        tool: [
          {
            "@type": "HowToTool",
            name: "Hololive OCG Wiki",
          },
        ],
        step: [
          {
            "@type": "HowToStep",
            name: "Search for Cards",
            text: "Use the search functionality to find specific cards by name, type, or other attributes.",
          },
          {
            "@type": "HowToStep",
            name: "Filter Cards",
            text: "Apply filters to narrow down card results by color, rarity, card type, and more.",
          },
          {
            "@type": "HowToStep",
            name: "Build Decks",
            text: "Create and manage your Oshi, Main, and Yell decks using the deck builder feature.",
          },
          {
            "@type": "HowToStep",
            name: "Share Decks",
            text: "Share your deck configurations with others using deck codes.",
          },
        ],
      }),
    },
  ],
});
</script>

<template>
  <div class="min-h-screen">
    <AppHeader>
      <Button class="text-[12px] md:text-sm" @click="$router.push('/')">
        <Database class="size-3 md:size-4" />
        {{ $t("Card List") }}
      </Button>
    </AppHeader>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8 max-w-4xl">
      <!-- Introduction -->
      <section class="mb-12">
        <div class="bg-card p-6 rounded-lg border">
          <h2 class="text-2xl font-bold mb-4 flex items-center gap-2">
            <Icon name="lucide:book-open" class="w-6 h-6 text-primary" />
            {{ $t("howToUse.introduction.title") }}
          </h2>
          <p class="text-muted-foreground text-lg leading-relaxed">
            {{ $t("howToUse.introduction.description") }}
          </p>
        </div>
      </section>

      <!-- Navigation -->
      <nav class="mb-8">
        <div class="bg-muted/50 p-4 rounded-lg">
          <h3 class="font-semibold mb-3">
            {{ $t("howToUse.tableOfContents") }}
          </h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            <a href="#searching" class="text-primary hover:underline">{{
              $t("howToUse.sections.searching")
            }}</a>
            <a href="#filtering" class="text-primary hover:underline">{{
              $t("howToUse.sections.filtering")
            }}</a>
            <a href="#deckBuilder" class="text-primary hover:underline">{{
              $t("howToUse.sections.deckBuilder")
            }}</a>
            <a href="#cardDetails" class="text-primary hover:underline">{{
              $t("howToUse.sections.cardDetails")
            }}</a>
            <a href="#sharing" class="text-primary hover:underline">{{
              $t("howToUse.sections.sharing")
            }}</a>
            <a href="#tips" class="text-primary hover:underline">{{
              $t("howToUse.sections.tips")
            }}</a>
          </div>
        </div>
      </nav>

      <!-- Searching Cards -->
      <section id="searching" class="mb-12">
        <h2 class="text-2xl font-bold mb-6 flex items-center gap-2">
          <Icon name="lucide:search" class="w-6 h-6 text-primary" />
          {{ $t("howToUse.searching.title") }}
        </h2>

        <div class="space-y-6">
          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.searching.basicSearch.title") }}
            </h3>
            <p class="text-muted-foreground mb-4">
              {{ $t("howToUse.searching.basicSearch.description") }}
            </p>
            <div class="bg-muted p-4 rounded-md font-mono text-sm">
              {{ $t("howToUse.searching.basicSearch.examples") }}
            </div>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.searching.advancedSearch.title") }}
            </h3>
            <p class="text-muted-foreground mb-4">
              {{ $t("howToUse.searching.advancedSearch.description") }}
            </p>
            <ul class="space-y-2 text-sm">
              <li class="flex items-start gap-2">
                <span class="text-primary font-mono">•</span>
                <span>{{ $t("howToUse.searching.advancedSearch.tip1") }}</span>
              </li>
              <li class="flex items-start gap-2">
                <span class="text-primary font-mono">•</span>
                <span>{{ $t("howToUse.searching.advancedSearch.tip2") }}</span>
              </li>
              <li class="flex items-start gap-2">
                <span class="text-primary font-mono">•</span>
                <span>{{ $t("howToUse.searching.advancedSearch.tip3") }}</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <!-- Filtering Cards -->
      <section id="filtering" class="mb-12">
        <h2 class="text-2xl font-bold mb-6 flex items-center gap-2">
          <Icon name="lucide:filter" class="w-6 h-6 text-primary" />
          {{ $t("howToUse.filtering.title") }}
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.filtering.cardType.title") }}
            </h3>
            <p class="text-muted-foreground mb-3">
              {{ $t("howToUse.filtering.cardType.description") }}
            </p>
            <div class="space-y-1 text-sm">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 bg-blue-500 rounded-full"></span>
                <span>{{ $t("cardTypes.character") }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 bg-yellow-500 rounded-full"></span>
                <span>{{ $t("cardTypes.oshiCharacter") }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>{{ $t("cardTypes.supportCheer") }}</span>
              </div>
            </div>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.filtering.colors.title") }}
            </h3>
            <p class="text-muted-foreground mb-3">
              {{ $t("howToUse.filtering.colors.description") }}
            </p>
            <div class="grid grid-cols-3 gap-2 text-sm">
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 bg-white border rounded-full"></span>
                <span>{{ $t("colors.white") }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 bg-green-500 rounded-full"></span>
                <span>{{ $t("colors.green") }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 bg-red-500 rounded-full"></span>
                <span>{{ $t("colors.red") }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 bg-blue-500 rounded-full"></span>
                <span>{{ $t("colors.blue") }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 bg-purple-500 rounded-full"></span>
                <span>{{ $t("colors.purple") }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 bg-yellow-500 rounded-full"></span>
                <span>{{ $t("colors.yellow") }}</span>
              </div>
            </div>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.filtering.rarity.title") }}
            </h3>
            <p class="text-muted-foreground mb-3">
              {{ $t("howToUse.filtering.rarity.description") }}
            </p>
            <div class="flex flex-wrap gap-2">
              <span class="px-2 py-1 bg-gray-500 text-white text-xs rounded"
                >C</span
              >
              <span class="px-2 py-1 bg-blue-500 text-white text-xs rounded"
                >R</span
              >
              <span class="px-2 py-1 bg-purple-500 text-white text-xs rounded"
                >SR</span
              >
              <span class="px-2 py-1 bg-yellow-500 text-white text-xs rounded"
                >UR</span
              >
            </div>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.filtering.reset.title") }}
            </h3>
            <p class="text-muted-foreground mb-3">
              {{ $t("howToUse.filtering.reset.description") }}
            </p>
            <div class="flex items-center gap-2 text-sm">
              <Icon name="lucide:rotate-ccw" class="w-4 h-4 text-primary" />
              <span>{{ $t("Reset") }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Deck Builder -->
      <section id="deckBuilder" class="mb-12">
        <h2 class="text-2xl font-bold mb-6 flex items-center gap-2">
          <Icon name="lucide:layers" class="w-6 h-6 text-primary" />
          {{ $t("howToUse.deckBuilder.title") }}
        </h2>

        <div class="space-y-6">
          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.deckBuilder.creating.title") }}
            </h3>
            <ol class="space-y-3 text-muted-foreground">
              <li class="flex items-start gap-3">
                <span
                  class="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-semibold"
                  >1</span
                >
                <span>{{ $t("howToUse.deckBuilder.creating.step1") }}</span>
              </li>
              <li class="flex items-start gap-3">
                <span
                  class="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-semibold"
                  >2</span
                >
                <span>{{ $t("howToUse.deckBuilder.creating.step2") }}</span>
              </li>
              <li class="flex items-start gap-3">
                <span
                  class="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-semibold"
                  >3</span
                >
                <span>{{ $t("howToUse.deckBuilder.creating.step3") }}</span>
              </li>
              <li class="flex items-start gap-3">
                <span
                  class="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-semibold"
                  >4</span
                >
                <span>{{ $t("howToUse.deckBuilder.creating.step4") }}</span>
              </li>
            </ol>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-card p-6 rounded-lg border">
              <h3 class="text-xl font-semibold mb-3">
                {{ $t("howToUse.deckBuilder.deckTypes.title") }}
              </h3>
              <div class="space-y-3">
                <div class="flex items-center gap-3">
                  <Icon name="lucide:star" class="w-5 h-5 text-yellow-500" />
                  <div>
                    <div class="font-medium">{{ $t("Oshi") }}</div>
                    <div class="text-sm text-muted-foreground">
                      {{ $t("howToUse.deckBuilder.deckTypes.oshi") }}
                    </div>
                  </div>
                </div>
                <div class="flex items-center gap-3">
                  <Icon name="lucide:layers" class="w-5 h-5 text-blue-500" />
                  <div>
                    <div class="font-medium">{{ $t("Main Deck") }}</div>
                    <div class="text-sm text-muted-foreground">
                      {{ $t("howToUse.deckBuilder.deckTypes.main") }}
                    </div>
                  </div>
                </div>
                <div class="flex items-center gap-3">
                  <Icon name="lucide:heart" class="w-5 h-5 text-red-500" />
                  <div>
                    <div class="font-medium">{{ $t("Yell Deck") }}</div>
                    <div class="text-sm text-muted-foreground">
                      {{ $t("howToUse.deckBuilder.deckTypes.yell") }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="bg-card p-6 rounded-lg border">
              <h3 class="text-xl font-semibold mb-3">
                {{ $t("howToUse.deckBuilder.management.title") }}
              </h3>
              <ul class="space-y-2 text-sm text-muted-foreground">
                <li class="flex items-center gap-2">
                  <Icon name="lucide:edit" class="w-4 h-4 text-primary" />
                  <span>{{ $t("howToUse.deckBuilder.management.edit") }}</span>
                </li>
                <li class="flex items-center gap-2">
                  <Icon name="lucide:copy" class="w-4 h-4 text-primary" />
                  <span>{{ $t("howToUse.deckBuilder.management.copy") }}</span>
                </li>
                <li class="flex items-center gap-2">
                  <Icon name="lucide:share" class="w-4 h-4 text-primary" />
                  <span>{{ $t("howToUse.deckBuilder.management.share") }}</span>
                </li>
                <li class="flex items-center gap-2">
                  <Icon name="lucide:trash" class="w-4 h-4 text-primary" />
                  <span>{{
                    $t("howToUse.deckBuilder.management.delete")
                  }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- Card Details -->
      <section id="cardDetails" class="mb-12">
        <h2 class="text-2xl font-bold mb-6 flex items-center gap-2">
          <Icon name="lucide:info" class="w-6 h-6 text-primary" />
          {{ $t("howToUse.cardDetails.title") }}
        </h2>

        <div class="bg-card p-6 rounded-lg border">
          <p class="text-muted-foreground mb-4">
            {{ $t("howToUse.cardDetails.description") }}
          </p>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 class="text-lg font-semibold mb-3">
                {{ $t("howToUse.cardDetails.basicInfo.title") }}
              </h3>
              <ul class="space-y-2 text-sm text-muted-foreground">
                <li>• {{ $t("fields.name") }}</li>
                <li>• {{ $t("fields.cardType") }}</li>
                <li>• {{ $t("fields.color") }}</li>
                <li>• {{ $t("fields.rarity") }}</li>
                <li>• {{ $t("fields.set") }}</li>
                <li>• {{ $t("fields.illustrator") }}</li>
              </ul>
            </div>

            <div>
              <h3 class="text-lg font-semibold mb-3">
                {{ $t("howToUse.cardDetails.gameInfo.title") }}
              </h3>
              <ul class="space-y-2 text-sm text-muted-foreground">
                <li>• {{ $t("fields.hp") }} / {{ $t("fields.life") }}</li>
                <li>• {{ $t("fields.cost") }}</li>
                <li>• {{ $t("fields.damage") }}</li>
                <li>• {{ $t("fields.arts") }}</li>
                <li>• {{ $t("fields.ability") }}</li>
                <li>• {{ $t("fields.keyword") }}</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- Sharing -->
      <section id="sharing" class="mb-12">
        <h2 class="text-2xl font-bold mb-6 flex items-center gap-2">
          <Icon name="lucide:share-2" class="w-6 h-6 text-primary" />
          {{ $t("howToUse.sharing.title") }}
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.sharing.deckCodes.title") }}
            </h3>
            <p class="text-muted-foreground mb-4">
              {{ $t("howToUse.sharing.deckCodes.description") }}
            </p>
            <div class="space-y-2">
              <div class="flex items-center gap-2 text-sm">
                <Icon name="lucide:copy" class="w-4 h-4 text-primary" />
                <span>{{ $t("howToUse.sharing.deckCodes.copy") }}</span>
              </div>
              <div class="flex items-center gap-2 text-sm">
                <Icon name="lucide:download" class="w-4 h-4 text-primary" />
                <span>{{ $t("howToUse.sharing.deckCodes.import") }}</span>
              </div>
            </div>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-xl font-semibold mb-3">
              {{ $t("howToUse.sharing.localStorage.title") }}
            </h3>
            <p class="text-muted-foreground mb-4">
              {{ $t("howToUse.sharing.localStorage.description") }}
            </p>
            <div class="bg-amber-50 border border-amber-200 p-3 rounded-md">
              <div class="flex items-start gap-2">
                <Icon
                  name="lucide:alert-triangle"
                  class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5"
                />
                <p class="text-amber-800 text-sm">
                  {{ $t("howToUse.sharing.localStorage.warning") }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Tips and Tricks -->
      <section id="tips" class="mb-12">
        <h2 class="text-2xl font-bold mb-6 flex items-center gap-2">
          <Icon name="lucide:lightbulb" class="w-6 h-6 text-primary" />
          {{ $t("howToUse.tips.title") }}
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-lg font-semibold mb-3 flex items-center gap-2">
              <Icon name="lucide:zap" class="w-5 h-5 text-yellow-500" />
              {{ $t("howToUse.tips.performance.title") }}
            </h3>
            <ul class="space-y-2 text-sm text-muted-foreground">
              <li>• {{ $t("howToUse.tips.performance.tip1") }}</li>
              <li>• {{ $t("howToUse.tips.performance.tip2") }}</li>
              <li>• {{ $t("howToUse.tips.performance.tip3") }}</li>
            </ul>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-lg font-semibold mb-3 flex items-center gap-2">
              <Icon name="lucide:keyboard" class="w-5 h-5 text-blue-500" />
              {{ $t("howToUse.tips.shortcuts.title") }}
            </h3>
            <ul class="space-y-2 text-sm text-muted-foreground">
              <li>• {{ $t("howToUse.tips.shortcuts.tip1") }}</li>
              <li>• {{ $t("howToUse.tips.shortcuts.tip2") }}</li>
              <li>• {{ $t("howToUse.tips.shortcuts.tip3") }}</li>
            </ul>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-lg font-semibold mb-3 flex items-center gap-2">
              <Icon name="lucide:smartphone" class="w-5 h-5 text-green-500" />
              {{ $t("howToUse.tips.mobile.title") }}
            </h3>
            <ul class="space-y-2 text-sm text-muted-foreground">
              <li>• {{ $t("howToUse.tips.mobile.tip1") }}</li>
              <li>• {{ $t("howToUse.tips.mobile.tip2") }}</li>
              <li>• {{ $t("howToUse.tips.mobile.tip3") }}</li>
            </ul>
          </div>

          <div class="bg-card p-6 rounded-lg border">
            <h3 class="text-lg font-semibold mb-3 flex items-center gap-2">
              <Icon name="lucide:help-circle" class="w-5 h-5 text-purple-500" />
              {{ $t("howToUse.tips.troubleshooting.title") }}
            </h3>
            <ul class="space-y-2 text-sm text-muted-foreground">
              <li>• {{ $t("howToUse.tips.troubleshooting.tip1") }}</li>
              <li>• {{ $t("howToUse.tips.troubleshooting.tip2") }}</li>
              <li>• {{ $t("howToUse.tips.troubleshooting.tip3") }}</li>
            </ul>
          </div>
        </div>
      </section>

      <!-- Footer -->
      <section class="text-center py-8">
        <div class="bg-muted/50 p-6 rounded-lg">
          <h3 class="text-xl font-semibold mb-2">
            {{ $t("howToUse.footer.title") }}
          </h3>
          <p class="text-muted-foreground mb-4">
            {{ $t("howToUse.footer.description") }}
          </p>
          <NuxtLink
            to="/"
            class="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Icon name="lucide:play" class="w-5 h-5" />
            {{ $t("howToUse.footer.startUsing") }}
          </NuxtLink>
        </div>
      </section>
    </main>
  </div>
</template>
