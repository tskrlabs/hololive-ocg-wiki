/**
 * The Worker's bindings, as declared in `wrangler.jsonc`.
 *
 * `IMAGES` is bound but unused by the API: card art is served directly from
 * `img.hololive-ocg-wiki.tskrlabs.com`, and the database stores an `image_key` the
 * client composes a URL from (D9). The binding stays declared because the bucket is
 * part of this Worker's infrastructure and `wrangler.jsonc` is the record of that.
 */

export interface Env {
  DB: D1Database;
  ARTIFACTS: R2Bucket;
  IMAGES: R2Bucket;
  /**
   * The generated site, so the Worker can fetch a shell and rewrite it (D7).
   *
   * Only the card-page route uses this. Everything else outside `/api/` is served
   * directly by the asset layer without invoking the Worker at all, which is what keeps
   * those requests free.
   */
  ASSETS: Fetcher;
  /** Comma-separated CORS allowlist. Same-origin production traffic needs none. */
  ALLOWED_ORIGINS?: string;
  /** The public origin, for canonical URLs. Defaults to the production domain. */
  SITE_URL?: string;
  /** The card-art CDN origin, for `og:image`. */
  IMAGE_BASE_URL?: string;
}
