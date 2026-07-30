# PROTOTYPE — visual identity (#35)

⚠️ **Throwaway.** Delete this directory and `app/pages/prototype-identity.vue` once the
decision is recorded on #35.

## Question

"Neutral but crafted" was chosen for the identity — real typeface, spacing scale, proper
dark mode, one accent, card art carrying the colour. That is the direction most at risk of
reading as *unchanged* if executed timidly, so it has to be seen rather than described.

## Run it

```bash
make dev
open http://localhost:3000/tc/prototype-identity
```

`?variant=A|B|C`, or ← / → arrow keys. The moon/sun button in the header toggles
light/dark — **both modes must be judged**; the current site's dark mode is unexamined
inverted slate.

## The three directions

| | A — Archive | B — Console | C — Gallery |
|---|---|---|---|
| feel | reference catalogue | deck-builder's instrument | print portfolio |
| ground | warm paper `oklch(.985 .006 85)` | near-white cool `oklch(.995 0 0)` | soft grey `oklch(.975 .002 260)` |
| accent | crimson `oklch(.505 .178 22)` | cyan `oklch(.60 .145 215)` | none — ink only |
| type | Source Serif 4 + Source Sans 3 | Inter + mono numerics | Figtree, uppercase micro-labels |
| radius | 0.25rem | 0.5rem | 0 |
| density | tight (~155px tiles) | medium (~190px) | loose (~235px) |
| names | always on | always on | **off** — art leads |

All three carry CJK and Thai via Noto, since the site renders seven locales.

## What is deliberately real

- **Real cards, real art** from the fixture set through the live API.
- **The #36 layout** — 280px rail, search in the rail, pinned Apply/Reset (no "Close"),
  flex-column shell with `min-h-0` instead of the `100dvh` scroller (#44).
- **The #43 fix** — columns derive from a target tile width, so tile size is monotonic.
  The footer readout prints live column count and tile width; resize the window and watch
  it stay stable, which is the bug being fixed.

## What is deliberately fake

No virtual scroller (60 cards, plain grid), filters do not filter, Apply does nothing.
The question is what it *looks* like, not whether it works.

## Verdict — **variant D** (chosen 2026-07-30)

**B "Console" structure and typography + C "Gallery" ink-only palette.**

| | |
|---|---|
| ground light | `oklch(0.975 0.002 260)` |
| ground dark | `oklch(0.135 0.004 260)` |
| `--primary` | **ink** — same as `--foreground`; no accent hue anywhere |
| type | Inter (+ Noto TC/JP/Thai), `ui-monospace` tabular numerics for card numbers |
| radius | `0.5rem` |
| density | ~203px tiles → 6 columns at 1512px |
| card names | on, with card number beneath |

Card art is the only saturated thing on screen.

**The accent question was put and answered: no accent.** Variant E offered one restrained
blue for active/primary state only, on the grounds that `Apply`, the selected colour chips
and #36's per-group "uncommitted edits" markers all lose their signal when `--primary`
equals `--foreground`. D was chosen anyway — so **those three affordances must be carried
by weight, fill and border rather than hue**, and that is now a constraint on #37 and #38
rather than an open question.

A, B, C, E and the switcher are deleted. What remains is D, kept runnable as the build
session's visual target:

```bash
make dev && open http://localhost:3000/tc/prototype-identity
```

Delete this directory and the route once the tokens land in `assets/css/tailwind.css`.
