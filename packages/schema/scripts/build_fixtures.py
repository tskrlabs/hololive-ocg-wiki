"""Select the fixture card set from `holo-data build` output.

Fixtures serve two purposes at once (decision: one corpus, not two):

1. **Credential-free local dev** (D14) — a fresh clone seeds a local D1 from these and
   runs the whole site with no Cloudflare account. That property is what separates
   "public repo" from "contributor-ready repo".
2. **The golden-file corpus** for the localize() parity test — every edge case the
   contract has to handle is pinned by a test rather than living in someone's memory.

Selection is by *coverage*, not by "the first 40 cards": at least one card for every
enum member and every structural edge case found by census over the whole card set. The
resulting id list is committed to `fixtures/card-ids.txt`, so the selection is
reproducible and reviewable — a PR that changes which cards are fixtures shows up as a
diff, not as a silently different corpus.

    holo-data transform && holo-data build    # produce the source
    make fixtures                             # re-select and rewrite fixtures/

**The source is v2's own build output** (issue #16). It used to be v1's `cards.json`,
read through a `v1_adapter.py` that translated camelCase and patched two card types — a
hardcoded absolute path into a checkout that exists on one laptop. Selecting from a
schema the contract had moved on from is what let the corpus and its generator disagree:
F-002 hand-edited `fixtures/cards.json` rather than regenerating it, and the generator
stayed broken for two commits with `make check` green.

The invariants this file encodes — every coverage rule satisfied, every PINNED id
present — are asserted against the committed corpus by
`packages/schema/tests/test_card.py::TestFixtures`. That test is what makes the drift
loud, since the source data is gitignored and `make check` cannot re-run this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def _default_source() -> Path:
    """Where `holo-data build` writes, honouring HOLO_BUILD_DIR.

    Imported lazily: `holo_schema` must stay installable without the pipeline, and this
    module is imported by the schema package's own tests for its coverage rules. A
    top-level import would invert the package dependency (holo-pipeline depends on
    holo-schema, not the reverse) at import time.
    """
    from holo_data import paths

    return paths.cards_json()

# Cards that must be in the fixture set regardless of what coverage selection picks,
# because they are the specific anomalies the contract has to survive. Each is a bug
# that would otherwise only be discovered in production.
PINNED: dict[str, str] = {
    "446": "hSD03-009 — 2 arts but 0 `en` translated arts (short-list zip)",
    "447": "hSD04-009 — same arts-length mismatch",
    "1877": "hBP07-091 — cardTypeCode 'unknown' (scraper could not classify)",
    "2003": "hBP07-091 — the other 'unknown', different rarity",
    "2444": "hBP01-028 HR — rarity missing from v1's TypeScript union",
    # Originally selected to cover an `arts[].value` field the contract no longer models
    # (F-003). Kept pinned because it is also the `rarity=P` cover: with it pinned, the
    # greedy pass no longer needs card 176, which is the single card repointing the
    # source removed from the corpus.
    "2164": "hBP03-011 P — rarity=P, and the card F-003's `arts[].value` came from",
    "2138": "hBP03-044 SR (hCO01 reprint) — image_key collision pair A",
    "726": "hBP03-044 SR (hBP03 original) — image_key collision pair B",
    "2139": "hBP03-055 SR (hCO01 reprint) — image_key collision pair C",
    "735": "hBP03-055 SR (hBP03 original) — image_key collision pair D",
    # The three dual-colour forms. All print two badges on a gold ribbon (F-007); the
    # source spells two of them as one token, which `transform` normalises (ADR 0013).
    # Kept pinned as the cover for a colour *pair* — including the order difference,
    # which is printed and must survive: miComet is red-then-blue, FUWAMOCO blue-then-red.
    "1218": "hBP05-040 miComet — ['red','blue'], the source's two-tag spelling",
    "2263": "hBP08-060 FUWAMOCO — ['blue','red'] from one 青赤 token, opposite order",
    "614": "hBP03-050 FUWAMOCO — second 青赤 card, different set",
    "13": "hSD01-013 SorAZ — ['white','green'], the other normalised pair",
    # Cards 1 and 2 are pinned as a pair, and both are load-bearing for the smoke suite:
    # `hSD01-001` is named directly by a dozen HTTP assertions (by-key, detail, ordering),
    # and card 2 is the second oshiCharacter/OSR, without which the group-AND check
    # matches one row and stops distinguishing AND from OR.
    #
    # Neither was pinned before because the greedy pass happened to pick both — card 1 as
    # the oshiCharacter cover, card 2 for `color=green`. ADR 0013 gave green to card 13
    # (SorAZ normalises to white+green), which freed card 2 and let the pass drop it.
    # Depending on a coincidence for a fixture a dozen tests name is the real defect here.
    "1": "hSD01-001 — oshiCharacter cover, and the card the smoke suite addresses by key",
    "2": "hSD01-002 — second oshiCharacter+OSR, for the group-AND and batch checks",
}


# The one fixture with no real card behind it.
#
# `localize()` merge rule 2 — arts pair by index, tolerating a short translated list —
# was covered by cards 446 and 447, which had 2 arts and 0 `en` translated arts. The
# field-level translation cache has since filled both in (F-004), and a census over the
# whole set finds **zero** cards with an arts-length mismatch in any locale. So the
# branch has no natural cover left anywhere in the data, not merely none in the
# selection.
#
# That branch runs in production, in two languages: `localize()` exists in Python (the
# pipeline) and TypeScript (the Worker projects at request time, D8), and the golden
# files are what pin them together. Without a fixture of this shape, a rule that ships
# goes untested in both implementations with `make check` green — which is what F-004's
# warning predicted would happen when the corpus was repointed.
#
# The id is numeric and deliberately far above the real range (ids run 1..2457):
# `schema.sql` makes the card id the FTS5 rowid and `seed.py` raises `NonNumericCardId`
# rather than work around a non-numeric one, so `synthetic-short-arts` would not seed.
# `seed` never reads this file — it only ever writes to production from a real build —
# but `fixtures.sql` goes through the same DDL, so the constraint is real.
SYNTHETIC_ID = "9000001"
SYNTHETIC_REASON = "synthetic — short translated arts list (localize() merge rule 2)"

SYNTHETIC_CARD: dict[str, Any] = {
    "id": SYNTHETIC_ID,
    "card_number": "hSYN-001",
    "card_type_code": "character",
    "rarity_code": "C",
    "color_codes": ["red"],
    "bloom_level_code": "debut",
    "image_key": "hSYN/hSYN-001_C",
    "source_image_url": "https://example.invalid/cardlist/hSYN/hSYN-001_C.png",
    "card_sets": ["hSYN"],
    "life": None,
    "hp": 100,
    "baton_touch_count": 1,
    "baton_touch_types": ["null"],
    "arts": [
        {"cost_types": ["red"], "damage": 30},
        {"cost_types": ["red", "null"], "damage": 60, "is_plus": True},
    ],
    "translations": {
        # `ja` carries both arts, so the pairing has something to pair against.
        "ja": {
            "name": "テスト・ショートアーツ",
            "arts": [
                {"name": "アーツ一", "effect": "効果一"},
                {"name": "アーツ二", "effect": "効果二"},
            ],
        },
        # The whole point: 2 arts, 0 translated. `localize("en")` must emit both arts
        # with their costs and damage and no name.
        "en": {"name": "Test Short Arts", "arts": []},
        "tc": {"name": "測試短技能", "arts": [{"name": "技能一", "effect": "效果一"}]},
        "ko": {"name": "테스트", "arts": []},
        "id": {"name": "Tes Seni Pendek", "arts": []},
        "th": {"name": "ทดสอบ", "arts": []},
        "es": {"name": "Prueba de Artes Cortas", "arts": []},
    },
}


def _coverage_rules() -> list[tuple[str, Callable[[Card], bool]]]:
    """One rule per thing that must appear at least once in the fixture set."""
    rules: list[tuple[str, Callable[[Card], bool]]] = []

    # Two card types are deliberately excluded, for different reasons — and both were
    # emitting "no card covers …" warnings on every run, which is how a warning stops
    # being read.
    #
    # `unknown` is the scraper's placeholder for a type it cannot classify. F-001 fixed
    # the missing `サポート・スタッフ` mapping, so no card carries it and none can be
    # selected. It stays in the enum as a safety valve; whether that valve should be
    # *loud* is issue #19, and a corpus fixture is not what answers it.
    #
    # `rulesNotice` cannot appear here at all: `Card` rejects it outright, because a
    # notice is not a card (F-020). `pipeline/tests/test_notices.py` covers it.
    #
    # `test_card.py::TestFixtures` already asserted both were absent, so before this the
    # coverage rules and the tests contradicted each other.
    uncoverable = {"unknown", "rulesNotice"}
    for value in CARD_TYPE_VALUES:
        if value in uncoverable:
            continue
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

    chosen[SYNTHETIC_ID] = SYNTHETIC_REASON
    by_id[SYNTHETIC_ID] = Card.model_validate(SYNTHETIC_CARD)

    selected = sorted(
        (by_id[cid] for cid in chosen), key=lambda c: int(c.id)
    )
    return selected, chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="cards.json to select from (default: `holo-data build` output)",
    )
    args = parser.parse_args()

    source = args.source or _default_source()

    if not source.exists():
        print(f"source not found: {source}", file=sys.stderr)
        print(
            "Run `holo-data transform && holo-data build` first, or pass --source. "
            "Or skip: fixtures/ is committed and only needs rebuilding when the "
            "selection rules change.",
            file=sys.stderr,
        )
        return 1

    collection = CardCollection.model_validate_json(source.read_text(encoding="utf-8"))
    cards = collection.cards
    print(f"  loaded {len(cards)} cards from {source}")

    selected, reasons = select(cards)
    print(f"  selected {len(selected)} fixture cards")

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # Deliberately fixed, not the source build's timestamp. Determinism is what makes
    # regeneration reviewable: same input, byte-identical output, so a diff in
    # fixtures/ means the *selection* changed. Passing the real timestamp through would
    # produce a diff on every run and drown the signal. A fixture corpus's own build
    # time is not a fact anyone reads.
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
        "# by census over the whole card set. Committed so the selection is reviewable.",
        "#",
        "# Selected from `holo-data build` output. One entry is synthetic — see",
        "# SYNTHETIC_CARD in build_fixtures.py for why no real card can cover it.",
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
