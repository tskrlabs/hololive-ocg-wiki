/**
 * The card source (Candidate 01, ADR 0006 Q5).
 *
 * This is what the seam is *for*: a fake transport records the requests the app would
 * make, so the endpoint contract — the batch cap, the comma-joined paths, `skip_count`,
 * the filter mapping — is asserted without a network, a database, or a browser.
 *
 * The behaviours pinned here are ones v1 got wrong:
 *
 * - it joined **every** deck id into one URL, and Phase 4 made that a 400 rather than a
 *   silent truncation — so a legal 71-card deck depends on chunking
 * - its `skip_count` handling read a `-1` sentinel that no longer exists
 */

import { describe, expect, it } from "vitest";
import { MAX_BATCH } from "@holo/schema/enums";

import { chunk, createCardSource, type Transport } from "../app/composables/cardSource";
import { createEmpty } from "../app/composables/filter-states";

/** A transport that records calls and replays canned responses. */
function recorder(responses: unknown[] = []) {
  const calls: { path: string; query?: Record<string, unknown> }[] = [];
  let index = 0;
  const transport: Transport = async <T>(
    path: string,
    query?: Record<string, unknown>,
  ) => {
    calls.push({ path, query });
    return (responses[index++] ?? { cards: [] }) as T;
  };
  return { transport, calls };
}

const card = (id: string) => ({ id, card_number: `hBP01-${id}` });

describe("chunk", () => {
  it("splits at the contract's batch cap", () => {
    const ids = Array.from({ length: 71 }, (_, i) => String(i));
    const batches = chunk(ids);
    expect(batches).toHaveLength(2);
    expect(batches[0]).toHaveLength(MAX_BATCH);
    expect(batches[1]).toHaveLength(71 - MAX_BATCH);
    expect(batches.flat()).toEqual(ids);
  });

  it("leaves an exactly-cap-sized list as one batch", () => {
    expect(chunk(Array.from({ length: MAX_BATCH }, (_, i) => String(i)))).toHaveLength(1);
  });

  it("returns nothing for an empty list", () => {
    expect(chunk([])).toEqual([]);
  });
});

describe("byIds", () => {
  it("chunks a legal deck so the API does not 400", async () => {
    // 1 oshi + 50 main + 20 yell. v1 sent all 71 in one URL; the API rejects that now.
    const ids = Array.from({ length: 71 }, (_, i) => String(i));
    const { transport, calls } = recorder([
      { cards: ids.slice(0, MAX_BATCH).map(card) },
      { cards: ids.slice(MAX_BATCH).map(card) },
    ]);

    const result = await createCardSource(transport).byIds(ids, "en");

    expect(calls).toHaveLength(2);
    expect(calls[0]!.path).toBe(`/api/cards-list/${ids.slice(0, MAX_BATCH).join(",")}`);
    expect(result).toHaveLength(71);
  });

  it("makes no request for an empty list", async () => {
    const { transport, calls } = recorder();
    expect(await createCardSource(transport).byIds([], "en")).toEqual([]);
    expect(calls).toHaveLength(0);
  });
});

describe("filter", () => {
  it("sends only active filters, with paging", async () => {
    const { transport, calls } = recorder([{ cards: [], total: 0 }]);
    const filters = createEmpty();
    filters.colors.blue = true;
    filters.name = "白上フブキ";

    await createCardSource(transport).filter(filters, "tc", 2, 25);

    expect(calls[0]!.path).toBe("/api/cards/filter");
    expect(calls[0]!.query).toEqual({
      colors: ["blue"],
      name: "白上フブキ",
      locale: "tc",
      page: 2,
      limit: 25,
    });
  });

  it("omits skip_count unless it is true", async () => {
    // The API reads the literal string "true"; sending "false" is indistinguishable from
    // not asking, so it is left out entirely.
    const { transport, calls } = recorder([{ cards: [], total: 0 }, { cards: [] }]);
    const source = createCardSource(transport);

    await source.filter(createEmpty(), "en", 1, 50, false);
    expect(calls[0]!.query).not.toHaveProperty("skip_count");

    await source.filter(createEmpty(), "en", 2, 50, true);
    expect(calls[1]!.query).toMatchObject({ skip_count: "true" });
  });
});

describe("search", () => {
  it("does not call the API for a blank query", async () => {
    const { transport, calls } = recorder();
    const source = createCardSource(transport);
    expect(await source.search("   ", "en")).toEqual([]);
    expect(calls).toHaveLength(0);
  });

  it("trims the query and passes the limit", async () => {
    const { transport, calls } = recorder([{ cards: [card("1")] }]);
    await createCardSource(transport).search("  フブキ  ", "ja", 20);
    expect(calls[0]!.query).toEqual({ q: "フブキ", locale: "ja", limit: 20 });
  });
});

describe("byCardNumber", () => {
  it("encodes the number into the path", async () => {
    const { transport, calls } = recorder([{ cards: [] }]);
    await createCardSource(transport).byCardNumber("hBP01-001", "en");
    expect(calls[0]!.path).toBe("/api/cards/filter-by-card-number/hBP01-001");
  });
});
