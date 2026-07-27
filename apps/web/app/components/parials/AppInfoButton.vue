<script setup lang="ts">
import { Info } from "lucide-vue-next";

/**
 * The about dialog.
 *
 * **Editorial copy comes from `/api/info`** — the Worker streaming `content/info.json`
 * out of R2 (D11). v1 fetched it from
 * `raw.githubusercontent.com/…/main/public/info.json`, a live production dependency on a
 * git URL that breaks the moment a repo is renamed or made private. This repo is private
 * until launch, so v1's approach would already be broken here.
 *
 * **The card count comes from `/api/status`**, not from the prose. v1's `info.json`
 * embedded "Our database has 2448 cards (June 19, 2026)" as editorial text, hand-updated
 * and therefore permanently out of date. `status.json` carries `counts.total` and
 * `generated_at`, written by the seeder against the database itself.
 *
 * Both are fetched lazily — the dialog is click-to-open, so a closed dialog costs
 * nothing. Neither failure is fatal: the panel renders without whichever part is
 * missing, because an unpublished artifact must not take out the disclaimer.
 */

const { locale } = useI18n();

type InfoContent = {
  "discord-invite-url"?: string;
  contents?: string[];
  disclaimer?: string;
};

type StatusSummary = { generated_at?: string; counts?: { total?: number } };

const isOpen = ref(false);

const { data: info } = await useAsyncData<InfoContent>(
  "info",
  () => $fetch<InfoContent>("/api/info"),
  { immediate: false, default: () => ({}) },
);

const { data: status } = await useAsyncData<StatusSummary>(
  "info-status",
  () => $fetch<StatusSummary>("/api/status"),
  { immediate: false, default: () => ({}) },
);

// Fetch on first open, not at boot.
watch(isOpen, (open) => {
  if (!open) return;
  if (!info.value?.contents) refreshNuxtData("info");
  if (!status.value?.counts) refreshNuxtData("info-status");
});

const discordInviteUrl = computed(() => info.value?.["discord-invite-url"] ?? "");
const contents = computed(() => info.value?.contents ?? []);
const disclaimer = computed(() => info.value?.disclaimer ?? "");

/** "2,448 · 27 Jul 2026" — the two facts, formatted for the reader's locale. */
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
</script>

<template>
  <Dialog v-model:open="isOpen">
    <DialogTrigger as-child>
      <Button variant="ghost" size="icon">
        <Info />
      </Button>
    </DialogTrigger>
    <DialogScrollContent class="sm:max-w-[425px]">
      <DialogHeader class="text-start">
        <!--
          v1 rendered a shields.io release badge here from `info.json`'s
          `release-shields-url`. That key is absent from the v2 artifact: the repo is
          private until launch so the badge would 404 throughout, nothing here cuts
          releases, and it was a third-party request on every open.
        -->
        <DialogTitle>Hololive OCG Wiki</DialogTitle>
        <DialogDescription>
          <span v-if="dataSummary" class="text-xs tabular-nums">
            {{ $t("status.sourceTotal") }}: {{ dataSummary }}
          </span>

          <div class="flex gap-2 mt-2">
            <Button variant="outline" size="icon" as-child>
              <a href="https://github.com/tskrlabs/hololive-ocg-wiki" target="_blank">
                <IconGithub />
              </a>
            </Button>
            <Button v-if="discordInviteUrl" variant="outline" size="icon" as-child>
              <a :href="discordInviteUrl" target="_blank">
                <IconDiscord />
              </a>
            </Button>
          </div>

          <p
            class="leading-5 [&:not(:first-child)]:mt-4"
            v-for="(content, index) in contents"
            :key="index"
            v-html="content"
          />

          <hr class="[&:not(:first-child)]:mt-4" />

          <p class="leading-5 [&:not(:first-child)]:mt-4" v-html="disclaimer" />
        </DialogDescription>
      </DialogHeader>
    </DialogScrollContent>
  </Dialog>
</template>
