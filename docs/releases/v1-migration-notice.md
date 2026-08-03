# The v1 migration notice

Copy and a component sketch for the **v1 repository**
([`lichingchester/hololive-ocg-wiki`](https://github.com/lichingchester/hololive-ocg-wiki),
serving `hololive-ocg-wiki.lichingchester.dev`).

This file lives here because it is part of the v2.0.0 release, but **nothing in it has been
applied**. The v1 repo was not touched. It is a handoff.

## What it says, and what it does not

The decision is *"move now, v1 is frozen"*: a one-way door, stated plainly, dismissible.

It says v1 is **no longer updated**, because that is true and is the reader's actual risk.
v2 has 2,463 cards to v1's 2,448, and the gap only widens. It makes **no claim about the
domain's future**, because that is undecided: v1 stays online indefinitely for now. Writing
"this site will shut down" would be a promise nobody has made.

**One thing worth deciding separately.** Two live domains now serve near-identical card
content, which splits search ranking between them. A `<link rel="canonical">` on every v1
page pointing at its v2 equivalent consolidates that without taking v1 down or redirecting
anyone. It is independent of this notice and is not included below.

## The copy

English. Roughly 40 words, one heading, one paragraph, two buttons.

> ### We've moved
>
> This wiki has been rebuilt, and the new version is where everything happens now. Every
> card has its own page, the filters actually work, and it fits on a phone. **This site is
> no longer updated.**
>
> `[ Go to the new site ]`  `[ Not now ]`

Shorter variant, if the dialog feels heavy:

> **The wiki has moved.** New cards and fixes only land on the new site. This one is no
> longer updated.
>
> `[ Take me there ]`  `[ Not now ]`

If v1's other seven locales are wanted, translate the heading and the two buttons only, and
leave the paragraph English. That is the same rule v2's `/changelog` follows, and
untranslated buttons are the part that actually blocks someone.

## Component sketch

Untested, since v1 was not built or run for this. `@vueuse/nuxt` is in v1's dependencies,
so `useLocalStorage` is auto-imported, and the `Dialog` and `Button` components already
exist under `components/ui/`.

```vue
<!-- components/parials/AppV2Notice.vue -->
<script setup lang="ts">
/**
 * v1 to v2 migration notice.
 *
 * Dismissal is remembered so this is a one-time interruption per browser rather than a
 * toll on every visit. A notice that reappears after being dismissed reads as broken and
 * gets blocked rather than read.
 *
 * The key is versioned (`v2-notice-dismissed`) so a future, different announcement can use
 * its own key rather than being silenced by a dismissal of this one.
 */
const V2_URL = "https://hololive-ocg-wiki.tskrlabs.com";

const dismissed = useLocalStorage("v2-notice-dismissed", false);

// Deferred one tick past hydration: an SPA that paints a modal on first frame shows it
// before the page behind it exists, which reads as an interstitial ad.
const open = ref(false);
onMounted(() => {
  if (!dismissed.value) setTimeout(() => (open.value = true), 600);
});

function dismiss() {
  dismissed.value = true;
  open.value = false;
}

/**
 * Remembered on the way out too. Someone who clicks through has migrated, and showing them
 * the same dialog if they ever come back is the one case where it is certainly noise.
 */
function go() {
  dismissed.value = true;
  window.location.href = V2_URL;
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="sm:max-w-md" @escape-key-down="dismiss" @pointer-down-outside="dismiss">
      <DialogHeader>
        <DialogTitle>We've moved</DialogTitle>
        <DialogDescription>
          This wiki has been rebuilt, and the new version is where everything happens now.
          Every card has its own page, the filters actually work, and it fits on a phone.
          <strong class="font-medium text-foreground">This site is no longer updated.</strong>
        </DialogDescription>
      </DialogHeader>

      <DialogFooter class="gap-2 sm:justify-end">
        <Button variant="ghost" @click="dismiss">Not now</Button>
        <Button @click="go">Go to the new site</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
```

Mount it once, in `layouts/default.vue`, so it is not duplicated per page:

```vue
<template>
  <div class="relative flex min-h-svh flex-col bg-background">
    <slot />
    <AppV2Notice />
  </div>
</template>
```

## Worth also doing in v1

A permanent, non-dismissible line in the footer or header. A banner someone dismissed six
months ago is invisible, and a first-time visitor arriving from Google has no idea a newer
site exists:

> This is the old Hololive OCG Wiki and is no longer updated.
> [Go to the current site](https://hololive-ocg-wiki.tskrlabs.com)

The dialog converts the people already there. The static line is what covers everyone
arriving afterwards.
