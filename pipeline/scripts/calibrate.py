"""Calibration: prove the per-kind prompts work before spending the quota on them.

Phase 4 of #23 is a **spend gate** (#24). Nothing bulk runs until the output here is
reviewed, because the whole rework rests on an untested premise: that a per-kind prompt
with masked names produces consistently good translations.

What this does:

1. Takes a small, deliberately hard sample from each kind — strings the issues name, and
   strings where the current cache holds several different answers.
2. Runs them through the real batcher, the real prompts and the real API.
3. Reports every result beside its Japanese source, and beside what the *old* pipeline
   produced for the same string, so quality is a comparison rather than an impression.

It writes nothing to the cache. The output is for reading.

    uv run python pipeline/scripts/calibrate.py --locale en
    uv run python pipeline/scripts/calibrate.py --all       # all six locales
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "pipeline" / ".env")

from holo_data.glossary import Glossary  # noqa: E402
from holo_data.translate.mask_table import Restorer, combined_table  # noqa: E402
from holo_data.translate import units as U  # noqa: E402
from holo_data.translate.batcher import build_batches, collect_result, parse_reply  # noqa: E402
from holo_data.translate.cache import TranslationCache  # noqa: E402
from holo_data.translate.poe import DEFAULT_MODEL, RateLimiter  # noqa: E402
from holo_data.translate.prompts_v2 import LOCALE_NAMES  # noqa: E402
from holo_data.translate.runner import POE_BASE_URL, _send  # noqa: E402

CARDS_JSON = REPO_ROOT / "pipeline" / "build" / "cards.json"

# How many units to sample per kind. Small enough to read in one sitting, large enough
# that a systematic problem shows up rather than hiding behind one lucky example.
SAMPLE_PER_KIND = 6

# Q&A is excluded from the cold run (D6), so it is excluded here too — calibrating a
# prompt that will not be used costs quota and proves nothing.
SKIP_KINDS = {"qa"}


def old_translations(
    v1: TranslationCache, cards: list[dict], locale: str
) -> dict[str, Counter]:
    """What the *old* pipeline produced for each source string.

    The comparison that makes the calibration meaningful: a new translation that reads
    well is good, and a new translation that replaces four different old ones with one is
    the point of the whole rework.
    """
    from holo_data.translate.units import unit_key

    found: dict[str, Counter] = {}

    def record(key: str, card_id: str, path: str) -> None:
        entry = v1.get(locale, card_id, path)
        if entry is not None:
            found.setdefault(key, Counter())[
                json.dumps(entry.value, ensure_ascii=False)
            ] += 1

    for card in cards:
        translation = (card.get("translations") or {}).get("ja") or {}
        card_id = card["id"]
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

    return found


def pick_sample(units: dict[str, U.Unit], old: dict[str, Counter]) -> list[U.Unit]:
    """The hardest units, not a random draw.

    Ranked by how badly the old pipeline disagreed with itself: a string with four
    different `en` translations is exactly what this rework claims to fix, so it is what
    calibration should look at. Ties break on occurrence count, then the key, so the
    sample is the same on every run and two calibrations are comparable.
    """
    by_kind: dict[str, list[U.Unit]] = {}
    for key, unit in units.items():
        if unit.kind in SKIP_KINDS:
            continue
        by_kind.setdefault(unit.kind, []).append(unit)

    sample: list[U.Unit] = []
    for kind in sorted(by_kind):
        ranked = sorted(
            by_kind[kind],
            key=lambda u: (-len(old.get(u.key, ())), -u.occurrences, u.key),
        )
        sample.extend(ranked[:SAMPLE_PER_KIND])
    return sample


async def calibrate(
    locale: str, sample: list[U.Unit], table: list, restorer: Restorer, old: dict
) -> dict:
    import openai

    client = openai.AsyncOpenAI(
        api_key=__import__("os").getenv("POE_API_KEY"), base_url=POE_BASE_URL
    )
    limiter = RateLimiter()
    batches = build_batches(sample, locale, table)

    print(f"\n{'=' * 78}\n{locale} ({LOCALE_NAMES.get(locale, locale)}) — "
          f"{len(sample)} units in {len(batches)} call(s)\n{'=' * 78}")

    totals = {"prompt_tokens": 0, "completion_tokens": 0}
    stats = {"units": 0, "ok": 0, "failed": 0, "still_japanese": 0, "consolidated": 0}

    for batch in batches:
        reply, usage = await _send(client, batch, limiter, DEFAULT_MODEL, 3)
        totals["prompt_tokens"] += usage["prompt_tokens"]
        totals["completion_tokens"] += usage["completion_tokens"]

        if reply is None:
            print(f"\n--- {batch.kind} --- BATCH FAILED")
            stats["failed"] += batch.size
            continue

        result = collect_result(batch, reply, restorer)
        print(f"\n--- {batch.kind} ---")

        for item in batch.items:
            stats["units"] += 1
            source = item.unit.value
            new = result.translations.get(item.unit.key)
            if new is None:
                stats["failed"] += 1
                print(f"  ✗ {source!r}\n      REJECTED")
                continue

            stats["ok"] += 1
            variants = old.get(item.unit.key, Counter())
            if len(variants) > 1:
                stats["consolidated"] += 1

            # Did the model leave Japanese in a locale that should not have any?
            if locale != "ja" and isinstance(new, str):
                import re

                if re.search(r"[ぁ-んァ-ヶ]", new):
                    stats["still_japanese"] += 1

            masked_note = (
                f"  [masked: {list(item.masked.surfaces.values())}]"
                if item.masked.is_masked
                else ""
            )
            print(f"  {source!r}")
            print(f"    NEW  {new!r}{masked_note}")
            if variants:
                shown = [json.loads(v) for v, _ in variants.most_common(3)]
                label = f"OLD  ({len(variants)} different)" if len(variants) > 1 else "OLD "
                print(f"    {label} {shown}")

    print(f"\n  {locale}: {stats['ok']}/{stats['units']} translated, "
          f"{stats['failed']} rejected, {stats['still_japanese']} left Japanese, "
          f"{stats['consolidated']} replaced multiple old variants")
    print(f"  tokens: {totals['prompt_tokens']:,} in / {totals['completion_tokens']:,} out")

    return {"locale": locale, **stats, **totals}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", default="en")
    parser.add_argument("--all", action="store_true", help="every target locale")
    args = parser.parse_args()

    if not CARDS_JSON.exists():
        print(f"no build at {CARDS_JSON}", file=sys.stderr)
        return 1

    cards = json.loads(CARDS_JSON.read_text(encoding="utf-8"))["cards"]
    units = U.collect(cards)
    names = Glossary.load("names")
    tags = Glossary.load("tags")
    table = combined_table(names, tags)
    restorer = Restorer(names, tags)
    v1 = TranslationCache.load()
    print(f"mask table: {len(table)} entries ({len(names.entries)} names + {len(tags.entries)} tags)")

    locales = list(LOCALE_NAMES) if args.all else [args.locale]
    summaries = []

    for locale in locales:
        old = old_translations(v1, cards, locale)
        sample = pick_sample(units, old)
        summaries.append(asyncio.run(calibrate(locale, sample, table, restorer, old)))

    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    total_tokens = 0
    for summary in summaries:
        tokens = summary["prompt_tokens"] + summary["completion_tokens"]
        total_tokens += tokens
        print(
            f"  {summary['locale']}: {summary['ok']}/{summary['units']} ok, "
            f"{summary['failed']} rejected, {summary['still_japanese']} left Japanese, "
            f"{summary['consolidated']} consolidated, {tokens:,} tokens"
        )
    print(f"\n  total: {total_tokens:,} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
