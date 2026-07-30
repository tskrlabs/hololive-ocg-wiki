/**
 * Whether card labels are shown in the source language alongside the translation.
 *
 * A reader who knows a card by its Japanese name is scanning a list of 50 tiles for a
 * name they already recognise. The toggle is for them, and it has to be instant — the
 * API ships `card.original` with every response precisely so this is a state flip and
 * not a round-trip. A spinner per glance would defeat the point.
 *
 * Global rather than per-component: a reader who turns it on wants it on everywhere,
 * and `useState` makes it survive navigation without a store.
 *
 * Persisted, because the preference is durable — someone who reads Japanese card names
 * on Monday still does on Tuesday. `useState` alone resets on reload.
 */
export const useShowOriginal = () => {
  const enabled = useState<boolean>("show-original", () => false);

  // localStorage is read once on mount rather than in the state initialiser: the
  // initialiser runs during SSR-style hydration where `window` may not exist, and this
  // app is `ssr: false` but the same code path runs under `nuxt generate`.
  onMounted(() => {
    const stored = localStorage.getItem("show-original");
    if (stored !== null) enabled.value = stored === "true";
  });

  watch(enabled, (value) => {
    localStorage.setItem("show-original", String(value));
  });

  const toggle = () => {
    enabled.value = !enabled.value;
  };

  return { enabled, toggle };
};
