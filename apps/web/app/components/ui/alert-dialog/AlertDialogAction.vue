<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { reactiveOmit } from "@vueuse/core";
import { AlertDialogAction, type AlertDialogActionProps } from "reka-ui";
import { cn } from "@/lib/utils";
import { type ButtonVariants, buttonVariants } from "@/components/ui/button";

const props = defineProps<
  AlertDialogActionProps & {
    class?: HTMLAttributes["class"];
    variant?: ButtonVariants["variant"];
  }
>();

const delegatedProps = reactiveOmit(props, "class");
</script>

<template>
  <AlertDialogAction
    v-bind="delegatedProps"
    :class="cn(buttonVariants({ variant }), props.class)"
  >
    <slot />
  </AlertDialogAction>
</template>
