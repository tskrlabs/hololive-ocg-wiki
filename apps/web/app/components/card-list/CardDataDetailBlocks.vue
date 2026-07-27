<script setup lang="ts">
import type { Card } from "@/types/card";

const icon = useGameIcon();

defineProps<{
  item: Card;
}>();

const { t } = useI18n();

const getCostTypesString = (costTypes: string[]): string => {
  const counts: Record<string, number> = {};
  for (const type of costTypes) {
    counts[type] = (counts[type] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([type, count]) => `${t(`colors.${type}`)} x${count}`)
    .join(", ");
};
</script>

<template>
  <!-- oshiSkill -->
  <template v-if="item.oshi_skill">
    <div class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50">
      <div class="flex items-center justify-between gap-2">
        <span
          class="text-[#ED798D] bg-[#ED798D]/20 text-xs rounded-lg px-2 py-1"
        >
          {{ $t("fields.oshiSkill") }}
        </span>

        <div class="flex gap-2">
          <!-- timing -->
          <!-- <Badge
            v-if="item.oshi_skill.timing_code"
            variant="outline"
            class="text-xs font-semibold"
          >
            {{ item.oshi_skill.timing_code }}
          </Badge> -->

        </div>
      </div>

      <!-- name -->
      <div class="font-semibold">
        {{ item.oshi_skill.name }}
      </div>

      <!-- effect -->
      <div class="">
        {{ item.oshi_skill.effect }}
      </div>
    </div>
  </template>

  <!-- spOshiSkill -->
  <template v-if="item.sp_oshi_skill">
    <div class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50">
      <div class="flex items-center justify-between gap-2">
        <span
          class="text-[#ED798D] bg-[#ED798D]/20 text-xs rounded-lg px-2 py-1"
        >
          {{ $t("fields.spOshiSkill") }}
        </span>

        <div class="flex gap-2">
          <!-- timing -->
          <!-- <Badge
            v-if="item.sp_oshi_skill.timing_code"
            variant="outline"
            class="text-xs"
          >
            {{ item.sp_oshi_skill.timing_code }}
          </Badge> -->

        </div>
      </div>

      <!-- name -->
      <div class="font-semibold">
        {{ item.sp_oshi_skill.name }}
      </div>

      <!-- effect -->
      <div class="">
        {{ item.sp_oshi_skill.effect }}
      </div>
    </div>
  </template>

  <!-- keyword -->
  <template v-if="item.keyword">
    <div class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50">
      <div class="flex items-center justify-between gap-2">
        <template v-if="item.keyword.type_code === 'collab_effect'">
          <span class="text-red-500 bg-red-500/20 text-xs rounded-lg px-2 py-1">
            {{ $t(`keywordType.${item.keyword.type_code}`) }}
          </span>
        </template>
        <template v-if="item.keyword.type_code === 'bloom_effect'">
          <span class="text-sky-600 bg-sky-600/20 text-xs rounded-lg px-2 py-1">
            {{ $t(`keywordType.${item.keyword.type_code}`) }}
          </span>
        </template>
        <template v-if="item.keyword.type_code === 'gift'">
          <span
            class="text-lime-600 bg-lime-600/20 text-xs rounded-lg px-2 py-1"
          >
            {{ $t(`keywordType.${item.keyword.type_code}`) }}
          </span>
        </template>

        <div class="flex gap-2">
          <Image
            v-if="item.keyword.type_code === 'collab_effect'"
            :src="icon.keyword('collab_effect')"
            :img-attributes="{ class: 'w-28' }"
          />
          <Image
            v-if="item.keyword.type_code === 'bloom_effect'"
            :src="icon.keyword('bloom_effect')"
            :img-attributes="{ class: 'w-28' }"
          />
          <Image
            v-if="item.keyword.type_code === 'gift'"
            :src="icon.keyword('gift')"
            :img-attributes="{ class: 'w-14' }"
          />
        </div>
      </div>

      <!-- name -->
      <div class="font-semibold">
        {{ item.keyword.name }}
      </div>

      <!-- effect -->
      <div class="">
        {{ item.keyword.effect }}
      </div>
    </div>
  </template>

  <!-- arts -->
  <template v-if="item.arts?.length">
    <template v-for="(art, index) in item.arts" :key="index">
      <div class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50">
        <div class="flex items-center justify-between gap-2">
          <!-- <span
            class="text-violet-500 bg-violet-500/20 text-xs rounded-lg px-2 py-1"
          >
            {{ $t("fields.arts") }}
          </span> -->

          <!-- cost -->
          <template v-if="art.cost_types">
            <div class="flex items-center flex-wrap">
              <template
                v-for="(costType, costTypeIndex) in art.cost_types"
                :key="costTypeIndex"
              >
                <Image
                  :class="
                    costTypeIndex === art.cost_types.length - 1 ? 'mr-1' : ''
                  "
                  :src="icon.artCost(costType)"
                  :img-attributes="{ class: 'size-6 min-w-6 min-h-6' }"
                />
              </template>

              <span class=""> ({{ getCostTypesString(art.cost_types) }}) </span>
            </div>
          </template>

          <div class="flex flex-wrap gap-1 justify-end">
            <!-- damage -->
            <Badge variant="outline" class="text-xs">
              {{ $t("fields.damage") }}:
              {{ `${art.damage}${art.is_plus ? "+" : ""}` }}
            </Badge>

            <!-- specialTargets -->
            <template v-if="art.special_targets">
              <template
                v-for="(
                  specialTarget, specialTargetIndex
                ) in art.special_targets"
                :key="specialTargetIndex"
              >
                <Badge variant="outline" class="text-xs">
                  <div class="flex items-center">
                    <Image
                      :src="icon.specialTarget(specialTarget)"
                      :img-attributes="{ class: 'w-12 min-w-8' }"
                    />

                    <span class="ml-1">
                      {{ $t("fields.tokkouColor") }}:
                      {{ $t(`colors.${specialTarget}`) }}
                    </span>
                  </div>
                </Badge>
              </template>
            </template>
          </div>
        </div>

        <!-- name -->
        <div class="font-semibold">
          {{ art.name }}
        </div>

        <!-- effect -->
        <div v-if="art.effect">
          {{ art.effect }}
        </div>
      </div>
    </template>
  </template>

  <!-- extra -->
  <template v-if="item.extra">
    <div class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50">
      <div class="flex items-center justify-between gap-2">
        <span
          class="text-amber-500 bg-amber-500/20 text-xs rounded-lg px-2 py-1"
        >
          {{ $t("fields.extra") }}
        </span>
      </div>

      {{ item.extra }}
    </div>
  </template>

  <!-- abilityText -->
  <template v-if="item.ability_text">
    <div class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50">
      <div class="flex items-center justify-between gap-2">
        <span
          class="text-stone-800 bg-stone-800/20 dark:text-white dark:bg-white/10 text-xs rounded-lg px-2 py-1"
        >
          {{ $t("fields.ability") }}
        </span>
      </div>

      <div v-html="item.ability_text.replaceAll('\n', '<br>')" />
      <!-- <div
        v-html="$t(`cards.${item.id}.abilityText`).replaceAll('\n', '<br>')"
      /> -->
    </div>
  </template>

  <!-- illustrator -->
  <template v-if="item.illustrator">
    <div class="flex flex-col gap-2 p-2 rounded-lg border bg-accent/50">
      <div class="flex items-center justify-between gap-2">
        <Badge variant="outline" class="text-xs">
          {{ $t(`fields.illustrator`) }}
        </Badge>

        <div class="text-xs">
          {{ item.illustrator }}
        </div>
      </div>
    </div>
  </template>
</template>
