# Captured card identity

`id-to-image-key-20260826.json` is a snapshot of `id -> image_key` as production D1 held it
**before** the 2026-08-26 renumbering, taken while investigating
[#83](https://github.com/tskrlabs/hololive-ocg-wiki/issues/83).

**It is committed because it cannot be regenerated.** The official site reused card ids: 82
cards kept their `card_number` and artwork and were handed a different `?id=`. Once D1 is
seeded with the new ids, nothing anywhere records which card an old id used to mean — and
saved decks are stored *as ids*, in `localStorage` and inside shared deck-code URLs. This
file is the only bridge from a deck saved before that date to the card it actually names.

Verified total at capture: 2,650 rows, 2,650 distinct `image_key`s, and every one of them
still present in the 2,686-card build. No card was removed, so every old deck reference
resolves exactly rather than approximately.

This is data, not a cache. `holo-data` never writes here, and nothing regenerates it. Do not
delete it once #83 lands — decks in the wild outlive the migration that reads this, and a
deck code pasted in 2027 still needs it.
