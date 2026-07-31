/**
 * How much of a card the grid shows (ADR 0009 D13, D14; #37, #52).
 *
 * **Comfortable** is art + name + card number; **compact** is art alone. Compact is not a
 * new idea — it is what the site did before this, kept for readers who recognise a card
 * by its art and want more of them on screen.
 *
 * On desktop this is a preference. **On mobile it is not**: measured at 375×812,
 * comfortable at 2 columns shows **4 cards per screen** against compact-at-3-columns'
 * **9**. Across 2,463 cards that is the difference between browsing and scrolling, which
 * is why `columnsFor()` below adds a column in compact mode on a phone and why the
 * control has to be reachable there at all.
 *
 * Dropping the text at 3 mobile columns costs nothing: the name box would be 112px, where
 * **130 of 2,463 names truncate (5.3%)** against **1 (0.0%)** at 2 columns — and at that
 * size the name printed in the art is unreadable too.
 *
 * Persisted for the same reason `useShowOriginal` is, and deliberately built the same way:
 * someone who prefers dense browsing on Monday still does on Tuesday. That composable is
 * the template this copies, down to reading `localStorage` in `onMounted` rather than in
 * the state initialiser.
 */

export type CardDensity = "comfortable" | "compact";

const STORAGE_KEY = "card-density";

/**
 * Whether a mode shows the name and card number.
 *
 * A plain function rather than a computed, because `gridColumns.ts` needs the same answer
 * and is deliberately mount-free — the geometry is arithmetic over every width, which no
 * fixture set covers and no mounted test should have to.
 */
export function showsText(density: CardDensity): boolean {
  return density === "comfortable";
}

export const useCardDensity = () => {
  const density = useState<CardDensity>(STORAGE_KEY, () => "comfortable");

  // Read once on mount, not in the initialiser: the initialiser runs during hydration
  // where `window` may not exist, and this app is `ssr: false` but the same code path
  // runs under `nuxt generate`.
  onMounted(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "comfortable" || stored === "compact") density.value = stored;
  });

  watch(density, (value) => {
    localStorage.setItem(STORAGE_KEY, value);
  });

  const toggle = () => {
    density.value = density.value === "comfortable" ? "compact" : "comfortable";
  };

  return { density, toggle, isCompact: computed(() => density.value === "compact") };
};
