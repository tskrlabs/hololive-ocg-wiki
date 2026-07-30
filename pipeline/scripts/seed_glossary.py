"""One-time: build `pipeline/glossary/` from the curated web i18n maps and the card data.

The maintainer hand-wrote 216 name translations, 26 set names and 40 tags into
`apps/web/i18n/locales/*.json` over the life of v1. That work is good — `一伊那尓栖` ->
"Ninomae Ina'nis" is not something a model produces reliably — and it is the seed for the
glossary rather than something the rework discards.

What this script does:

1. Takes the **key set from the card data**, not from the i18n files. The data has 296
   card names to i18n's 216, and i18n has one key (`デッキ構築ルール`) that is not a card
   name at all. Keying on the data means every entry corresponds to something real, and
   the gaps are visible as gaps.
2. Fills in each locale's value from the curated maps where one exists.
3. Derives tag entries from `Card.tags` — the unprefixed identity — pairing each with its
   `Translation.tags` display spelling positionally. This is the fix for #26: the filter
   must key on the identity, not the `#`-prefixed display text.

Run once. After that the glossary is the source of truth and is edited directly.

    uv run python pipeline/scripts/seed_glossary.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))

from holo_data.glossary import Entry, Glossary  # noqa: E402

I18N_DIR = REPO_ROOT / "apps" / "web" / "i18n" / "locales"
CARDS_JSON = REPO_ROOT / "pipeline" / "build" / "cards.json"
SOURCE_LOCALE = "ja"
TARGET_LOCALES = ("en", "tc", "ko", "es", "th", "id")


def load_curated() -> dict[str, dict[str, dict[str, str]]]:
    """The existing hand-written maps, as {locale: {kind: {key: value}}}."""
    curated: dict[str, dict[str, dict[str, str]]] = {}
    for locale in TARGET_LOCALES:
        payload = json.loads((I18N_DIR / f"{locale}.json").read_text(encoding="utf-8"))
        curated[locale] = {
            kind: payload.get(kind, {}) for kind in ("names", "sets", "tags")
        }
    return curated


def load_cards() -> list[dict]:
    return json.loads(CARDS_JSON.read_text(encoding="utf-8"))["cards"]


def build_names(cards: list[dict], curated: dict) -> Glossary:
    """One entry per distinct source-locale card name."""
    glossary = Glossary(kind="names")
    for card in cards:
        key = card["translations"][SOURCE_LOCALE]["name"]
        if key not in glossary.entries:
            glossary.entries[key] = Entry(key=key)

    for locale in TARGET_LOCALES:
        source = curated[locale]["names"]
        for key, entry in glossary.entries.items():
            value = source.get(key)
            # A curated value identical to the key is a *decision* ("FUWAMOCO stays as
            # it is"), not a gap, so it is recorded rather than dropped.
            if value:
                entry.translations[locale] = value
    return glossary


def build_sets(cards: list[dict], curated: dict) -> Glossary:
    glossary = Glossary(kind="sets")
    for card in cards:
        for name in card.get("card_sets") or []:
            glossary.entries.setdefault(name, Entry(key=name))

    for locale in TARGET_LOCALES:
        source = curated[locale]["sets"]
        for key, entry in glossary.entries.items():
            if value := source.get(key):
                entry.translations[locale] = value
    return glossary


def build_tags(cards: list[dict], curated: dict) -> Glossary:
    """Tag entries keyed on `Card.tags` — the unprefixed identity.

    The display spelling comes from `Translation.tags`, which pairs positionally with
    `Card.tags` (verified: zero cards disagree on list length across all 7 locales). The
    curated map is consulted too, since its keys are already unprefixed.

    Where a locale's cards disagree on the display spelling — 6 identities in `en`, 17 in
    `ko` — the most common wins, with the text itself breaking ties so the output is
    deterministic. Those are exactly the inconsistencies this rework exists to remove;
    recording the majority now gives the maintainer something concrete to review.
    """
    display: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    glossary = Glossary(kind="tags")

    for card in cards:
        identity = card.get("tags") or []
        for locale, translation in card["translations"].items():
            shown = translation.get("tags") or []
            if len(identity) != len(shown):
                continue
            for key, text in zip(identity, shown):
                glossary.entries.setdefault(key, Entry(key=key))
                display[key][locale][text] += 1

    for locale in TARGET_LOCALES:
        curated_map = curated[locale]["tags"]
        for key, entry in glossary.entries.items():
            if value := curated_map.get(key):
                entry.translations[locale] = value
                continue
            counts = display[key].get(locale)
            if counts:
                entry.translations[locale] = max(
                    counts.items(), key=lambda item: (item[1], item[0])
                )[0]
    return glossary


def main() -> int:
    if not CARDS_JSON.exists():
        print(f"no build at {CARDS_JSON} — run `holo-data build` first", file=sys.stderr)
        return 1

    cards = load_cards()
    curated = load_curated()

    built = {
        "names": build_names(cards, curated),
        "sets": build_sets(cards, curated),
        "tags": build_tags(cards, curated),
    }

    for kind, glossary in built.items():
        path = glossary.save()
        print(f"→ {kind}: {len(glossary.entries)} entries -> {path}")
        for locale in TARGET_LOCALES:
            decided, total = glossary.coverage(locale)
            gap = total - decided
            note = f"  ⚠ {gap} undecided" if gap else ""
            print(f"    {locale}: {decided}/{total}{note}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
