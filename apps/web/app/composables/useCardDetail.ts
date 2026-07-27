import type { Card } from "@/types/card";

export function useCardDetail() {
  const { locale } = useI18n();

  const open = ref(false);
  const card = ref<Card | null>(null);
  const loading = ref(false);

  async function openCard(id: string) {
    open.value = true;
    if (!card.value || card.value.id !== id) {
      card.value = null;
      loading.value = true;
      try {
        const data = await $fetch<{ card: Card }>(`/api/cards/${id}`, {
          params: { locale: locale.value },
        });
        card.value = data?.card ?? null;
      } catch {
        card.value = null;
      } finally {
        loading.value = false;
      }
    }
  }

  return { open, card, loading, openCard };
}
