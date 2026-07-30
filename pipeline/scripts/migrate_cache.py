"""One-time: seed the content-addressed cache from the per-card one.

Migrates **Q&A only** — 596 units per locale, 62% of the source corpus by character
count. Everything else is re-translated cold, because re-keying it by content puts
conflicting values in one slot: 59% of `en`'s fillable slots hold two or more different
translations, and 2,006 of those have no principled winner.

Also applies the four `tc` art names recovered by F-003, which have been waiting since
Phase 0 for a cache with a reviewable surface (#18). Under content addressing each now
covers every card printing that string rather than the one it was stranded on.

Idempotent — re-running produces the same cache, because the winner-picking rule is
deterministic and `manual` entries are rewritten with the same values.

    uv run python pipeline/scripts/migrate_cache.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))

from holo_data.translate import migrate as M  # noqa: E402
from holo_data.translate import units as U  # noqa: E402
from holo_data.translate.cache import TranslationCache  # noqa: E402
from holo_data.translate.cache_v2 import TranslationCacheV2  # noqa: E402

CARDS_JSON = REPO_ROOT / "pipeline" / "build" / "cards.json"
LOCALES = ("en", "tc", "ko", "es", "th", "id")

# F-003: four `tc` art translations the model emitted into a stray `value` key instead of
# replacing `name`. Recorded verbatim in docs/archive/findings.md and deliberately never
# applied — the cache was gitignored, so a correction to it had no reviewable surface and
# would not survive a clone.
#
# Keyed on the *source* string rather than a card id, so each covers every card that
# prints it: `おつルーナ` appears on 3 cards, not the 1 it was stranded on.
F003_TC_ART_NAMES = {
    "おつルーナ": "辛苦啦露娜～",
    "ぐっどないと～": "晚安～",
    "ぬんぬんしよう": "來ぬんぬん吧",
    "あなたの心は…くもりのち晴れ！": "你的心情是……陰轉晴！",
}


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    if not CARDS_JSON.exists():
        print(f"no build at {CARDS_JSON} — run `holo-data build` first", file=sys.stderr)
        return 1

    cards = json.loads(CARDS_JSON.read_text(encoding="utf-8"))["cards"]
    units = U.collect(cards)
    stats = U.stats(units)

    v1 = TranslationCache.load()
    if not v1.entries:
        print("no v1 cache to migrate from", file=sys.stderr)
        return 1

    v2 = TranslationCacheV2.load()

    print(f"→ {stats.distinct} distinct units from {stats.occurrences} occurrences")
    for line in stats.lines():
        print(line)

    print("\n→ conflict census (en), the measurement behind not migrating the rest:")
    census = M.conflict_census(v1, units, cards, "en")
    fillable = conflicting = 0
    for kind in U.ALL_KINDS:
        if kind not in census:
            continue
        can_fill, conflicts = census[kind]
        fillable += can_fill
        conflicting += conflicts
        print(f"  {kind:15s} {conflicts:4d}/{can_fill:4d} conflict ({100 * conflicts / can_fill:3.0f}%)")
    print(f"  {'TOTAL':15s} {conflicting:4d}/{fillable:4d} ({100 * conflicting / fillable:.0f}%)")

    print("\n→ migrating Q&A")
    report = M.migrate_qa(v1, v2, units, cards, list(LOCALES))
    for line in report.lines():
        print(line)

    print("\n→ applying the four F-003 `tc` art names as manual entries")
    for source, translated in F003_TC_ART_NAMES.items():
        unit = units.get(U.unit_key("art_name", source))
        if unit is None:
            print(f"  ✗ {source!r} is no longer an art name in the build")
            continue
        v2.put("tc", unit, translated, source="manual")
        print(f"  ✓ {source!r} -> {translated!r} ({unit.occurrences} occurrences)")

    if dry_run:
        print("\n(dry run — nothing written)")
        return 0

    v2.save()
    print(f"\n✓ wrote {v2.count()} entries")
    print(f"  legacy: {v2.count(source='legacy')}, manual: {v2.count(source='manual')}")

    print("\nper-locale status against the full unit set:")
    for locale in LOCALES:
        print(f"  {v2.status(locale, units.values()).describe()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
