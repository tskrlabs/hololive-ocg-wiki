<script setup lang="ts">
import { UseClipboard } from "@vueuse/components";
import type { Card } from "@/types/card";

defineProps<{
  item: Card;
}>();

// Use translation composable
const { getTranslatedText } = useTranslation();

const icon = useGameIcon();

// The tag row reads the toggle directly rather than through `CardListOriginalText`,
// because it renders a *list* as its own line rather than one string inline. See the
// comment on that block for why tags are the exception.
const { enabled: showOriginal } = useShowOriginal();
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
        <div class="flex flex-col items-end gap-1">
          <div class="flex flex-wrap justify-end gap-1">
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

          <!--
            The source tags, as a second row rather than inline after each one (#62).
            Every other label puts its original inline via `CardListOriginalText`; tags
            are the one place that reads badly, for two measured reasons.

            **The lists overlap heavily.** On the golden fixtures, 39% of tag pairs in
            `en` are byte-identical and 60% in `tc` — `#JP`, `#EN`, `#Advent`, and in `tc`
            also `#0期生` and `#4期生`, which are already Japanese in Chinese. Inline would
            print `#JP #JP` more often than not, burying the pairs that actually differ
            (`#Singing` → `#歌`). Suppressing the identical ones is not available: the
            contract is whole-list-or-nothing, because a partially-shown tag list reads as
            a data error (`localize.ts`), so that would be a change to the schema rather
            than to this view.

            **A tag is a button.** Each one copies its source string to the clipboard, so
            a second string inside the button changes what "copy" means, and outside it
            roughly doubles the width of a row that already wraps.

            Stacking sidesteps both. It is also the treatment `CardItem` already gives a
            card name on a tile, so the pattern is not new here.

            Not a `<Button>`: these are for reading, not copying — the translated row above
            already carries every clipboard target.
          -->
          <div
            v-if="showOriginal && item.original?.tags?.length"
            lang="ja"
            class="flex flex-wrap justify-end gap-x-3 gap-y-1 text-[0.9em] font-normal text-muted-foreground"
          >
            <span v-for="(tag, index) in item.original.tags" :key="index">
              {{ tag }}
            </span>
          </div>
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
