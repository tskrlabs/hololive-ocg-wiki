<script setup lang="ts">
import { PackagePlus, Trash2, Layers, Pencil, Eye } from "lucide-vue-next";
import type { Deck } from "@/types/deck";
import { toast } from "vue-sonner";

const { t } = useI18n();

const decks = useDecks();

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
  decks.setCurrentDeck(newDeck);

  // Close the dialog
  isCreateDeckDialogOpen.value = false;

  // Reset fields after creation
  name.value = "";
  author.value = "";

  toast.success(t("Deck created successfully!"));
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
        <Button>
          <Layers />
          {{ $t("Decks") }}
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
                      @click="decks.setCurrentDeck(deck), (isActive = false)"
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
                      @click="decks.setCurrentDeck(deck), (isActive = false)"
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
