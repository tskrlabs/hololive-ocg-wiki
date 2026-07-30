"""Generate the web app's proper-noun maps from `pipeline/glossary/`.

DO NOT EDIT `names`, `sets` or `tags` in `apps/web/i18n/locales/*.json` — this script
overwrites them. Edit `pipeline/glossary/*.json` instead and re-run `make generate`.

Every other key in those files is UI copy ("No results found.", "Deck Name") and is left
untouched: this rewrites exactly three top-level keys per locale and preserves the rest,
including their order.

**Why generate rather than maintain by hand.** The same 296 names are needed in three
places — the pipeline masks with them, `build` labels filter dropdowns with them, and the
site displays them. Three hand-maintained copies is three chances to drift, and the drift
is invisible: a name the site translates but the pipeline does not mask is exactly the
inconsistency #20 records.

`make check` fails if the generated maps are stale, the same guard the card contract and
the D1 DDL already use.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))

from holo_data.glossary import KINDS, load_all  # noqa: E402

I18N_DIR = REPO_ROOT / "apps" / "web" / "i18n" / "locales"

# The site serves these; `ja` is the source locale and displays the keys themselves.
LOCALES = ("ja", "en", "tc", "ko", "es", "th", "id")


def render(locale: str, glossaries: dict) -> dict[str, dict[str, str]]:
    """The three maps for one locale.

    `ja` gets identity maps — the keys *are* the Japanese text — so the frontend's
    lookup succeeds in every locale and never has to special-case the source language.
    """
    return {
        kind: {
            key: (key if locale == "ja" else entry.display(locale))
            for key, entry in sorted(glossaries[kind].entries.items())
        }
        for kind in KINDS
    }


def update_locale_file(path: Path, maps: dict[str, dict[str, str]]) -> bool:
    """Replace the three generated keys in one locale file. Returns True if it changed.

    Key order is preserved by rebuilding the dict in the original order and substituting
    values in place, so the diff shows only what actually changed rather than a
    reordering of 74 keys.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))

    rebuilt = {}
    for key, value in payload.items():
        rebuilt[key] = maps[key] if key in KINDS else value
    # A locale file that never had one of these keys still gets it.
    for kind in KINDS:
        if kind not in rebuilt:
            rebuilt[kind] = maps[kind]

    text = json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n"
    if path.read_text(encoding="utf-8") == text:
        return False

    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    check_only = "--check" in sys.argv
    glossaries = load_all()
    if not any(g.entries for g in glossaries.values()):
        print(
            "pipeline/glossary/ is empty — nothing to generate.\n"
            "Seed it with `uv run python pipeline/scripts/seed_glossary.py`.",
            file=sys.stderr,
        )
        return 1

    missing = [loc for loc in LOCALES if not (I18N_DIR / f"{loc}.json").exists()]
    if missing:
        # Hard failure, not a skip. An earlier version of this script had the repo root
        # off by one directory, found no locale files at all, and reported "already
        # current" — a generator that succeeds when it generated nothing is invisible to
        # the staleness check that is supposed to catch exactly this.
        print(
            f"missing locale file(s) under {I18N_DIR}: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    changed = []
    for locale in LOCALES:
        path = I18N_DIR / f"{locale}.json"
        maps = render(locale, glossaries)
        if check_only:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if any(payload.get(kind) != maps[kind] for kind in KINDS):
                changed.append(locale)
        elif update_locale_file(path, maps):
            changed.append(locale)

    counts = ", ".join(f"{k} {len(glossaries[k].entries)}" for k in KINDS)

    if check_only:
        if changed:
            print(
                f"✗ i18n maps are stale in: {', '.join(changed)}\n"
                "  run `make generate` — they are derived from pipeline/glossary/",
                file=sys.stderr,
            )
            return 1
        print(f"✓ i18n maps current ({counts})")
        return 0

    print(f"i18n maps from glossary ({counts})")
    print(f"  {len(changed)} locale file(s) updated" if changed else "  already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
