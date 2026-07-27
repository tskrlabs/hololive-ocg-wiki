/**
 * The card-detail dialog's open/loading state.
 *
 * Fetches **through `useCardQuery`**, not with its own `$fetch`. v1 called the endpoint
 * directly here, so the detail dialog was a second, uncached path to a card the store may
 * already have held — and reopening the same card refetched it.
 */

import type { Card, Locales } from "@/types/card";

export function useCardDetail() {
  const { locale } = useI18n();
  const cardQuery = useCardQuery();

  const open = ref(false);
  const card = ref<Card | null>(null);
  const loading = ref(false);

  async function openCard(id: string) {
    open.value = true;
    if (card.value?.id === id) return;

    card.value = null;
    loading.value = true;
    try {
      card.value = (await cardQuery.getCardById(id, locale.value as Locales)) ?? null;
    } catch {
      card.value = null;
    } finally {
      loading.value = false;
    }
  }

  return { open, card, loading, openCard };
}
