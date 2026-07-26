"""Seed the translation cache from v1's `cards.json`.

**Run this once, before the first `holo-data translate`.** The cache starts empty, so
without it a first run would re-translate all 2,448 cards in 6 locales — paying again
for a year of translations that already exist.

v1's `cards.json` carries every translation inline. This walks it, matches each field to
its cache key, and stores it against the current JP source hash. Tested against the real
file: 81,124 field entries imported, after which `translate --dry-run` reports 2,228 of
2,448 cards already current.

Migration aid, not part of the pipeline. Delete it once the cache is established.

    uv run python -m holo_data.import_v1 --source /path/to/v1/data/cards.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from . import transform
from .translate.cache import TranslationCache, field_keys
from .translate.poe import read_field, target_locales

DEFAULT_SOURCE = Path(
    "/Users/chingli/lichingchester/projects/hololive-ocg-wiki/data/cards.json"
)


def to_v1_key(field_key: str) -> str:
    """Translate a cache key into v1's camelCase path.

    Order matters: `sp_oshi_skill` must be replaced before `oshi_skill`, or it becomes
    `spOshi_skill` and silently matches nothing. That mistake cost 4,140 entries on the
    first attempt.
    """
    return (
        field_key.replace("sp_oshi_skill", "spOshiSkill")
        .replace("oshi_skill", "oshiSkill")
        .replace("ability_text", "abilityText")
    )


def import_translations(source: Path, cache: TranslationCache) -> tuple[int, Counter]:
    """Copy every translation v1 has into the field cache.

    Returns:
        (entries_imported, misses_by_field_type)
    """
    v1_cards = {
        card["id"]: card
        for card in json.loads(source.read_text(encoding="utf-8"))
    }
    cards = transform.load_i18n()
    if not cards:
        raise SystemExit("no cards found — run `holo-data scrape` first")

    imported = 0
    misses: Counter = Counter()

    for card in cards:
        card_id = card["id"]
        jp = card.get("translations", {}).get("ja", {})
        v1_card = v1_cards.get(card_id)
        if not v1_card:
            continue

        for locale in target_locales():
            translation = v1_card.get("translations", {}).get(locale)
            if not translation:
                continue

            for field_key, source_value in field_keys(jp):
                value = read_field(translation, to_v1_key(field_key))
                if value is None:
                    misses[field_key.split("[")[0].split(".")[0]] += 1
                    continue
                cache.put(locale, card_id, field_key, source_value, value)
                imported += 1

    return imported, misses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()

    if not args.source.exists():
        print(f"v1 cards.json not found: {args.source}")
        return 1

    cache = TranslationCache.load()
    imported, misses = import_translations(args.source, cache)
    cache.save()

    print(f"imported {imported} field translations")
    if misses:
        print("fields v1 had no translation for (expected — it never translated these):")
        for field_name, count in misses.most_common(8):
            print(f"  {field_name}: {count}")
    print("\nRun `holo-data translate --dry-run` to see what remains.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
