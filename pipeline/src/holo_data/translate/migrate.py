"""Migrating the per-card cache into the content-addressed one.

Only **Q&A** is migrated. Everything else is re-translated cold, because re-keying the
existing cache by content puts conflicting values in the same slot:

| kind | `en` slots | conflicting |
|---|---:|---:|
| qa | 596 | 528 (89%) |
| keyword_effect | 524 | 432 (82%) |
| art_effect | 405 | 336 (83%) |
| ability_text | 224 | 170 (76%) |
| art_name | 926 | 362 (39%) |
| card_name | 296 | 83 (28%) |

Of `en`'s 2,277 conflicts, only 271 are `{source, one translation}` — the case a rule can
settle. The other 2,006 hold two or more genuinely different translations, and picking
between them is a coin flip that would then become the canonical answer for every card
carrying that string.

**Q&A is migrated despite being the worst offender at 89%**, for three reasons. It is 62%
of the source corpus by character count, so re-translating it dominates the bill. It is
the least read — official rules clarifications in a detail panel. And the Japanese is
authoritative anyway, so a merely-adequate translation is not the same kind of loss as a
character's name being wrong.

Migrated entries are marked `source: "legacy"` so a later pass can find exactly them.
Without a distinct provenance, "which entries are still old-prompt output?" is
unanswerable a month from now.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .cache import TranslationCache
from .cache_v2 import TranslationCacheV2
from .units import QA_KIND, Unit, unit_hash


@dataclass
class MigrationReport:
    """What a migration did, per locale."""

    migrated: dict[str, int] = field(default_factory=dict)
    conflicted: dict[str, int] = field(default_factory=dict)
    unmatched: dict[str, int] = field(default_factory=dict)

    def lines(self) -> list[str]:
        out = []
        for locale in sorted(self.migrated):
            migrated = self.migrated[locale]
            conflicts = self.conflicted.get(locale, 0)
            unmatched = self.unmatched.get(locale, 0)
            detail = []
            if conflicts:
                detail.append(f"{conflicts} had conflicting values")
            if unmatched:
                detail.append(f"{unmatched} units had no v1 entry")
            suffix = f" ({'; '.join(detail)})" if detail else ""
            out.append(f"  {locale}: {migrated} Q&A units migrated{suffix}")
        return out


def _pick_winner(candidates: Counter, source_value: Any) -> Any:
    """Choose one translation from the several a unit accumulated under v1.

    Rules, in order:

    1. Anything that differs from the untranslated source beats a passthrough — a card
       whose Q&A was never translated should not win over one that was.
    2. Then the most common, since agreement between independent translations is weak
       evidence of correctness.
    3. Then the serialised text, so the result does not depend on dict ordering. The
       cache is content-diffed on publish, and a winner that varied per run would upload
       a "changed" file every build.

    This is a coin flip dressed up, and it is used *only* for Q&A — see the module
    docstring for why that is acceptable there and nowhere else.
    """
    import json

    source_text = json.dumps(source_value, ensure_ascii=False, sort_keys=True)
    return max(
        candidates.items(),
        key=lambda item: (item[0] != source_text, item[1], item[0]),
    )[0]


def migrate_qa(
    v1: TranslationCache,
    v2: TranslationCacheV2,
    units: dict[str, Unit],
    cards: list[dict[str, Any]],
    locales: list[str],
) -> MigrationReport:
    """Fold v1's per-card Q&A translations into content-addressed `legacy` entries.

    Args:
        v1: the per-card cache.
        v2: the cache to write into.
        units: every unit in the build, keyed by content address.
        cards: the build, for mapping card ids and indices back to source values.
        locales: which locales to migrate.

    Returns:
        A report naming, per locale, how many units were migrated and how many had
        conflicting candidates.
    """
    import json

    report = MigrationReport()
    qa_units = {key: unit for key, unit in units.items() if unit.kind == QA_KIND}

    # Where does each Q&A source value live in v1? `(card_id, "qa_items[i]")`, possibly
    # many places for one unit — that multiplicity is the whole point.
    locations: dict[str, list[tuple[str, str]]] = {}
    for card in cards:
        translation = (card.get("translations") or {}).get("ja") or {}
        for index, qa in enumerate(translation.get("qa_items") or []):
            if not isinstance(qa, dict):
                continue
            key = f"{QA_KIND}:{unit_hash(qa)}"
            if key in qa_units:
                locations.setdefault(key, []).append(
                    (card["id"], f"qa_items[{index}]")
                )

    for locale in locales:
        migrated = conflicted = unmatched = 0

        for key, unit in qa_units.items():
            candidates: Counter = Counter()
            for card_id, field_path in locations.get(key, []):
                entry = v1.get(locale, card_id, field_path)
                if entry is None or entry.source_hash != unit_hash(unit.value):
                    continue
                candidates[json.dumps(entry.value, ensure_ascii=False, sort_keys=True)] += 1

            if not candidates:
                unmatched += 1
                continue

            if len(candidates) > 1:
                conflicted += 1

            winner = _pick_winner(candidates, unit.value)
            v2.put(locale, unit, json.loads(winner), source="legacy")
            migrated += 1

        report.migrated[locale] = migrated
        report.conflicted[locale] = conflicted
        report.unmatched[locale] = unmatched

    return report


def conflict_census(
    v1: TranslationCache,
    units: dict[str, Unit],
    cards: list[dict[str, Any]],
    locale: str,
) -> dict[str, tuple[int, int]]:
    """Per kind: (slots that v1 can fill, slots where it holds conflicting values).

    The measurement behind the decision not to migrate. Kept as code rather than a note
    in a commit message so the claim can be re-checked against a future build — if a
    later refresh brought the conflict rate to near zero, migrating would become the
    better option and this is how that would be noticed.
    """
    import json

    # Map every unit to the v1 locations that could fill it.
    locations: dict[str, list[tuple[str, str]]] = {}

    def record(key: str, card_id: str, path: str) -> None:
        locations.setdefault(key, []).append((card_id, path))

    from .units import iter_fields, unit_key

    for card in cards:
        translation = (card.get("translations") or {}).get("ja") or {}
        card_id = card["id"]

        # Rebuild v1's field paths alongside v2's kinds. They disagree on tags — v1
        # stores the whole list under one key, v2 stores each tag — so tags have no
        # per-unit v1 entry and are counted as unfillable rather than silently skipped.
        if name := translation.get("name"):
            record(unit_key("card_name", name), card_id, "name")
        for field_name in ("ability_text", "extra"):
            if value := translation.get(field_name):
                record(unit_key(field_name, value), card_id, field_name)
        for index, art in enumerate(translation.get("arts") or []):
            if not isinstance(art, dict):
                continue
            if value := art.get("name"):
                record(unit_key("art_name", value), card_id, f"arts[{index}].name")
            if value := art.get("effect"):
                record(unit_key("art_effect", value), card_id, f"arts[{index}].effect")
        keyword = translation.get("keyword")
        if isinstance(keyword, dict):
            if value := keyword.get("name"):
                record(unit_key("keyword_name", value), card_id, "keyword.name")
            if value := keyword.get("effect"):
                record(unit_key("keyword_effect", value), card_id, "keyword.effect")
        for skill_key in ("oshi_skill", "sp_oshi_skill"):
            skill = translation.get(skill_key)
            if not isinstance(skill, dict):
                continue
            if value := skill.get("name"):
                record(unit_key("skill_name", value), card_id, f"{skill_key}.name")
            if value := skill.get("effect"):
                record(unit_key("skill_effect", value), card_id, f"{skill_key}.effect")
            if value := skill.get("timing"):
                record(unit_key("skill_timing", value), card_id, f"{skill_key}.timing")
        for index, qa in enumerate(translation.get("qa_items") or []):
            if isinstance(qa, dict):
                record(unit_key(QA_KIND, qa), card_id, f"qa_items[{index}]")

    census: dict[str, tuple[int, int]] = {}
    for key, unit in units.items():
        candidates = {
            json.dumps(entry.value, ensure_ascii=False, sort_keys=True)
            for card_id, path in locations.get(key, [])
            if (entry := v1.get(locale, card_id, path)) is not None
            and entry.source_hash == unit_hash(unit.value)
        }
        if not candidates:
            continue
        fillable, conflicting = census.get(unit.kind, (0, 0))
        census[unit.kind] = (fillable + 1, conflicting + (1 if len(candidates) > 1 else 0))

    return census
