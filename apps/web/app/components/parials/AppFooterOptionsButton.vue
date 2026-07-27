<script setup lang="ts">
import { CircleEllipsis, Trash2, ClipboardCopy, Eye } from "lucide-vue-next";
import { toast } from "vue-sonner";
import { useClipboard } from "@vueuse/core";

const { t } = useI18n();

const localeRoute = useLocaleRoute();

const decks = useDecks();
const currentDeck = computed(() => decks.currentDeck.value);

const source = ref("");
const { text, copy, copied, isSupported } = useClipboard({ source });

const shareDeck = () => {
  if (currentDeck.value) {
    source.value = decks.getDeckCode(currentDeck.value.id).fullUrl;
    copy();
    if (!isSupported.value) {
      toast.error(t("Clipboard is not supported in this browser."));
      return;
    }
    toast.success(t("Copied deck code URL."));
  } else {
    toast.warning(t("Please select a deck to continue."));
  }
};

const goToDetailPage = () => {
  if (!currentDeck.value) {
    toast.warning(t("Please select a deck to continue."));
    return;
  }
  const code = decks.getDeckCode(currentDeck.value.id).code;
  const route = localeRoute({ name: "deck-code", params: { code } });
  if (route) {
    navigateTo(route.fullPath);
  } else {
    toast.error(t("Deck detail page not found."));
  }
};

const deleteDeck = () => {
  if (!currentDeck.value) {
    toast.warning(t("Please select a deck to continue."));
    return;
  }

  decks.deleteDeck(currentDeck.value.id);
  toast.success(t("Deck deleted successfully!"));
};
</script>

<template>
  <div class="">
    <AlertDialog>
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <Button variant="outline">
            <CircleEllipsis />
            <span class="hidden md:inline-flex"> {{ $t("Options") }} </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuItem @click="shareDeck">
              <ClipboardCopy /> {{ $t("Copy Deck Code URL") }}
            </DropdownMenuItem>
            <DropdownMenuItem @click="goToDetailPage">
              <Eye /> {{ $t("Go to Detail Page") }}
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <AlertDialogTrigger as-child>
              <DropdownMenuItem>
                <Trash2 class="text-red-500 size-4" /> {{ $t("Delete") }}
              </DropdownMenuItem>
            </AlertDialogTrigger>
          </DropdownMenuGroup>
          <!-- <DropdownMenuItem>Export Decks</DropdownMenuItem>
        <DropdownMenuItem>Import Decks</DropdownMenuItem> -->
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialogContent class="md:max-w-xs">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {{ $t("Sure?") }}
          </AlertDialogTitle>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>
            {{ $t("Cancel") }}
          </AlertDialogCancel>
          <AlertDialogAction variant="destructive" @click="deleteDeck">
            {{ $t("Delete") }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
