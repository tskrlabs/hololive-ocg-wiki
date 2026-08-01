<script setup lang="ts">
/**
 * The saved-decks picker: choose one, create one, view or delete (D18).
 *
 * ⚠️ **Not to be confused with `AppFooterDeckPanelButton` beside it**, which opens the
 * panel showing the *current* deck. The two sat in the same footer labelled "Decks" and
 * "Deck" — one letter apart in English, and in **`tc` the identical string**: both read
 * 牌組, so on Traditional Chinese the footer carried two differently-icon'd buttons with
 * the same word. `ja`, `ko` and `th` had already distinguished them (デッキ一覧 against
 * デッキ); `en`, `id` and `es` differed only by a plural.
 *
 * So this is named for what it holds rather than pluralised: **"My Decks"**, with
 * `Library` for a shelf of saved things. The panel button keeps "Deck" and `PanelRight`,
 * which describes a surface rather than a collection. `Layers` went with the rename — it
 * reads as "stacked cards", which is what a *deck* is, not what a list of decks is.
 *
 * The old top-level `Decks` key is deleted rather than left: it had no other caller, and
 * a translated string sitting unused in seven locales is one a later component reaches
 * for by name without knowing it was retired.
 */
import { PackagePlus, Trash2, Library, Pencil, Eye } from "lucide-vue-next";
import type { Deck } from "@/types/deck";
import { toast } from "vue-sonner";

const { t } = useI18n();

const decks = useDecks();

/**
 * Choosing a deck opens the panel and starts editing (D18).
 *
 * Every path out of this component that sets the current deck goes through `openFor`,
 * because all three are the same statement of intent: create a deck, click its name, or
 * click the pencil. Setting the deck and stopping there left the user with a shut panel,
 * editing off, and a grid whose add controls do not render — three more actions to reach
 * the state their first click already meant.
 */
const panel = useDeckPanel();

// popover
const isActive = ref(false);

// create deck
const name = ref("");
const author = ref("");

const isCreateDeckDialogOpen = ref(false);

const createDeck = () => {
  if (!name.value) {
    toast.error(t("Deck name is required."));
    return;
  }

  const newDeck: Deck = decks.createNewDeck(name.value, author.value);

  decks.addDeck(newDeck);
  // Not `setCurrentDeck`: creating a deck is the strongest statement of intent there is,
  // so it lands in the state that intent implies — panel open, editing on.
  panel.openFor(newDeck);

  // Close the dialog
  isCreateDeckDialogOpen.value = false;

  // Reset fields after creation
  name.value = "";
  author.value = "";

  toast.success(t("Deck created successfully!"));
};

/**
 * Pick a deck from the list, and get on with editing it.
 *
 * The name and the pencil both land here — they were two copies of the same comma
 * expression, `decks.setCurrentDeck(deck), (isActive = false)`, which is also why the
 * pencil (the *edit* affordance) did not turn editing on. Closing the popover is part of
 * the action: the deck panel is what the user asked for, and leaving a popover open on
 * top of it would cover the thing it just revealed.
 */
const selectDeck = (deck: Deck) => {
  panel.openFor(deck);
  isActive.value = false;
};

const onNewDeckButtonClick = () => {
  isCreateDeckDialogOpen.value = true;
  isActive.value = false; // Close the popover when creating a new deck
};
</script>

<template>
  <Dialog v-model:open="isCreateDeckDialogOpen">
    <Popover v-model:open="isActive">
      <PopoverTrigger as-child>
        <!--
          The label stays visible at every width, unlike the panel button's, which is
          `hidden md:inline-flex`. That asymmetry is useful rather than untidy: on a phone
          the panel button is an icon alone, so the only labelled deck control is this
          one — and "My Decks" beside a bare `PanelRight` is easier to tell apart than two
          unlabelled icons would be.
        -->
        <Button>
          <Library aria-hidden="true" />
          {{ $t("deck.myDecks") }}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" class="w-auto min-w-50 p-3 md:p-3">
        <DialogTrigger as-child>
          <Button
            variant="outline"
            @click="onNewDeckButtonClick"
            class="w-full"
          >
            <PackagePlus /> {{ $t("New Deck") }}
          </Button>
        </DialogTrigger>

        <div v-if="decks.decks.value.length" class="mt-2 md:mt-3"></div>

        <div class="flex">
          <ScrollArea class="w-full max-h-[50vh]">
            <div class="flex flex-col gap-0">
              <template v-for="(deck, index) in decks.decks.value" :key="index">
                <Separator v-if="index !== 0" class="my-1" />

                <div class="flex items-center">
                  <div class="pr-2 max-w-[50vw] grow">
                    <button
                      class="w-full text-left"
                      @click="selectDeck(deck)"
                    >
                      {{ deck.name }}
                    </button>
                  </div>

                  <div class="flex gap-1 ml-auto">
                    <Button
                      variant="ghost"
                      size="icon"
                      class="size-8"
                      as-child
                      @click="isActive = false"
                    >
                      <NuxtLink :to="decks.getDeckCode(deck.id).localePath">
                        <Eye class="size-4" />
                      </NuxtLink>
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="size-8"
                      @click="selectDeck(deck)"
                    >
                      <Pencil class="size-4" />
                    </Button>
                  </div>
                </div>
              </template>
            </div>
          </ScrollArea>
        </div>
      </PopoverContent>
    </Popover>

    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle>{{ $t("New Deck") }}</DialogTitle>
      </DialogHeader>

      <div class="space-y-4">
        <div class="grid gap-2">
          <Label for="name">
            {{ `${$t("Deck Name")}*` }}
          </Label>
          <Input
            id="name"
            type="text"
            placeholder="My New Deck"
            v-model="name"
          />
        </div>

        <div class="grid gap-2">
          <Label for="author">
            {{ $t("Author") }}
          </Label>
          <Input id="author" type="text" placeholder="Me" v-model="author" />
        </div>

        <DialogFooter>
          <Button class="w-full" @click="createDeck">
            {{ $t("Create Deck") }}
          </Button>
        </DialogFooter>
      </div>
    </DialogContent>
  </Dialog>
</template>
