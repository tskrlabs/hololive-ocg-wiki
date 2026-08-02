/**
 * `?set_code=hBP03` — the one filter with a URL (ADR 0010).
 *
 * Filter state is otherwise in-memory only: `index.vue` reads no query parameters, so no
 * filter today survives a reload, a share or the back button. Serialising all of them is
 * its own design — defaults, encoding, history depth, what a bare `/` means — and this
 * does not attempt it.
 *
 * Set code gets one because it is the highest-value link a card wiki has after a card
 * page: "every card in hBP03" is a thing people send each other, and the official card
 * list has had `?expansion=` for it all along. It is also the safest one to start with,
 * being a single opaque token with no encoding questions.
 *
 * **`replace`, not `push`.** The set code is usually reached by typing in the search box,
 * which fires on a 500 ms debounce — pushing would put one history entry per pause in
 * typing, so Back would walk the user through their own keystrokes instead of returning
 * them to where they came from.
 */
export function useSetCodeUrl() {
  const route = useRoute();
  const router = useRouter();
  const filter = useFilter();

  /** Read the URL into the filter — once, on load. */
  const applyFromUrl = () => {
    const fromUrl = route.query.set_code;
    const code = Array.isArray(fromUrl) ? fromUrl[0] : fromUrl;
    if (typeof code !== "string" || !code) return;

    // Both, for the same reason the search handoff writes both: the applied filter is
    // what fetches, the draft is what the panel shows, and leaving the draft empty would
    // make the next Apply silently clear a filter the user can see is active.
    filter.filter.value.setCode = code;
    filter.draftFilter.value.setCode = code;
  };

  /**
   * Write the filter back to the URL whenever it changes.
   *
   * Watches the *applied* value rather than the draft: the URL should describe what the
   * grid is showing, not what the panel is being edited to.
   */
  const syncToUrl = () =>
    watch(
      () => filter.filter.value.setCode,
      (code) => {
        const query = { ...route.query };
        if (code) query.set_code = code;
        else delete query.set_code;

        // Nothing to do if it already says this — a redundant `replace` still fires the
        // router's navigation guards and, on some browsers, interrupts an in-flight
        // scroll restoration.
        if (query.set_code === route.query.set_code) return;
        router.replace({ query });
      },
    );

  return { applyFromUrl, syncToUrl };
}
