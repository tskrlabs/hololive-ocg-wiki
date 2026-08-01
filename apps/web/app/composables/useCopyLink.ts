/**
 * Copy a URL to the clipboard and say whether it worked (#57).
 *
 * **This fixes a real ordering bug**, found by reading the toasts #57 made visible. Both
 * copy paths were written as:
 *
 *     copy();
 *     if (!isSupported.value) { toast.error(…); return; }
 *     toast.success(…);
 *
 * — so an unsupported browser was asked to copy *before* anything checked whether it
 * could, and in `AppFooterCurrentDeck` the guard sat after a `source.value =` assignment
 * that made the success path read as though it had already worked. The check belongs
 * before the attempt.
 *
 * It also awaits the copy. `useClipboard().copy()` returns a promise (it calls
 * `navigator.clipboard.writeText`), and a rejected one — permissions, a non-secure
 * context, a document that is not focused — was unhandled, so a failed copy reported
 * success. Now the failure is reported as one.
 */
import { useClipboard } from "@vueuse/core";
import { toast } from "vue-sonner";

export const useCopyLink = () => {
  const { copy, isSupported } = useClipboard();
  const { t } = useI18n();

  /**
   * Returns whether the text reached the clipboard.
   *
   * The toast is fired here rather than by the caller so the three outcomes — unsupported,
   * failed, copied — cannot drift apart between the two components that copy a deck URL.
   */
  const copyLink = async (text: string): Promise<boolean> => {
    if (!isSupported.value) {
      toast.error(t("clipboard.unsupported"));
      return false;
    }

    try {
      await copy(text);
      toast.success(t("clipboard.copied"));
      return true;
    } catch {
      // A rejected write is not the same as an unsupported browser: the API exists and
      // said no. Usually permissions or an unfocused document, neither of which the user
      // can act on from a message that claims the browser lacks the feature.
      toast.error(t("clipboard.failed"));
      return false;
    }
  };

  return { copyLink, isSupported };
};
