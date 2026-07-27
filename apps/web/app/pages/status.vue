<script setup lang="ts">
import { ArrowLeft, List, Table2 } from "lucide-vue-next";
import type { StatusEntry, StatusReport, StatusTab } from "~/types/status";

const { t, locale } = useI18n();

useSeoMeta({
  title: t("status.title"),
  description: t("status.description"),
});

useHead({
  bodyAttrs: { class: "bg-background" },
  htmlAttrs: { lang: locale.value },
});

// ── Data ──────────────────────────────────────────────────────────────────
//
// From `/api/status` — the Worker streaming the seeder's own report out of R2 (D11). v1
// read a `public/status.json` committed into the repo, so it was always as stale as the
// last deploy and had to be hand-copied after every pipeline run.
//
// The shape changed with the writer: `holo-data seed` describes a *database* diff, where
// v1's `migrate.js` described a source-to-source one. See `~/types/status` for the full
// mapping; the visible consequences here are snake_case fields, `counts.total` in place
// of `source.total`/`source.valid`, and no Skipped tab.
const { data: status } = await useAsyncData<StatusReport>("status", () =>
  $fetch<StatusReport>("/api/status"),
);

// ── View mode & sort ──────────────────────────────────────────────────────
type ViewMode = "list" | "table";
type SortMode = "cardNumber" | "name";

const viewMode = ref<ViewMode>("table");
const sortMode = ref<SortMode>("cardNumber");
const activeTab = ref<StatusTab>("new");

const tabs: StatusTab[] = ["new", "changed"];

// ── Pagination ────────────────────────────────────────────────────────────
const PAGE_SIZE = 100;
const visibleCount = ref(PAGE_SIZE);

watch([activeTab, sortMode], () => {
  visibleCount.value = PAGE_SIZE;
});

function naturalSort(a: StatusEntry, b: StatusEntry, mode: SortMode): number {
  if (mode === "name") {
    const nameA = a.name || a.card_number || a.id;
    const nameB = b.name || b.card_number || b.id;
    return nameA.localeCompare(nameB);
  }
  // Card number natural sort: hBPXX-YYY
  const numA = a.card_number || `~${a.id}`; // push null to end
  const numB = b.card_number || `~${b.id}`;
  return numA.localeCompare(numB, undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function sorted(items: StatusEntry[]): StatusEntry[] {
  return [...items].sort((a, b) => naturalSort(a, b, sortMode.value));
}

// Full sorted lists per tab
const allTabItems = computed<Record<StatusTab, StatusEntry[]>>(() => {
  if (!status.value) return { new: [], changed: [] };
  return {
    new: sorted(status.value.new),
    // "Updated" folds together the three ways an existing card can change. v1 also
    // appended `skipped[]`, which v2 does not produce.
    changed: sorted([
      ...status.value.changed,
      ...status.value.qa_updated,
      ...status.value.removed,
    ]),
  };
});

// Sliced to visible window — prevents mounting thousands of rows at once
const tabItems = computed<Record<StatusTab, StatusEntry[]>>(() => {
  const all = allTabItems.value;
  return {
    new: all.new.slice(0, visibleCount.value),
    changed: all.changed.slice(0, visibleCount.value),
  };
});

function tabCount(key: StatusTab): number {
  return allTabItems.value[key]?.length ?? 0;
}

const activeTotal = computed(() => tabCount(activeTab.value));
const hasMore = computed(() => visibleCount.value < activeTotal.value);

function loadMore() {
  visibleCount.value += PAGE_SIZE;
}

const formattedDate = computed(() => {
  if (!status.value?.generated_at) return "—";
  return new Date(status.value.generated_at).toLocaleDateString(locale.value, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
});

const viewIcons = { list: List, table: Table2 };
</script>

<template>
  <div class="min-h-svh bg-background">
    <!-- Top bar -->
    <div class="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
      <div
        class="mx-auto max-w-7xl px-4 py-3 flex items-center gap-3 flex-wrap"
      >
        <!-- Back -->
        <Button variant="ghost" size="icon" as-child>
          <NuxtLink to="/">
            <ArrowLeft class="w-5 h-5" />
          </NuxtLink>
        </Button>

        <h1 class="text-lg font-semibold grow">{{ $t("status.title") }}</h1>

        <!-- Sort -->
        <div class="flex items-center gap-2">
          <span class="text-sm text-muted-foreground hidden sm:inline">{{
            $t("status.sort.label")
          }}</span>
          <select
            v-model="sortMode"
            class="text-sm rounded-md border bg-background px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="cardNumber">
              {{ $t("status.sort.cardNumber") }}
            </option>
            <option value="name">{{ $t("status.sort.name") }}</option>
          </select>
        </div>

        <!-- View mode toggle -->
        <div class="flex rounded-md border">
          <button
            v-for="(Icon, key) in viewIcons"
            :key="key"
            class="p-1.5 transition-colors"
            :class="
              viewMode === key
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted'
            "
            :title="$t(`status.views.${key}`)"
            @click="viewMode = key as ViewMode"
          >
            <component :is="Icon" class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <div class="mx-auto max-w-7xl px-4 py-6 flex flex-col gap-6">
      <!--
        Stats bar. Two tiles, not three: v1 showed "Source Total" beside "In Database",
        a split that existed because its pipeline could skip cards that failed
        validation. v2 seeds only what `build` validated, so the two numbers are the
        same one — `counts.total`.
      -->
      <div v-if="status" class="grid grid-cols-2 gap-3">
        <div class="rounded-lg border bg-card p-4 flex flex-col gap-1">
          <span class="text-xs text-muted-foreground">{{
            $t("status.validInDB")
          }}</span>
          <span
            class="text-2xl font-bold text-green-600 dark:text-green-400 tabular-nums"
            >{{ status.counts.total.toLocaleString() }}</span
          >
        </div>
        <div class="rounded-lg border bg-card p-4 flex flex-col gap-1">
          <span class="text-xs text-muted-foreground">{{
            $t("status.lastUpdated")
          }}</span>
          <span class="text-sm font-medium">{{ formattedDate }}</span>
        </div>
      </div>

      <!-- Full-mode note -->
      <div
        v-if="status?.mode === 'full'"
        class="rounded-lg bg-muted px-4 py-3 text-sm text-muted-foreground"
      >
        {{ $t("status.fullModeNote") }}
      </div>

      <!-- Tabs -->
      <div v-if="status">
        <!-- Tab headers -->
        <div class="flex gap-1 border-b flex-wrap">
          <button
            v-for="tab in tabs"
            :key="tab"
            class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
            :class="
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            "
            @click="activeTab = tab"
          >
            {{ $t(`status.tabs.${tab}`) }}
            <span class="ml-1 text-xs tabular-nums">({{ tabCount(tab) }})</span>
          </button>
        </div>

        <!-- Tab content -->
        <div class="mt-4">
          <!-- Empty state -->
          <p
            v-if="tabCount(activeTab) === 0"
            class="text-muted-foreground text-sm py-8 text-center"
          >
            {{ $t("status.noChanges") }}
          </p>

          <!-- List view -->
          <StatusCardList
            v-else-if="viewMode === 'list'"
            :items="tabItems[activeTab]"
            :status="activeTab"
          />

          <!-- Table view -->
          <StatusCardTable
            v-else
            :items="tabItems[activeTab]"
            :status="activeTab"
          />

          <!-- Load more -->
          <div v-if="hasMore" class="mt-6 flex flex-col items-center gap-1">
            <Button variant="outline" @click="loadMore">
              {{
                $t("status.loadMore", {
                  loaded: tabItems[activeTab].length,
                  total: activeTotal,
                })
              }}
            </Button>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div
        v-else
        class="flex items-center justify-center h-64 text-muted-foreground"
      >
        {{ $t("Loading") }}
      </div>
    </div>
  </div>
</template>
