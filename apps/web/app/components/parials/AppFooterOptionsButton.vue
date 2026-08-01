<script setup lang="ts">
/**
 * Deck actions: copy the share URL, open the detail page, delete (#57).
 *
 * All three needed a deck and each carried its own copy of the guard and its toast; that
 * is now `useDeckGuard`, which also stops two of them stacking the same message. The copy
 * path is `useCopyLink`, which checks clipboard support *before* attempting the write —
 * see there for the ordering bug this had.
 */
import { CircleEllipsis, Trash2, ClipboardCopy, Eye } from "lucide-vue-next";
import { toast } from "vue-sonner";

const { t } = useI18n();

const localeRoute = useLocaleRoute();

const decks = useDecks();
const { requireDeck } = useDeckGuard();
const { copyLink } = useCopyLink();
const currentDeck = computed(() => decks.currentDeck.value);

const shareDeck = async () => {
  if (!requireDeck()) return;
  await copyLink(decks.getDeckCode(currentDeck.value!.id).fullUrl);
};

const goToDetailPage = () => {
  if (!requireDeck()) return;

  const code = decks.getDeckCode(currentDeck.value!.id).code;
  const route = localeRoute({ name: "deck-code", params: { code } });
  if (route) {
    navigateTo(route.fullPath);
  } else {
    toast.error(t("errors.deck.routeMissing"));
  }
};

const deleteDeck = () => {
  if (!requireDeck()) return;

  // Named, because the confirm dialog that precedes this says only "Sure?" — and after
  // the fact the deck is gone from the list, so the name is the only way to be certain
  // which one went.
  const name = currentDeck.value!.name;
  decks.deleteDeck(currentDeck.value!.id);
  toast.success(t("deck.deleted", { name }));
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
                <!-- `--destructive`, not a hardcoded red: it is the one semantic colour
                     D4 keeps, and it is reserved for exactly this — a destructive
                     *action*, not a state or a failure report. -->
                <Trash2 class="text-destructive size-4" /> {{ $t("Delete") }}
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
