<script setup lang="ts">
/**
 * What the database holds, when it was last seeded, and what the official card list did
 * (ADR 0009 D19, extended by D26).
 *
 * **The tabs are gone, and the data is why.** The page offered New / Updated tabs over
 * per-card lists, in two view modes, with a sort control and pagination — 580 lines
 * across four files. Production reports `changed: 2463, new: 0`: a full reseed marks
 * every card changed, so one tab held all 2,463 entries and the other held none.
 *
 * **D26 found the deeper problem: `changed` was measuring the wrong thing.** It covers
 * the translated payload, so the translation rework marked all 2,463 cards changed while
 * the official site published nothing at all. The number was real and the story it told
 * was false. `source_changed` measures the JP source alone, so this page can now lead
 * with what the *game* did and keep the re-seed number as the footnote it always was.
 *
 * Two vocabularies, and the layout keeps them apart on purpose. The tiles are freshness —
 * how much data, how recent. The update section below is the source diff. `changed` never
 * appears as a headline number; it appears inside a sentence explaining itself.
 *
 * `writes` is deliberately still not rendered — it is seeder telemetry (rows written,
 * batches, database size) answering "did the run behave" for the maintainer, not "what
 * changed" for a reader. See `~/types/status`.
 *
 * This page is reachable from the header's overflow menu (D21), which is what finally
 * makes it reachable **on mobile** — its header button was `hidden sm:inline-flex`.
 */
import { ArrowLeft } from "lucide-vue-next";
import type { StatusEntry, StatusReport } from "~/types/status";

const { t, locale } = useI18n();
const localePath = useLocalePath();

useSeoMeta({
  title: t("status.title"),
  description: t("status.description"),
});

useHead({
  bodyAttrs: { class: "bg-background" },
  htmlAttrs: { lang: locale.value },
});

/**
 * From `/api/status` — the Worker streaming the seeder's own report out of R2 (D11).
 *
 * v1 read a `public/status.json` committed into the repo, so it was always as stale as
 * the last deploy and had to be hand-copied after every pipeline run.
 */
const { data: status, error } = await useAsyncData<StatusReport>("status", () =>
  $fetch<StatusReport>("/api/status"),
);

/** When the seeder ran — the answer to "is this current?". */
const seededAt = computed(() => formatTimestamp(status.value?.generated_at));

/**
 * When the `cards.json` behind it was built.
 *
 * A separate fact from the seed, and occasionally a surprising one: a re-run of `seed`
 * against an unchanged build moves this not at all while the row above moves. That gap
 * is exactly what someone checking freshness needs to see.
 */
const builtAt = computed(() => formatTimestamp(status.value?.built_at));

function formatTimestamp(value?: string): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(locale.value, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * The three source-side groups, in the order a reader cares about them.
 *
 * `count` comes from `counts` and `cards` from the capped list, so a group can honestly
 * say "12 cards" while showing 12 of them and "600 cards" while showing 100. Reading the
 * total off `cards.length` is the bug the cap would otherwise introduce.
 *
 * Absent fields (an artifact written before D26) yield 0 and an empty list, which renders
 * as `hasSourceNews === false` — the same as a quiet update, and the honest answer when
 * the report simply cannot say.
 */
const sourceGroups = computed(() => {
  const counts = status.value?.counts;
  const report = status.value;
  return [
    {
      key: "added",
      label: t("status.source.added"),
      count: counts?.source_added ?? 0,
      cards: report?.source_added ?? [],
    },
    {
      key: "edited",
      label: t("status.source.edited"),
      count: counts?.source_changed ?? 0,
      cards: report?.source_changed ?? [],
    },
    {
      key: "faq",
      label: t("status.source.faq"),
      count: counts?.faq_changed ?? 0,
      cards: report?.faq_changed ?? [],
    },
  ].filter((group) => group.count > 0);
});

/** Whether the official card list did anything at all in the run being reported. */
const hasSourceNews = computed(() => sourceGroups.value.length > 0);

/**
 * The sentence explaining the re-seed, chosen from the shape of the data (D26).
 *
 * Derived rather than authored because the seeder cannot know *why* a run rewrote every
 * row — a re-translation, a schema fix and a plain re-run look identical from there. A
 * hand-written note would be v1's bug in new clothes: its `info.json` embedded "Our
 * database has 2448 cards (June 19, 2026)" in prose, wrong the day after it was written.
 *
 * The interesting case is the first: rows churned, source silent. That is precisely the
 * translation rework, and saying so turns a number that looks alarming into one that
 * explains itself.
 */
const reseedNote = computed(() => {
  const counts = status.value?.counts;
  if (!counts) return "";

  const rewritten = counts.changed + counts.new;
  if (rewritten === 0) return t("status.reseed.none");
  if (!hasSourceNews.value) {
    return t("status.reseed.ours", { count: rewritten.toLocaleString(locale.value) });
  }
  return t("status.reseed.mixed", { count: rewritten.toLocaleString(locale.value) });
});

/** How many of a group's cards are not shown, so the list can say "and N more". */
function hiddenCount(group: { count: number; cards: StatusEntry[] }): number {
  return Math.max(0, group.count - group.cards.length);
}

/**
 * A card's page URL, from its `image_key` — which *is* the URL's `{set}/{stem}` (D6).
 *
 * A row with no key is rendered as plain text rather than a dead link: the entry survives
 * in the artifact even when the card is gone from the build, and a link to nothing is
 * worse than no link.
 */
function cardPath(entry: StatusEntry): string | null {
  return entry.image_key ? localePath(`/card/${entry.image_key}`) : null;
}

/** What to call a card whose name never made it into the artifact. */
function cardLabel(entry: StatusEntry): string {
  return entry.name || entry.card_number || entry.id;
}
</script>

<template>
  <!--
    Its own scroll region (#44). The shell is `h-dvh overflow-hidden`, so a page relying
    on the document scrolling gets clipped instead.
  -->
  <div class="h-full overflow-y-auto bg-background">
    <div class="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
      <div class="mx-auto flex max-w-3xl flex-wrap items-center gap-3 px-4 py-3">
        <Button variant="ghost" size="icon" as-child>
          <NuxtLink to="/">
            <ArrowLeft class="h-5 w-5" aria-hidden="true" />
            <span class="sr-only">{{ $t("Card List") }}</span>
          </NuxtLink>
        </Button>

        <h1 class="grow text-lg font-semibold">{{ $t("status.title") }}</h1>
      </div>
    </div>

    <div class="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
      <!--
        Three tiles, not two. v1 showed "Source Total" beside "In Database", a split that
        existed because its pipeline could skip cards that failed validation — v2 seeds
        only what `build` validated, so those were one number. The room that frees goes to
        the build date, which answers a question the seed date alone cannot.

        The count was `text-green-600 dark:text-green-400`. D4 leaves no accent hue, and a
        number is not a state: green here said nothing except "this is the good one".
      -->
      <div v-if="status" class="grid gap-3 sm:grid-cols-3">
        <div class="flex flex-col gap-1 rounded-lg border bg-card p-4">
          <span class="text-xs text-muted-foreground">{{ $t("status.validInDB") }}</span>
          <span class="font-mono text-2xl font-semibold">
            {{ status.counts.total.toLocaleString(locale) }}
          </span>
        </div>

        <div class="flex flex-col gap-1 rounded-lg border bg-card p-4">
          <span class="text-xs text-muted-foreground">{{ $t("status.lastUpdated") }}</span>
          <span class="text-sm font-medium">{{ seededAt }}</span>
        </div>

        <div class="flex flex-col gap-1 rounded-lg border bg-card p-4">
          <span class="text-xs text-muted-foreground">{{ $t("status.builtAt") }}</span>
          <span class="text-sm font-medium">{{ builtAt }}</span>
        </div>
      </div>

      <!--
        The latest update, from the source's point of view (D26).

        Headed "in the latest update" and not "recent changes", because `status.json` is
        overwritten every seed — there is exactly one run's worth of history here, and the
        heading is the only thing stopping a reader from reading it as a changelog.

        No badges and no colour. D19 deleted four hardcoded greens on the grounds that a
        number is not a state; "added" and "edited" are categories, not severities, and a
        green "added" beside an amber "edited" would invent a hierarchy the data does not
        have. The label carries the meaning.
      -->
      <section v-if="status" class="flex flex-col gap-4">
        <h2 class="text-sm font-semibold">{{ $t("status.source.heading") }}</h2>

        <div v-if="hasSourceNews" class="flex flex-col gap-4">
          <div
            v-for="group in sourceGroups"
            :key="group.key"
            class="flex flex-col gap-2 rounded-lg border bg-card p-4"
          >
            <div class="flex items-baseline gap-2">
              <span class="font-mono text-lg font-semibold">
                {{ group.count.toLocaleString(locale) }}
              </span>
              <span class="text-sm text-muted-foreground">{{ group.label }}</span>
            </div>

            <!--
              A flat list of links, not a table and not a grid. Every row is a card the
              reader can open, which is the entire reason D19's objection does not apply
              here: this list is 0-100 specific cards, not 2,463 rows of "re-seeded".
            -->
            <ul class="flex flex-wrap gap-x-3 gap-y-1 text-sm">
              <li v-for="entry in group.cards" :key="entry.id">
                <NuxtLink
                  v-if="cardPath(entry)"
                  :to="cardPath(entry)!"
                  class="underline-offset-4 hover:underline"
                >
                  {{ cardLabel(entry) }}
                  <span v-if="entry.card_number" class="text-muted-foreground">
                    {{ entry.card_number }}
                  </span>
                </NuxtLink>
                <span v-else class="text-muted-foreground">{{ cardLabel(entry) }}</span>
              </li>
            </ul>

            <!--
              The cap, stated rather than hidden. A list that silently stopped at 100 would
              read as "these are all of them", which is the failure mode a truncation
              should never have.
            -->
            <p v-if="hiddenCount(group)" class="text-xs text-muted-foreground">
              {{ $t("status.source.more", { count: hiddenCount(group).toLocaleString(locale) }) }}
            </p>
          </div>
        </div>

        <p v-else class="text-sm text-muted-foreground">
          {{ $t("status.source.quiet") }}
        </p>

        <!--
          The re-seed footnote — the 2,463, told rather than hidden.

          Below the source section on purpose. It is the answer to "why does it say the
          data changed when no cards did", which is a question a reader only has *after*
          reading the section above.
        -->
        <p v-if="reseedNote" class="text-sm text-muted-foreground">{{ reseedNote }}</p>
      </section>

      <p v-if="status" class="text-sm text-muted-foreground">
        {{ $t("status.summary") }}
      </p>

      <!--
        Retryable, and never red — D4 reserves `--destructive` for destructive actions,
        and #38 §5 for the shape: an artifact that has not been published yet is not the
        reader's fault and not permanent.
      -->
      <div
        v-else-if="error"
        class="flex flex-col items-center justify-center py-16 text-center"
      >
        <p class="text-lg font-medium">{{ $t("errors.status.title") }}</p>
        <p class="mt-1 text-sm text-muted-foreground">{{ $t("errors.status.detail") }}</p>
        <Button variant="outline" size="sm" class="mt-4" as-child>
          <NuxtLink to="/">{{ $t("Card List") }}</NuxtLink>
        </Button>
      </div>

      <div v-else class="flex flex-col gap-3 sm:flex-row">
        <div v-for="n in 3" :key="n" class="h-20 grow animate-pulse rounded-lg bg-muted"></div>
      </div>
    </div>
  </div>
</template>
