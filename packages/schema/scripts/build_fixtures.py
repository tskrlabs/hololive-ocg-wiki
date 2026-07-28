"""Select the fixture card set from v1's data.

Fixtures serve two purposes at once (decision: one corpus, not two):

1. **Credential-free local dev** (D14) — a fresh clone seeds a local D1 from these and
   runs the whole site with no Cloudflare account. That property is what separates
   "public repo" from "contributor-ready repo".
2. **The golden-file corpus** for the localize() parity test — every edge case the
   contract has to handle is pinned by a test rather than living in someone's memory.

Selection is by *coverage*, not by "the first 40 cards": at least one card for every
enum member and every structural edge case found by census over all 2,448 cards. The
resulting id list is committed to `fixtures/card-ids.txt`, so the selection is
reproducible and reviewable — a PR that changes which cards are fixtures shows up as a
diff, not as a silently different corpus.

    make fixtures       # re-select from v1 data and rewrite fixtures/

Once Phase 1 lands, this reads from `holo-data build` output instead of v1's cards.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from v1_adapter import load_v1_cards  # noqa: E402

from holo_schema import (  # noqa: E402
    BLOOM_LEVEL_VALUES,
    CARD_TYPE_VALUES,
    COLOR_VALUES,
    KEYWORD_TYPE_VALUES,
    RARITY_VALUES,
    TIMING_VALUES,
    Card,
    CardCollection,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "fixtures"
DEFAULT_SOURCE = Path(
    "/Users/chingli/lichingchester/projects/hololive-ocg-wiki/data/cards.json"
)

# Cards that must be in the fixture set regardless of what coverage selection picks,
# because they are the specific anomalies the contract has to survive. Each is a bug
# that would otherwise only be discovered in production.
PINNED: dict[str, str] = {
    "446": "hSD03-009 — 2 arts but 0 `en` translated arts (short-list zip)",
    "447": "hSD04-009 — same arts-length mismatch",
    "1877": "hBP07-091 — cardTypeCode 'unknown' (scraper could not classify)",
    "2003": "hBP07-091 — the other 'unknown', different rarity",
    "2444": "hBP01-028 HR — rarity missing from v1's TypeScript union",
    # Selected when the corpus came from v1, to cover an `arts[].value` field the
    # contract no longer models (F-003). Pinned rather than dropped because removing it
    # means hand-editing the generated corpus, and this generator cannot currently run
    # (it selects from v1 data through a contract that has moved on). The repaired
    # generator does not select this card; see the fixture-toolchain finding.
    "2164": "hBP03-011 P — was `arts[].value`; kept until the generator is repaired",
    "2138": "hBP03-044 SR (hCO01 reprint) — image_key collision pair A",
    "726": "hBP03-044 SR (hBP03 original) — image_key collision pair B",
    "2139": "hBP03-055 SR (hCO01 reprint) — image_key collision pair C",
    "735": "hBP03-055 SR (hBP03 original) — image_key collision pair D",
    "1218": "hBP05-040 miComet — genuine two-element colour array ['red','blue']",
    "2263": "hBP08-060 FUWAMOCO — fused colour code 'blue_red'",
    "614": "hBP03-050 FUWAMOCO — second fused-colour card, different set",
}


def _coverage_rules() -> list[tuple[str, Callable[[Card], bool]]]:
    """One rule per thing that must appear at least once in the fixture set."""
    rules: list[tuple[str, Callable[[Card], bool]]] = []

    for value in CARD_TYPE_VALUES:
        rules.append((f"card_type={value}", lambda c, v=value: c.card_type_code == v))
    for value in RARITY_VALUES:
        rules.append((f"rarity={value}", lambda c, v=value: c.rarity_code == v))
    for value in BLOOM_LEVEL_VALUES:
        rules.append((f"bloom={value}", lambda c, v=value: c.bloom_level_code == v))
    for value in COLOR_VALUES:
        rules.append(
            (f"color={value}", lambda c, v=value: v in (c.color_codes or []))
        )
    for value in KEYWORD_TYPE_VALUES:
        rules.append(
            (
                f"keyword={value}",
                lambda c, v=value: c.keyword is not None and c.keyword.type_code == v,
            )
        )
    for value in TIMING_VALUES:
        rules.append(
            (
                f"timing={value}",
                lambda c, v=value: (
                    (c.oshi_skill is not None and c.oshi_skill.timing_code == v)
                    or (c.sp_oshi_skill is not None and c.sp_oshi_skill.timing_code == v)
                ),
            )
        )

    # Structural coverage — shapes rather than values.
    rules += [
        ("has_life", lambda c: c.life is not None),
        ("has_oshi_skill", lambda c: c.oshi_skill is not None),
        ("has_sp_oshi_skill", lambda c: c.sp_oshi_skill is not None),
        ("has_arts", lambda c: bool(c.arts)),
        ("has_multi_arts", lambda c: len(c.arts or []) > 1),
        (
            "has_special_arts",
            lambda c: any(a.special_targets for a in (c.arts or [])),
        ),
        ("has_is_plus", lambda c: any(a.is_plus for a in (c.arts or []))),
        ("has_baton_touch", lambda c: c.baton_touch_count is not None),
        ("has_illustrator", lambda c: c.illustrator is not None),
        ("has_card_tags", lambda c: bool(c.tags)),
        ("no_card_tags", lambda c: not c.tags),
        ("no_colors", lambda c: not c.color_codes),
        ("multi_sets", lambda c: len(c.card_sets) > 1),
        ("many_sets", lambda c: len(c.card_sets) >= 8),
        (
            "has_ability_text",
            lambda c: any(t.ability_text for t in c.translations.values()),
        ),
        ("has_extra", lambda c: any(t.extra for t in c.translations.values())),
        ("has_qa_items", lambda c: any(t.qa_items for t in c.translations.values())),
        (
            "has_qa_related_cards",
            lambda c: any(
                q.related_cards
                for t in c.translations.values()
                for q in (t.qa_items or [])
            ),
        ),
    ]
    return rules


def select(cards: list[Card]) -> tuple[list[Card], dict[str, str]]:
    """Pick the smallest greedy set covering every rule, plus the pinned anomalies.

    Deterministic: cards are considered in id order, and the first card satisfying an
    uncovered rule wins. Re-running on unchanged input produces an identical list.
    """
    by_id = {card.id: card for card in cards}
    chosen: dict[str, str] = {}

    for card_id, reason in PINNED.items():
        if card_id in by_id:
            chosen[card_id] = reason
        else:
            print(f"  warning: pinned card {card_id} not found in source", file=sys.stderr)

    ordered = sorted(cards, key=lambda c: int(c.id))

    for label, predicate in _coverage_rules():
        if any(predicate(by_id[cid]) for cid in chosen):
            continue
        for card in ordered:
            if predicate(card):
                chosen.setdefault(card.id, f"covers {label}")
                break
        else:
            print(f"  warning: no card covers {label}", file=sys.stderr)

    selected = sorted(
        (by_id[cid] for cid in chosen), key=lambda c: int(c.id)
    )
    return selected, chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="v1 cards.json to select from",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"source not found: {args.source}", file=sys.stderr)
        print(
            "Pass --source, or skip: fixtures/ is committed and only needs rebuilding "
            "when the selection rules change.",
            file=sys.stderr,
        )
        return 1

    raw = load_v1_cards(args.source)
    cards = [Card.model_validate(entry) for entry in raw]
    print(f"  loaded {len(cards)} cards from {args.source}")

    selected, reasons = select(cards)
    print(f"  selected {len(selected)} fixture cards")

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    collection = CardCollection(
        generated_at="2026-07-25T00:00:00Z",
        cards=selected,
    )
    payload = collection.model_dump(mode="json", exclude_none=True)
    (FIXTURE_DIR / "cards.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# Fixture card selection — regenerate with `make fixtures`.",
        "#",
        "# Chosen for coverage: every enum member and every structural edge case found",
        "# by census over all 2,448 cards. Committed so the selection is reviewable.",
        "#",
        "# <card id>  <why this card is here>",
        "",
    ]
    for card in selected:
        lines.append(f"{card.id:>6}  {reasons[card.id]}")
    (FIXTURE_DIR / "card-ids.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    size_kb = (FIXTURE_DIR / "cards.json").stat().st_size / 1024
    print(f"  wrote fixtures/cards.json ({size_kb:.0f} KB)")
    print(f"  wrote fixtures/card-ids.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
