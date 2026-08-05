<script setup lang="ts">
/**
 * What this site is, who made it, and what it does with your data (ADR 0009 D27).
 *
 * **A page, not the dialog it replaces.** `AppInfoButton` rendered the same editorial copy
 * inside a `Dialog` opened from the overflow menu, which meant the site's only statement
 * about itself had no URL: nothing to link from a social profile, nothing to point an
 * external service at for a privacy policy, and nothing for Phase 7 to index. A dialog is
 * the right container for a passing glance and the wrong one for a document.
 *
 * **`/api/info` stays the source of the editorial paragraphs and the disclaimer** (D11) —
 * the Worker streaming `content/info.json` out of R2. Keeping it means the prose is still
 * editable by publishing an artifact rather than by shipping a build, and the Python
 * publish path and its smoke test keep the consumer they were written for. What is *new*
 * here — the lab, the maker links, the privacy section — is page-local, because it changes
 * when the code changes.
 *
 * **The card count comes from `/api/status`**, not from the prose. v1 embedded
 * "Our database has 2448 cards (June 19, 2026)" as editorial text, hand-updated and
 * therefore permanently wrong; `status.json` carries `counts.total` and `generated_at`,
 * written by the seeder against the database itself.
 *
 * Neither fetch is fatal. A missing artifact drops its own section and leaves the rest
 * standing — an unpublished `info.json` must not take out the privacy policy, which is the
 * one thing on this page that exists for legal reasons rather than editorial ones.
 */
import { ArrowLeft, Globe, Heart, Instagram, Mail } from "lucide-vue-next";

const { t, locale } = useI18n();
const localePath = useLocalePath();
const { siteUrl } = useRuntimeConfig().public;

useSeoMeta({
  title: t("about.title"),
  description: t("about.description"),
  ogTitle: t("about.title"),
  ogDescription: t("about.description"),
  ogType: "website",
  ogUrl: `${siteUrl}/${locale.value}/about`,
});

useHead({
  bodyAttrs: { class: "bg-background" },
  htmlAttrs: { lang: locale.value },
});

type InfoContent = {
  contents?: string[];
  disclaimer?: string;
};

type StatusSummary = { generated_at?: string; counts?: { total?: number } };

/**
 * Shares the `"info"` key with `AppHeaderOverflowMenu`, which needs the Discord invite from
 * the same artifact. `useAsyncData` resolves one request between them rather than two.
 *
 * Fetched eagerly here, unlike the dialog this replaces: a page the reader has navigated
 * to *is* the request for its contents, so there is nothing to defer.
 */
const { data: info } = await useAsyncData<InfoContent>(
  "info",
  () => $fetch<InfoContent>("/api/info"),
  { default: () => ({}) },
);

const { data: status } = await useAsyncData<StatusSummary>(
  "info-status",
  () => $fetch<StatusSummary>("/api/status"),
  { default: () => ({}) },
);

const contents = computed(() => info.value?.contents ?? []);
const disclaimer = computed(() => info.value?.disclaimer ?? "");

/** "2,463 · 2 Aug 2026" — the two facts, formatted for the reader's locale. */
const dataSummary = computed(() => {
  const total = status.value?.counts?.total;
  const generatedAt = status.value?.generated_at;
  if (!total) return "";

  const count = total.toLocaleString(locale.value);
  if (!generatedAt) return count;

  const date = new Date(generatedAt).toLocaleDateString(locale.value, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  return `${count} · ${date}`;
});

/**
 * The contact address, in one place.
 *
 * **Deliberately not in the locale files**, and the reason is worth keeping: `@` opens a
 * *linked message* in vue-i18n's syntax, so a literal address is a metacharacter. The
 * documented escape (`{'@'}`) compiles standalone but is rejected by `unplugin-vue-i18n`
 * — which is the path the build takes — with "Unterminated closing brace". That failure is
 * **not** scoped to the offending key: the locale module fails to compile as a whole, so
 * every one of the ~79 keys in that language renders as its own raw key path. One address
 * blanked the entire UI, in all seven languages.
 *
 * It is not translatable content in any case. The locale files carry the *label*.
 */
const CONTACT_EMAIL = "tskrlabs.info@lichingchester.dev";

/**
 * The maker's links (D27).
 *
 * Data rather than markup because they render identically and the list is the thing that
 * changes — an added channel should be one line here, not a fifth copy of the same anchor.
 *
 * `text` is what the reader sees where the address itself is the useful thing to show;
 * the rest use their translated label.
 */
const makerLinks = [
  {
    key: "website",
    href: "https://lichingchester.dev/",
    icon: Globe,
    text: "lichingchester.dev",
  },
  {
    key: "instagram",
    href: "https://www.instagram.com/lichingchester/",
    icon: Instagram,
    text: null,
  },
  {
    key: "email",
    href: `mailto:${CONTACT_EMAIL}`,
    icon: Mail,
    text: CONTACT_EMAIL,
  },
  { key: "kofi", href: "https://ko-fi.com/lichingchester", icon: Heart, text: null },
] as const;
</script>

<template>
  <!--
    Its own scroll region (#44). The shell is `h-dvh overflow-hidden`, so a page relying on
    the document scrolling gets clipped instead. Same construction as `/status`.
  -->
  <div class="h-full overflow-y-auto bg-background">
    <div class="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
      <div class="mx-auto flex max-w-3xl flex-wrap items-center gap-3 px-4 py-3">
        <Button variant="ghost" size="icon" as-child>
          <NuxtLink :to="localePath('/')">
            <ArrowLeft class="h-5 w-5" aria-hidden="true" />
            <span class="sr-only">{{ $t("Card List") }}</span>
          </NuxtLink>
        </Button>

        <h1 class="grow text-lg font-semibold">{{ $t("about.title") }}</h1>
      </div>
    </div>

    <div class="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-6">
      <!-- 1. What this site is. -->
      <section class="flex flex-col gap-3">
        <h2 class="text-sm font-semibold">{{ $t("about.theSite") }}</h2>

        <p class="text-sm leading-6 text-muted-foreground">
          {{ $t("about.description") }}
        </p>

        <!--
          The count, from the database rather than from prose (D11). Absent until
          `/api/status` resolves, because a card count that might be wrong is worse than
          none on the page that exists to be believed.
        -->
        <p v-if="dataSummary" class="text-xs tabular-nums text-muted-foreground">
          {{ $t("status.validInDB") }}: {{ dataSummary }}
        </p>

        <!--
          `v-html` because `info.json` carries anchors in its prose — the Discord invite and
          the link to the official card list. The artifact is ours, published from a
          committed file in this repo through `publish.py`, so this is our own markup rather
          than user input.
        -->
        <p
          v-for="(content, index) in contents"
          :key="index"
          class="text-sm leading-6 text-muted-foreground"
          v-html="content"
        />
      </section>

      <!-- 2. The lab it belongs to. -->
      <section class="flex flex-col gap-3">
        <h2 class="text-sm font-semibold">{{ $t("about.theLab") }}</h2>

        <p class="text-sm leading-6 text-muted-foreground">
          {{ $t("about.labBlurb") }}
        </p>

        <a
          href="https://tskrlabs.com/"
          target="_blank"
          rel="noopener"
          class="text-sm font-medium underline underline-offset-4"
        >
          tskrlabs.com
        </a>
      </section>

      <!-- 3. Who made it, and how to reach them. -->
      <section class="flex flex-col gap-3">
        <h2 class="text-sm font-semibold">{{ $t("about.madeBy") }}</h2>

        <p class="text-sm leading-6 text-muted-foreground">
          {{ $t("about.contactBlurb") }}
        </p>

        <ul class="flex flex-col gap-2">
          <li v-for="link in makerLinks" :key="link.key">
            <!--
              `mailto:` written plainly. Obfuscation is defeated by any scraper worth the
              name and costs copy-paste, assistive tech and "open in mail client" for the
              humans it inconveniences instead. The address is a purpose-specific alias, so
              the remedy for scraping is rotating it.

              `target` and `rel` only for the http(s) links — a `_blank` mailto opens a
              blank tab beside the mail client in several browsers.
            -->
            <a
              :href="link.href"
              :target="link.key === 'email' ? undefined : '_blank'"
              :rel="link.key === 'email' ? undefined : 'noopener'"
              class="inline-flex items-center gap-2 text-sm underline underline-offset-4"
            >
              <!-- Every entry carries an icon, so the labels align down a single edge. -->
              <component :is="link.icon" class="size-4 shrink-0" aria-hidden="true" />
              {{ link.text ?? $t(`about.links.${link.key}`) }}
            </a>
          </li>
        </ul>
      </section>

      <!-- 4. Legal: what happens to your data, and whose IP this is. -->
      <section class="flex flex-col gap-3">
        <h2 class="text-sm font-semibold">{{ $t("about.privacy") }}</h2>

        <!--
          **English, with a translated note saying so** (D27). The section labels above are
          translated because they are short and verifiable; this body is not, because it is
          a statement about data handling that nobody here can audit in five of the seven
          locales, and a mistranslated privacy policy is worse than an honest English one.

          This is also the status quo stated out loud: `info.json`'s disclaimer has always
          been English in all seven locales.
        -->
        <p
          v-if="locale !== 'en'"
          class="text-xs italic text-muted-foreground"
        >
          {{ $t("about.englishOnlyNote") }}
        </p>

        <!--
          Written against what the code actually does, and it is worth keeping it that way:
          `nuxt-gtag` with `G-LCSL88VF1N` (silent until `IS_PUBLIC`, `analytics_storage`
          granted and the `ad_*` types denied per ADR 0011 D1 as amended), typefaces
          self-hosted by `@nuxt/fonts` rather than fetched from Google, card images from the
          R2 CDN, and `localStorage` for decks, density and show-original. A policy
          describing a site other than this one is not a smaller problem than no policy.
        -->
        <div class="flex flex-col gap-3 text-sm leading-6 text-muted-foreground">
          <p>
            This site has no accounts and no sign-in, and asks you for nothing. There is no
            advertising here, and nothing collected is sold or shared with anyone.
          </p>

          <p>
            <strong class="font-medium text-foreground">Your decks stay in your browser.</strong>
            Decks, and your display preferences, are saved in this browser's local storage
            and are never sent to a server. Clearing your browser data deletes them, and
            they do not follow you to another device. A deck you choose to share is encoded
            into the link itself, so sharing that link is what publishes it, and nothing is
            stored on our side when you do.
          </p>

          <p>
            <strong class="font-medium text-foreground">Analytics.</strong>
            We use Google Analytics to count visits and see which pages get read, which is
            how we decide what to work on. <strong class="font-medium text-foreground">It
            sets a cookie and gives your browser a persistent identifier</strong>, so we can
            tell roughly how many people visit, whether a visit is a returning one, roughly
            from where, and on what kind of browser — never who you are, and we ask you for
            nothing. Advertising signals are switched off, so nothing here is used for ad
            targeting. You can block it with any content blocker, or with your browser's
            <a
              href="https://support.google.com/analytics/answer/181881"
              target="_blank"
              rel="noopener"
              class="underline underline-offset-4"
            >opt-out</a>, and everything on the site keeps working.
          </p>

          <p>
            <strong class="font-medium text-foreground">Things loaded from elsewhere.</strong>
            Typefaces are served from this site, not from Google — they are downloaded when
            the site is built, so your browser never asks Google for them. Card images come
            from our own CDN, which sees your IP address, as any web request does.
          </p>

          <p>
            Questions about any of this, or want something removed? Email
            <a
              href="mailto:tskrlabs.info@lichingchester.dev"
              class="underline underline-offset-4"
            >tskrlabs.info@lichingchester.dev</a>.
          </p>
        </div>
      </section>

      <!-- The disclaimer, from the artifact — the IP position, kept where it is edited. -->
      <section v-if="disclaimer" class="flex flex-col gap-3 border-t pt-6">
        <h2 class="text-sm font-semibold">{{ $t("about.disclaimer") }}</h2>
        <p class="text-sm leading-6 text-muted-foreground" v-html="disclaimer" />
      </section>
    </div>
  </div>
</template>
