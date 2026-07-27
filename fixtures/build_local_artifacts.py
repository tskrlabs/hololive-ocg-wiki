"""Build the R2 artifacts for local development, from the committed fixtures.

`fixtures.sql` gives a local D1 with no credentials (D12), but the site also reads three
*R2* artifacts — the per-locale filter options, `info.json` and `status.json` — and
nothing produced those locally. `make dev` therefore served a site whose filter dropdowns
404ed in six of seven locales.

The filter options are built with the **pipeline's own `filter_options()`**, not a
reimplementation, so what a contributor sees locally has the same shape as what
`holo-data build` publishes. `status.json` is synthesised: it describes a seeder run that
never happened, over the fixture set, because `seed` only ever writes to production.

Usage: `python3 fixtures/build_local_artifacts.py <output-dir>`
Driven by `apps/api/scripts/seed-local-r2.sh`; not part of the published pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "schema" / "src"))

from holo_data.build import filter_options  # noqa: E402
from holo_schema import CardCollection, LOCALE_VALUES  # noqa: E402


def main(out_dir: Path) -> None:
    raw = json.loads((REPO_ROOT / "fixtures" / "cards.json").read_text("utf-8"))
    collection = CardCollection.model_validate(raw)

    options_dir = out_dir / "filter-options"
    options_dir.mkdir(parents=True, exist_ok=True)
    for locale in LOCALE_VALUES:
        payload = filter_options(collection, locale)
        (options_dir / f"{locale}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # A status report describing the fixture set as though it had just been seeded. Every
    # card counts as "new", which is what a first seed into an empty database looks like.
    cards = collection.cards
    status = {
        "generated_at": raw["generated_at"],
        "built_at": raw["generated_at"],
        "mode": "full",
        "counts": {
            "total": len(cards),
            "new": len(cards),
            "changed": 0,
            "qa_updated": 0,
            "unchanged": 0,
            "removed": 0,
            "missing_from_build": 0,
        },
        "new": [
            {
                "id": card.id,
                "card_number": card.card_number,
                "image_key": card.image_key,
                "name": card.translations["ja"].name if "ja" in card.translations else None,
            }
            for card in cards
        ],
        "changed": [],
        "qa_updated": [],
        "removed": [],
    }
    (out_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"  built {len(LOCALE_VALUES)} filter-options files and status.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_local_artifacts.py <output-dir>")
    main(Path(sys.argv[1]))
