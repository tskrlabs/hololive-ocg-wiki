"""Generate the golden files that pin `localize()`'s behaviour.

`localize()` exists twice — Python (the reference) and TypeScript (what the Worker
runs). These files are the contract between them: Python writes them, TypeScript
asserts it reproduces them exactly.

Without this, the two implementations drift silently. The TypeScript side gets written
in Phase 4, months of context after the Python side, which is precisely where "I'm sure
I ported that correctly" goes wrong.

    make golden     # regenerate
    make check      # verify both implementations still agree

One file per locale, each holding every fixture card projected into that locale — so a
divergence report names the locale and the card.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from holo_schema import LOCALE_VALUES, CardCollection, localize

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_ROOT.parent.parent
GOLDEN_DIR = PACKAGE_ROOT / "golden"
FIXTURES = REPO_ROOT / "fixtures" / "cards.json"


def main() -> int:
    if not FIXTURES.exists():
        print(f"fixtures not found: {FIXTURES}", file=sys.stderr)
        print("Run `make fixtures` first.", file=sys.stderr)
        return 1

    collection = CardCollection.model_validate_json(FIXTURES.read_text(encoding="utf-8"))
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    for locale in LOCALE_VALUES:
        localized = [localize(card, locale) for card in collection.cards]
        payload = [item.model_dump(mode="json", exclude_none=True) for item in localized]
        path = GOLDEN_DIR / f"localized-{locale}.json"
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"  wrote golden/{path.name} ({len(payload)} cards)")

    print(f"✓ wrote {len(LOCALE_VALUES)} golden files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
