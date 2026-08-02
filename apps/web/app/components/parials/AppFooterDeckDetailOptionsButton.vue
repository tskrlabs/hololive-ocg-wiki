<script setup lang="ts">
/**
 * Import or share the deck this page is showing (#57).
 *
 * `importDeckByCode` returns a `message` that was passed straight to the toast. It *is*
 * translated — the composable calls `t()` — but routing a string through a status object
 * means the copy the user reads is chosen a layer away from where it is displayed, and a
 * future caller returning an untranslated string would show it verbatim with nothing
 * failing. The status is the value worth returning; the wording is decided here.
 */
import { CircleEllipsis, Import, ClipboardCopy } from "lucide-vue-next";
import { toast } from "vue-sonner";

const { t } = useI18n();

const route = useRoute();

const decks = useDecks();
const { copyLink } = useCopyLink();

const importDeck = () => {
  if (!route.params.code) {
    toast.error(t("errors.deck.noCode"));
    return;
  }

  const result = decks.importDeckByCode(route.params.code as string);
  if (result.status) {
    toast.success(result.message);
  } else {
    // The only failure `importDeckByCode` reports is an undecodable code, and saying so
    // is more useful than repeating its own sentence back.
    toast.error(t("errors.deck.invalidCode"));
  }
};

const shareDeck = async () => {
  if (!import.meta.client) return;
  await copyLink(window.location.href);
};
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button variant="outline">
        <CircleEllipsis />
        <span class="hidden md:inline-flex"> {{ $t("Options") }} </span>
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end">
      <DropdownMenuGroup>
        <DropdownMenuItem @click="importDeck">
          <Import /> {{ $t("Import This Deck") }}
        </DropdownMenuItem>

        <DropdownMenuItem @click="shareDeck">
          <ClipboardCopy /> {{ $t("Copy Deck Code URL") }}
        </DropdownMenuItem>
      </DropdownMenuGroup>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
