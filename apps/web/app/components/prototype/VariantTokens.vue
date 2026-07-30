<script setup lang="ts">
/**
 * ⚠️ PROTOTYPE — throwaway. Delete once #35 is decided.
 *
 * Injects a variant's token set + typeface as a scoped stylesheet. Each variant is a
 * complete replacement for `assets/css/tailwind.css`'s `:root`/`.dark` blocks, so what
 * you see is what the real theme would be — not an overlay on top of the stock slate.
 */
const props = defineProps<{ variant?: string }>();
void props;

/**
 * D: B's structure and typography, C's ink-only palette. The chosen hybrid (#35).
 *
 * C's neutrals verbatim — no hue in the greys, no accent colour. B's Inter + tabular
 * numerics, B's 0.5rem radius, B's medium density. The one deliberate change from C:
 * --primary stays ink, so the sole saturated thing on screen is card art.
 */
const THEME = `
:root{
  --background: oklch(0.975 0.002 260);
  --foreground: oklch(0.16 0.004 260);
  --card: oklch(1 0 0); --card-foreground: var(--foreground);
  --popover: oklch(1 0 0); --popover-foreground: var(--foreground);
  --primary: oklch(0.16 0.004 260);
  --primary-foreground: oklch(0.99 0 0);
  --secondary: oklch(0.945 0.002 260); --secondary-foreground: oklch(0.24 0.004 260);
  --muted: oklch(0.945 0.002 260); --muted-foreground: oklch(0.545 0.006 260);
  --accent: oklch(0.925 0.003 260); --accent-foreground: oklch(0.20 0.004 260);
  --destructive: oklch(0.55 0.20 25); --destructive-foreground: oklch(0.99 0 0);
  --border: oklch(0.905 0.003 260); --input: oklch(0.905 0.003 260);
  --ring: oklch(0.16 0.004 260);
  --radius: 0.5rem;
}
.dark{
  --background: oklch(0.135 0.004 260);
  --foreground: oklch(0.955 0.002 260);
  --card: oklch(0.175 0.004 260); --card-foreground: var(--foreground);
  --popover: oklch(0.175 0.004 260); --popover-foreground: var(--foreground);
  --primary: oklch(0.955 0.002 260); --primary-foreground: oklch(0.14 0.004 260);
  --secondary: oklch(0.215 0.004 260); --secondary-foreground: var(--foreground);
  --muted: oklch(0.215 0.004 260); --muted-foreground: oklch(0.655 0.006 260);
  --accent: oklch(0.245 0.004 260); --accent-foreground: var(--foreground);
  --border: oklch(0.255 0.004 260); --input: oklch(0.255 0.004 260);
  --ring: oklch(0.955 0.002 260);
}
.proto-root{ font-family: "Inter","Noto Sans TC","Noto Sans JP","Noto Sans Thai",system-ui,sans-serif; font-feature-settings:"cv05","ss01"; }
.proto-display{ font-family:"Inter",system-ui,sans-serif; font-weight:700; letter-spacing:-0.02em; }
.proto-num{ font-family: ui-monospace,"SF Mono",monospace; font-variant-numeric: tabular-nums; }
`;

/**
 * E: D, but with a single restrained accent restored for interactive state only.
 *
 * D proved the ink-only palette reads beautifully at rest — and that at rest is not the
 * whole job. B's structure makes Apply the primary action and the colour chips a
 * multi-select; with --primary === --foreground both collapse into body text. This keeps
 * C's neutral ground everywhere and spends colour *only* on "this control is active".
 */

/**
 * Injected as a real <style> element appended to <head>, not via useHead().
 *
 * useHead's style array did not reach the DOM here (verified: zero :root style tags
 * present at runtime), so the stock `.dark` block in tailwind.css kept winning. Appending
 * last also guarantees these rules come after the compiled sheet in document order, which
 * is what the equal-specificity :root / .dark selectors need.
 */
const FONTS =
  "https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Source+Sans+3:wght@400;500;600&family=Inter:wght@400;500;600;700&family=Figtree:wght@400;500;600&family=Noto+Sans+TC:wght@400;500;700&family=Noto+Sans+JP:wght@400;500;700&family=Noto+Sans+Thai:wght@400;500;700&display=swap";

let styleEl: HTMLStyleElement | null = null;

function apply() {
  if (typeof document === "undefined") return;
  if (!document.getElementById("proto-fonts")) {
    const link = document.createElement("link");
    link.id = "proto-fonts";
    link.rel = "stylesheet";
    link.href = FONTS;
    document.head.appendChild(link);
  }
  if (!styleEl) {
    styleEl = document.createElement("style");
    styleEl.id = "proto-tokens";
    document.head.appendChild(styleEl);
  }
  styleEl.textContent = THEME;
}

onMounted(apply);
onUnmounted(() => {
  styleEl?.remove();
  styleEl = null;
});
</script>

<template><span class="hidden" /></template>
