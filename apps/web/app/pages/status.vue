<script setup lang="ts">
/**
 * What the database holds, and when it was last seeded (ADR 0009 D19).
 *
 * **The tabs are gone, and the data is why.** The page offered New / Updated tabs over
 * per-card lists, in two view modes, with a sort control and pagination — 580 lines
 * across four files. Production reports `changed: 2463, new: 0`: a full reseed marks
 * every card changed, so one tab held all 2,463 entries and the other held none. Neither
 * number tells a reader anything the total does not, and paginating 2,463 rows of "this
 * card was re-seeded" is work spent on a list nobody can act on.
 *
 * What a reader actually comes here for is whether the data is current, which is two
 * numbers. Those stay.
 *
 * `writes` is deliberately still not rendered — it is seeder telemetry (rows written,
 * batches, database size) answering "did the run behave" for the maintainer, not "what
 * changed" for a reader. See `~/types/status`.
 *
 * This page is reachable from the header's overflow menu (D21), which is what finally
 * makes it reachable **on mobile** — its header button was `hidden sm:inline-flex`.
 */
import { ArrowLeft } from "lucide-vue-next";
import type { StatusReport } from "~/types/status";

const { t, locale } = useI18n();

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
