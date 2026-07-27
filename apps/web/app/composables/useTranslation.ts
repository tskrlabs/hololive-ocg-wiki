/**
 * Composable for safe translation handling
 * Provides utilities for working with i18n translations with error handling
 */
export const useTranslation = () => {
  const { rt, tm } = useI18n();

  /**
   * Safely get translated text with fallback
   * @param category - The translation category (e.g., 'names', 'tags', 'sets')
   * @param key - The translation key
   * @param fallback - Fallback text if translation is not found
   * @returns Translated text or fallback
   */
  const getTranslatedText = (
    category: string,
    key: string,
    fallback: string
  ): string => {
    try {
      const translations = tm(category) as Record<string, string>;
      return translations?.[key] ? rt(translations[key]) : fallback;
    } catch (error) {
      console.warn(`Translation error for ${category}.${key}:`, error);
      return fallback;
    }
  };

  return {
    getTranslatedText,
  };
};
