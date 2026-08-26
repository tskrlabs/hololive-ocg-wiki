# Demo scripts

Browser-console snippets for exercising states the UI cannot reach on its own.

## `demo-legacy-deck.js` — the ADR 0014 deck migration

Plants a pre-migration, id-keyed deck in `localStorage`. Needed because there is no longer
any way to *create* one: decks are written as `image-key` from the moment they are made, so
without seeding one by hand the migration has nothing to act on and the demo shows nothing.

```bash
make dev          # API on :8787 (local D1 + fixtures), site on :3000
```

Open **http://localhost:3000** — port 3000, not 8787. `:8787` serves a stale static build,
not the live source, so a change made now will not appear there.

Paste `demo-legacy-deck.js` into the browser console, then **reload**.

### What to look for

| # | expected | why it matters |
|---|---|---|
| 1 | a toast: *Updated 1 deck(s) to the latest card numbering.* | the migration ran, and said so once — reload again and it must **not** reappear |
| 2 | `localStorage["hololive-ocg-wiki-decks.pre-image-key"]` holds the original | the eager migration touches every saved deck at once, so the pre-state is kept |
| 3 | the stored deck now holds `image_key`s and `cardRefFormat: "image-key"` | the format actually moved, rather than being translated on every read |
| 4 | the deck panel shows a **placeholder tile**, not a silently shorter deck | a dropped card in a 50-card deck is invisible; only the user knows what was meant |

Check 2 and 3 in the console:

```js
JSON.parse(localStorage.getItem("hololive-ocg-wiki-decks"))[0]
JSON.parse(localStorage.getItem("hololive-ocg-wiki-decks.pre-image-key"))[0]
```

### Seeing the actual bug, locally

The renumbering is the whole point, and it is visible in the stored data even though the
fixture set cannot render the card. After reloading, run:

```js
JSON.parse(localStorage.getItem("hololive-ocg-wiki-decks"))[0].mainCardIds
JSON.parse(localStorage.getItem("hololive-ocg-wiki-decks.pre-image-key"))[0].mainCardIds
```

The backup holds `"2582"`. The migrated deck holds `hEB01/hBP01-051_UR_02` — the card that
id **meant when the deck was saved**. In the current data that same id means
`hEB01/hEB01-007_SR`, a different card entirely.

That gap is the bug: without the migration the deck resolves cleanly to the wrong card, with
no error, no empty slot, and nothing for a player to notice.

### What the local demo cannot show

The fixture database is 34 cards, all `hSD01`/`hBP01`, so the `hEB01` key above has no local
artwork and renders as a placeholder alongside the genuinely unknown `999999`. Expected, not
a bug — locally this proves the migration (toast, backup, format change, surviving slots).
Seeing 2582 render as the *right card* needs the real dataset, i.e. production after the
seed.

### Reset

```js
localStorage.removeItem("hololive-ocg-wiki-decks");
localStorage.removeItem("hololive-ocg-wiki-decks.pre-image-key");
```
