/**
 * Game icons — colour symbols, art costs, keyword badges (ADR 0006, Q12).
 *
 * These are UI chrome shipped with the site, not card data, so unlike card art (D9) they
 * stay in `public/` rather than R2. But they are **WebP only** now: v1 committed a PNG
 * and a WebP of each, ~800 KB of duplicates hedging against browsers that no longer
 * exist, and every call site asked for the `.png`.
 *
 * The path convention was written out by hand in three components
 * (`/icons/type_${key}.png`) — the architecture review flagged it, and it is the same
 * shape of duplication `cardImage()` retires for card art. One composer here means the
 * extension changed in one place, which is what let the PNGs go.
 */

import type { ColorCode, KeywordTypeCode } from "@holo/schema/enums";

/** `bloomEF` / `collabEF` / `gift` — the filenames the keyword icons actually use. */
const KEYWORD_ICONS: Record<KeywordTypeCode, string> = {
  bloom_effect: "bloomEF",
  collab_effect: "collabEF",
  gift: "gift",
};

export function useGameIcon() {
  return {
    /** One colour badge, e.g. `type_red`. A dual-colour card calls this twice. */
    color: (code: ColorCode | string): string => `/icons/type_${code}.webp`,

    /** The cost symbol on an art, e.g. `arts_green`. */
    artCost: (code: ColorCode | string): string => `/icons/arts_${code}.webp`,

    /**
     * The 特攻 (special-target) badge, e.g. `tokkou_50_red`.
     *
     * Only the +50 variant is printed on any card in the set, which is why the value is
     * baked into the filename rather than parameterised.
     */
    specialTarget: (code: ColorCode | string): string =>
      `/icons/tokkou_50_${code}.webp`,

    /** A keyword badge. The filenames are camelCase, unlike the contract's codes. */
    keyword: (code: KeywordTypeCode | string): string =>
      `/icons/${KEYWORD_ICONS[code as KeywordTypeCode] ?? code}.webp`,
  };
}
