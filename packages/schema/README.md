# `@holo/schema` — the card contract

The card shape, defined **once**, as pydantic models. The JSON Schema, the TypeScript
types, and (from Phase 3) the D1 DDL are all generated from them.

See [ADR 0001](../../docs/adr/0001-card-contract-generation.md) for why, including the
five drift bugs in v1 that this prevents.

## Layout

```
src/holo_schema/        ← the source of truth. Edit here.
  enums.py              closed enums, each derived by census over 2,448 real cards
  card.py               Card — canonical: snake_case, all 7 locales
  localized.py          LocalizedCard — the API response shape
  localize.py           the projection Card -> LocalizedCard (reference impl)
  annotations.py        Column/Blob/FullText markers for the Phase 3 DDL emitter

src/localize.ts         ← TypeScript port of localize.py. The Worker runs this.

scripts/
  generate.py           models -> json-schema/ -> dist/
  build_fixtures.py     selects the fixture card set from `holo-data build` output
  golden.py             writes the parity fixtures from the Python reference

json-schema/  dist/  golden/     ← GENERATED AND COMMITTED. Do not hand-edit.
tests/
```

## Working on it

```bash
make generate      # after editing any model
make golden        # after changing localize() behaviour deliberately
make check         # verify everything (also runs pre-commit if you ran `make hooks`)
```

Editing a model without regenerating is the failure this package exists to prevent —
`make check` fails if the committed output is stale.

**If you change `localize.py`, change `localize.ts` in the same commit.** The golden
files will fail the parity test otherwise, which is the point.

## Consuming it

**TypeScript** (types only, no runtime dependency):

```ts
import type { Card, LocalizedCard } from "@holo/schema";
import { RARITIES, FUSED_COLORS, DEFAULT_LOCALE } from "@holo/schema/enums";
import { localize, cardImage } from "@holo/schema/localize";
```

**Python:**

```python
from holo_schema import Card, CardCollection, localize

collection = CardCollection.model_validate_json(raw)
api_shape = localize(collection.cards[0], "en")
```

## Two shapes, not one

`Card` is canonical — all 7 locales, nested. `LocalizedCard` is what the API returns —
one locale, flattened. `localize()` is the only thing that converts between them, and it
exists in both languages because the pipeline is Python (D3) while the Worker is
TypeScript (D8). `tests/localize.test.ts` asserts the two agree, byte for byte, across
every fixture card in every locale.

## Gotchas the data forced

- **`blue_red` is not `["blue","red"]`.** It is a single fused symbol as printed on the
  card, with its own icon asset. Both encodings exist in the data and mean different
  things. Never normalise one into the other. Use `FUSED_COLORS` for filter expansion.
- **`card_number` is not unique.** 2,448 cards share 1,228 numbers — rarity variants of
  one card all carry the same number. `id` is the only unique key.
- **Absent fields are omitted, never null.** Serialise with `exclude_none=True`; the
  generated TypeScript says `hp?: number`, not `hp?: number | null`.
- **Arts pair by index** between `Card.arts` and `Translation.arts`, and the translated
  list can be shorter (hSD03-009, hSD04-009 in `en`). Both are fixtures.
- **`oshi_skill` has no `cost`.** v1 declared one in three places; no card ever had it.
