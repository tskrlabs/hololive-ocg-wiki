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

  /** The `set_code` the URL currently names, normalised out of the array form. */
  const codeInUrl = () => {
    const fromUrl = route.query.set_code;
    const code = Array.isArray(fromUrl) ? fromUrl[0] : fromUrl;
    return typeof code === "string" && code ? code : undefined;
  };

  /** Read the URL into the filter — once, on load. */
  const applyFromUrl = () => {
    const code = codeInUrl();
    if (!code) return;

    // Both, for the same reason the search handoff writes both: the applied filter is
    // what fetches, the draft is what the panel shows, and leaving the draft empty would
    // make the next Apply silently clear a filter the user can see is active.
    filter.filter.value.setCode = code;
    filter.draftFilter.value.setCode = code;
  };

  /**
   * Keep following the URL after load, so an in-app link to `?set_code=` works.
   *
   * `applyFromUrl` alone runs at setup, which is enough for a cold load but not for a
   * link followed *while the listing page is already mounted* — the page does not
   * re-setup, so the query changes and nothing reads it. That is what made the deck
   * panel's "Browse hBP01" change the URL and nothing else (ADR 0014's placeholder).
   *
   * Navigating from another page (the deck detail view) re-runs setup, so the panel
   * updated there — but the grid still did not refetch, because `applyFiltersIfNeeded`
   * skips a `ready` list and the filter had been written *before* the watcher existed.
   * Assigning here, after mount, means the filter watcher in `CardListViewAPI` sees a
   * real change and refetches.
   *
   * Guarded on inequality: `syncToUrl` writes the URL from the filter, so an unguarded
   * watcher would answer its own write and loop.
   */
  const followUrl = () =>
    watch(codeInUrl, (code) => {
      const next = code ?? "";
      if (filter.filter.value.setCode === next) return;
      filter.filter.value.setCode = next;
      filter.draftFilter.value.setCode = next;
    });

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

  return { applyFromUrl, syncToUrl, followUrl };
}
