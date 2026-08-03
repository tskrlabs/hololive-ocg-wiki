<script setup lang="ts">
/**
 * What changed, and when.
 *
 * **A page with a URL, for the same reason `/about` is one (ADR 0009 D27).** A release is
 * the thing you link to — from the Discord, from an issue reply saying "this is fixed in
 * 2.0" — and a dialog or a toast cannot be linked to. It is also the surface that tells a
 * returning reader why the site looks different, which is the question a rebuild creates
 * and nothing else on the site answers.
 *
 * **The entries are imported, not fetched** (`content/changelog.json`, via the `#content`
 * alias). `info.json` is fetched from R2 because editorial prose about the project can
 * meaningfully be corrected between deploys; a release note describes what a particular
 * build changed, so decoupling it from the build only creates the state where the page
 * claims a feature the running code does not have. Importing also means there is no
 * loading state, no error state, and no empty page when a request fails — under
 * `ssr: false` the markup is in the bundle.
 *
 * **The entries are English only, and the page says so**, exactly like the privacy section
 * on `/about`. `contract.test.ts` sweeps every UI key across all seven locales, so a
 * translated changelog would be seven files edited per release — a tax on writing one at
 * all. The chrome (title, back, headings, the note itself) *is* translated, because that
 * is the part a reader needs to navigate rather than to read.
 */
import { ArrowLeft } from "lucide-vue-next";

import changelog from "#content/changelog.json";

const { t, locale } = useI18n();
const localePath = useLocalePath();
const { siteUrl } = useRuntimeConfig().public;

useSeoMeta({
  title: t("changelog.title"),
  description: t("changelog.description"),
  ogTitle: t("changelog.title"),
  ogDescription: t("changelog.description"),
  ogType: "website",
  ogUrl: `${siteUrl}/${locale.value}/changelog`,
});

useHead({
  bodyAttrs: { class: "bg-background" },
  htmlAttrs: { lang: locale.value },
});

type ChangeKind = "added" | "changed" | "fixed";

interface Change {
  kind: ChangeKind;
  text: string;
}

/**
 * No `known` field, deliberately.
 *
 * Open gaps are stated in the GitHub release body (`docs/releases/`), which is read by
 * people deciding whether to contribute — the audience a caveat is useful to. On the
 * player-facing page it read as a list of reasons not to trust the thing they are already
 * using, next to the entry saying it was fixed.
 *
 * The field is absent from the type rather than merely unrendered: an optional key nothing
 * reads is one a future release fills in and silently loses.
 */
interface Release {
  version: string;
  date: string;
  title: string;
  summary: string;
  changes: Change[];
}

/**
 * Newest first — the order in the file, not a sort.
 *
 * Sorting would need a comparator over a version string, which is a small parser with its
 * own bugs, to re-derive an order the author already knows. The file is the running order;
 * `content/README.md` says so.
 */
const releases = changelog.releases as Release[];

/**
 * The badge for each kind.
 *
 * Colour is *not* the only carrier — the label is a word ("Fixed"), so this stays legible
 * to a reader who cannot distinguish the hues, which is the rule D4 sets for the rest of
 * the site. Translated, because three words is a real translation and the entries are not.
 */
const KIND_CLASS: Record<ChangeKind, string> = {
  added: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  changed: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  fixed: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
};

/** "3 Aug 2026", in the reader's locale — a date is a fact, not prose. */
function formatDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(locale.value, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
</script>

<template>
  <!--
    Its own scroll region (#44). The shell is `h-dvh overflow-hidden`, so a page relying on
    the document scrolling gets clipped instead. Same construction as `/about` and `/status`.
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

        <h1 class="grow text-lg font-semibold">{{ $t("changelog.title") }}</h1>
      </div>
    </div>

    <div class="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-6">
      <!--
        The English-only note, in the reader's language. Stated once at the top rather than
        per release: it is a property of the page, and repeating it down a growing list
        would be louder than the content it qualifies.
      -->
      <p v-if="locale !== 'en'" class="text-xs italic text-muted-foreground">
        {{ $t("about.englishOnlyNote") }}
      </p>

      <section v-for="release in releases" :key="release.version" class="flex flex-col gap-4">
        <div class="flex flex-col gap-1">
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 class="text-base font-semibold">v{{ release.version }}</h2>
            <time
              :datetime="release.date"
              class="text-xs tabular-nums text-muted-foreground"
            >
              {{ formatDate(release.date) }}
            </time>
          </div>

          <p class="text-sm font-medium">{{ release.title }}</p>
        </div>

        <p class="text-sm leading-6 text-muted-foreground">{{ release.summary }}</p>

        <ul class="flex flex-col gap-5">
          <!--
            **Badge above the text, not beside it.** Side by side, the three labels are
            three different widths, so every entry's text started at a different x — and
            in seven languages there is no width to align to, since the labels translate
            to anything from "New" to "เปลี่ยนแปลง". Stacking gives every entry the same
            left edge for free, in every locale, and hands the full column width to the
            sentence that has to be read.

            `self-start` is load-bearing: a flex column stretches its children, so without
            it the badge becomes a full-width bar rather than a tag.
          -->
          <li v-for="(change, index) in release.changes" :key="index" class="flex flex-col gap-1.5">
            <!-- The label is a word, not only a colour (D4). -->
            <span
              class="self-start rounded px-1.5 py-0.5 text-[11px] font-medium"
              :class="KIND_CLASS[change.kind]"
            >
              {{ $t(`changelog.kind.${change.kind}`) }}
            </span>
            <span class="text-sm leading-6 text-muted-foreground">{{ change.text }}</span>
          </li>
        </ul>
      </section>

      <p class="border-t pt-6 text-sm text-muted-foreground">
        {{ $t("changelog.fullHistory") }}
        <a
          href="https://github.com/tskrlabs/hololive-ocg-wiki/releases"
          target="_blank"
          rel="noopener"
          class="underline underline-offset-4"
        >
          GitHub
        </a>
      </p>
    </div>
  </div>
</template>
