"""Diff a build against v1's published data.

This is what proves Phase 1's done-criterion: `holo-data build` reproduces today's card
*data* (amended from "shape" — the canonical artifact is snake_case now, so a byte-diff
would show every key renamed and tell you nothing).

Kept permanently rather than deleted once green. It is the only tool that answers "did a
site change break my scraper?" against a known-good 2,448-card baseline. The official
site's markup *will* change — `extract.py` holds 30+ selectors tuned to it — and when it
does this reports which fields stopped parsing, instead of `illustrator` quietly going
empty for six months.

The baseline is v1's `cards.json` (22 MB), passed with `--baseline`. It is not committed:
per D1 data lives outside git, and `verify` is inherently a maintainer tool — an outside
contributor cannot run `scrape` or `translate` anyway (D14).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# v1 emitted camelCase; the contract is snake_case. These are *expected* differences,
# not drift, so they are normalised away before comparing.
_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")
_PASSTHROUGH = {"qa_items", "related_cards", "raw_html", "card_number", "_source_hash"}


def snake(key: str) -> str:
    if key in _PASSTHROUGH:
        return key
    return _CAMEL.sub("_", key).lower()


def normalise(value: Any) -> Any:
    """Recursively snake_case keys and drop translator bookkeeping."""
    if isinstance(value, dict):
        return {
            snake(key): normalise(item)
            for key, item in value.items()
            if key != "_source_hash"
        }
    if isinstance(value, list):
        return [normalise(item) for item in value]
    return value


# Fields that are *expected* to differ, with why. Anything outside this set that differs
# is real drift and gets reported.
EXPECTED_DIFFERENCES = {
    "image_path": "replaced by image_key (D9 — store the key, compose the URL)",
    "image_url": "renamed to source_image_url",
    "image_key": "new in v2, derived from the official URL's set folder",
    "source_image_url": "renamed from image_url",
}


@dataclass
class VerifyReport:
    baseline_count: int = 0
    build_count: int = 0
    missing_ids: list[str] = field(default_factory=list)
    extra_ids: list[str] = field(default_factory=list)
    field_diffs: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    locale_diffs: dict[str, Counter] = field(
        default_factory=lambda: defaultdict(Counter)
    )

    @property
    def common_count(self) -> int:
        return min(self.baseline_count, self.build_count) - len(self.missing_ids)

    @property
    def is_clean(self) -> bool:
        return not self.missing_ids and not self.field_diffs and not self.locale_diffs


def compare(baseline_path: Path, built: dict[str, Any]) -> VerifyReport:
    """Compare a built collection against v1's `cards.json`.

    Args:
        baseline_path: v1's cards.json.
        built: the output of `CardCollection.model_dump(mode="json", exclude_none=True)`.
    """
    report = VerifyReport()

    baseline_raw = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline = {card["id"]: normalise(card) for card in baseline_raw}
    current = {card["id"]: card for card in built["cards"]}

    report.baseline_count = len(baseline)
    report.build_count = len(current)
    report.missing_ids = sorted(set(baseline) - set(current), key=int)
    report.extra_ids = sorted(set(current) - set(baseline), key=int)

    for card_id in sorted(set(baseline) & set(current), key=int):
        old, new = baseline[card_id], current[card_id]

        for key in (set(old) | set(new)) - {"translations"}:
            if key in EXPECTED_DIFFERENCES:
                continue
            if _json(old.get(key)) != _json(new.get(key)):
                report.field_diffs[key].append(card_id)

        old_translations = old.get("translations", {})
        new_translations = new.get("translations", {})
        for locale in set(old_translations) | set(new_translations):
            old_t = old_translations.get(locale, {})
            new_t = new_translations.get(locale, {})
            for key in set(old_t) | set(new_t):
                if _json(old_t.get(key)) != _json(new_t.get(key)):
                    report.locale_diffs[locale][key] += 1

    return report


def _json(value: Any) -> str:
    """Canonical form for comparison, treating empty and absent as the same thing.

    v1 wrote `"qa_items": []` where the contract omits the key entirely — Phase 0's
    "absent, not null/empty" rule (ADR 0001), which is what lets the generated
    TypeScript say `hp?: number` rather than `hp?: number | null`. That is an expected
    difference on ~1,590 cards per locale, so collapsing it here keeps `verify` reporting
    real drift only.
    """
    if value in (None, [], {}, ""):
        return "<empty>"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
