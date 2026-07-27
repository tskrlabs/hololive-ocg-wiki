/**
 * Card image URLs (D9).
 *
 * D1 stores an `image_key` — `hBP01/hBP01-028_C_02` — and the URL is composed here. v1
 * baked the folder layout *and* the `.png` extension into the database
 * (`image_path = "card_images/default/hBP01-028_C_02.png"`), so changing CDN host or
 * image format would have meant a full reseed.
 *
 * The composition itself lives in `@holo/schema`, beside the contract that defines the
 * key, and is covered by the golden parity tests. This composable exists only to supply
 * the configured base URL, so a component never has to know one.
 *
 * It replaces `getImagePath()`, which the architecture review found copy-pasted verbatim
 * into three components, plus three more templates that interpolated `image_path`
 * directly.
 */

import { cardImage } from "@holo/schema/localize";

export function useCardImage() {
  const { imageBaseUrl } = useRuntimeConfig().public;

  /**
   * @param imageKey - `Card.image_key`, e.g. `hBP01/hBP01-028_C_02`
   * @returns the WebP URL, or `""` when the key is missing so a template can `v-if` it
   */
  return (imageKey?: string | null): string =>
    imageKey ? cardImage(imageKey, imageBaseUrl) : "";
}
