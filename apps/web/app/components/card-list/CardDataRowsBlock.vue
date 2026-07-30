<script setup lang="ts">
import { UseClipboard } from "@vueuse/components";
import type { Card } from "@/types/card";

defineProps<{
  item: Card;
}>();

// Use translation composable
const { getTranslatedText } = useTranslation();

const icon = useGameIcon();
</script>

<template>
  <div class="">
    <div class="border divide-y rounded-lg [&>*:nth-of-type(odd)]:bg-accent/50">
      <!-- cardTypeCode -->
      <CardDataRowsBlockItem
        v-if="item.card_type_code"
        :name="$t('fields.cardType')"
      >
        {{ $t(`cardTypes.${item.card_type_code}`) }}
      </CardDataRowsBlockItem>

      <!-- tags -->
      <CardDataRowsBlockItem
        v-if="item?.tags?.length"
        :name="$t('fields.tags')"
      >
        <div class="flex flex-wrap gap-1">
          <template v-for="(tag, index) in item.tags" :key="index">
            <UseClipboard v-slot="{ copy, copied }" :source="tag">
              <div class="relative">
                <Button variant="link" class="p-0 h-auto" @click="copy()">
                  {{ getTranslatedText("tags", tag, tag) }}
                </Button>
                <!-- Copied indicator -->
                <Transition name="copied">
                  <span
                    v-if="copied"
                    class="absolute bottom-full md:top-auto md:bottom-[calc(100%+0rem)] left-2/4 -translate-x-2/4 -translate-y-1 rounded-lg bg-green-400 text-slate-800 text-xs py-1 px-2 whitespace-nowrap z-10"
                  >
                    {{ $t("Copied") }}
                  </span>
                </Transition>
              </div>
            </UseClipboard>
          </template>
        </div>
      </CardDataRowsBlockItem>

      <!-- rarityCode -->
      <CardDataRowsBlockItem
        v-if="item.rarity_code"
        :name="$t('fields.rarity')"
      >
        {{ item.rarity_code }}
      </CardDataRowsBlockItem>

      <!-- set -->
      <CardDataRowsBlockItem
        v-if="item?.card_sets && item?.card_sets.length > 0"
        :name="$t('fields.set')"
      >
        <div class="flex flex-wrap justify-end gap-2">
          <Badge
            variant="outline"
            v-for="set in item.card_sets"
            :key="set"
            class="text-wrap whitespace-normal"
          >
            {{ getTranslatedText("sets", set, set) }}
          </Badge>
        </div>
      </CardDataRowsBlockItem>

      <!-- colorCode -->
      <CardDataRowsBlockItem
        v-if="item.color_codes && item.color_codes.length > 0"
        :name="$t('fields.color')"
      >
        <div class="flex items-center gap-1">
          <!-- Handle multiple colors (new format) -->
          <template v-if="item.color_codes && item.color_codes.length > 0">
            <template v-for="(color, index) in item.color_codes" :key="index">
              <Image
                :src="icon.color(color)"
                :img-attributes="{ class: 'w-5' }"
              />
              <span v-if="index < item.color_codes.length - 1" class="mr-1"
                >{{ $t(`colors.${color}`) }},</span
              >
              <span v-else>{{ $t(`colors.${color}`) }}</span>
            </template>
          </template>
        </div>
      </CardDataRowsBlockItem>

      <!-- life -->
      <CardDataRowsBlockItem v-if="item.life" :name="$t('fields.life')">
        {{ item.life }}
      </CardDataRowsBlockItem>

      <!-- hp -->
      <CardDataRowsBlockItem v-if="item.hp" :name="$t('fields.hp')">
        {{ item.hp }}
      </CardDataRowsBlockItem>

      <!-- bloomLevelCode -->
      <CardDataRowsBlockItem
        v-if="item.bloom_level_code"
        :name="$t('fields.bloomLevel')"
      >
        {{ $t(`bloomLevel.${item.bloom_level_code}`) }}
      </CardDataRowsBlockItem>

      <!-- batonTouchCount -->
      <CardDataRowsBlockItem
        v-if="item.baton_touch_count && item.baton_touch_count > 0"
        :name="$t('fields.batonTouchCount')"
      >
        <div class="flex items-center">
          <template
            v-for="(type, index) in item.baton_touch_types"
            :key="index"
          >
            <Image
              :src="icon.artCost(type)"
              :img-attributes="{ class: 'w-6 h-6' }"
            />
          </template>
          <span class="ml-1">
            ({{
              item.baton_touch_types
                ?.map((type: string) => $t(`colors.${type}`))
                .join(", ")
            }})
          </span>
        </div>
      </CardDataRowsBlockItem>
    </div>
  </div>
</template>
