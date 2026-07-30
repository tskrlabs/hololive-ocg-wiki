"""Propose character-name aliases for the glossary, and flag the ones that are traps.

Aliases exist because the nickname *is* the joke in this dataset — `おつルーナ`,
`おつムーナ`, `おつリスー` are one construction across characters, and a calibration run
rendered `おつルーナ` as "OtsuLuna" because only the full name `姫森ルーナ` was a glossary
key. Masking cannot protect a short form it does not know about.

**This script proposes; it does not decide.** Deriving aliases mechanically is unsafe in
three ways this dataset actually exhibits, so every candidate is classified and only the
unambiguous ones are written:

1. **Ambiguous** — `マリン` is a valid short form of both `宝鐘マリン` and `魔法少女マリン`.
   Masking it would restore as whichever entry happened to be masked first, giving a
   silent per-run wrong answer. `Glossary.validate()` rejects these outright, so they must
   never be written.

2. **Substring false positives** — `ムリン` appears inside `グレムリン` (gremlin), `ローズ`
   inside `モンローズ`, `トワ` inside `トワイライトリゾート` (twilight), `こぼ` inside
   `ぼこぼこぼこぼ`. **Masking is boundary-aware, so these are reported rather than
   rejected**: a katakana alias followed by more katakana is one word and is left alone,
   while the same alias followed by a particle is a name. `トワにしか出せない色` masks and
   `トワイライトリゾート` does not. The report still names them, because the boundary rule
   is a heuristic and the maintainer should know which aliases depend on it.

3. **Common nouns** — restricting to *character* card types is what keeps `エール` (the
   game's cheer resource, from card `青エール`) and `魔法` (from `魔法のタンス`, a wardrobe)
   out of the table entirely. An earlier pass over all card types proposed both.

Run it, read the report, then edit `pipeline/glossary/names.json` by hand for anything in
the REVIEW section. That file is the source of truth; this script only ever adds aliases
it can prove are safe.

    uv run python pipeline/scripts/propose_aliases.py           # report only
    uv run python pipeline/scripts/propose_aliases.py --write   # apply the safe ones
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))

from holo_data.glossary import Glossary, absorbed_in  # noqa: E402

CARDS_JSON = REPO_ROOT / "pipeline" / "build" / "cards.json"

# Only these card types name a person. A support card is named for an object or an event
# — `ASMRマイク`, `青エール`, `魔法のタンス` — and its name's fragments are common nouns.
CHARACTER_TYPES = {"character", "oshiCharacter", "buzzCharacter"}

MIN_ALIAS_LEN = 2


def load_cards() -> list[dict]:
    return json.loads(CARDS_JSON.read_text(encoding="utf-8"))["cards"]


def character_names(cards: list[dict]) -> set[str]:
    return {
        card["translations"]["ja"]["name"]
        for card in cards
        if card["card_type_code"] in CHARACTER_TYPES
    }


def labels(cards: list[dict]) -> set[str]:
    """Every short label a character name might hide inside."""
    out: set[str] = set()
    for card in cards:
        translation = card["translations"]["ja"]
        for art in translation.get("arts") or []:
            if art.get("name"):
                out.add(art["name"])
        keyword = translation.get("keyword") or {}
        if keyword.get("name"):
            out.add(keyword["name"])
        for skill in ("oshi_skill", "sp_oshi_skill"):
            value = (translation.get(skill) or {}).get("name")
            if value:
                out.add(value)
    return out


def candidates_for(name: str) -> set[str]:
    """Plausible short forms: separator-delimited parts, katakana tail, kanji head.

    Western-style names split on `・` (`モココ・アビスガード` -> `モココ`). Japanese names
    concatenate surname and given name with no separator, so the katakana tail
    (`白上フブキ` -> `フブキ`) and the kanji head (`白上フブキ` -> `白上`) are both tried.
    """
    out: set[str] = set()
    for part in re.split(r"[・\s]+", name):
        if len(part) >= MIN_ALIAS_LEN:
            out.add(part)
    if tail := re.search(r"([ァ-ヶー]{2,})$", name):
        out.add(tail.group(1))
    if head := re.match(r"^([一-龯]{2,3})", name):
        out.add(head.group(1))
    return {c for c in out if len(c) >= MIN_ALIAS_LEN and c != name}


def classify(cards: list[dict]) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """Sort every candidate into (safe, ambiguous, suspicious).

    Returns:
        safe: {character name: [alias, ...]} — provably unambiguous.
        ambiguous: report lines for aliases claimed by more than one character.
        suspicious: report lines for aliases that also match unrelated text.
    """
    names = character_names(cards)
    all_labels = labels(cards)

    claimed: dict[str, set[str]] = defaultdict(set)
    for name in names:
        for candidate in candidates_for(name):
            claimed[candidate].add(name)

    safe: dict[str, list[str]] = defaultdict(list)
    ambiguous: list[str] = []
    suspicious: list[str] = []

    for candidate, owners in sorted(claimed.items()):
        matching = [label for label in all_labels if candidate in label]
        if not matching:
            continue  # proposes nothing; not worth an entry

        if len(owners) > 1:
            ambiguous.append(
                f"  {candidate!r} claimed by {sorted(owners)} — "
                f"masking would restore whichever was matched first"
            )
            continue

        owner = next(iter(owners))
        safe[owner].append(candidate)

        # Everything below is reporting only — these aliases are written either way,
        # because masking resolves both cases at match time rather than at table-build
        # time.

        # Nested inside another character's full name (`不知火` inside `不知火フレア`).
        # Longest-first ordering means the full name is consumed first, so the alias
        # never fires there.
        nested = [n for n in names if candidate in n and n != owner]

        # Absorbed into a longer katakana word (`トワ` inside `トワイライトリゾート`).
        # `mask()`'s boundary rule declines to match here.
        extended = [label for label in matching if absorbed_in(candidate, label)]

        if extended or nested:
            detail = (
                f"relies on the boundary rule: {extended[:2]}"
                if extended
                else f"relies on longest-first: nested in {nested}"
            )
            suspicious.append(f"  {candidate!r} ({owner}) — {detail}")

    return dict(safe), ambiguous, suspicious


def main() -> int:
    if not CARDS_JSON.exists():
        print(f"no build at {CARDS_JSON} — run `holo-data build` first", file=sys.stderr)
        return 1

    cards = load_cards()
    safe, ambiguous, suspicious = classify(cards)

    print(f"SAFE — unambiguous, no substring collisions ({sum(len(v) for v in safe.values())})")
    for name in sorted(safe):
        print(f"  {name}: {safe[name]}")

    print(f"\nAMBIGUOUS — never writable, `validate()` rejects these ({len(ambiguous)})")
    print("\n".join(ambiguous) or "  none")

    print(f"\nWRITTEN, BUT RESOLVED AT MATCH TIME ({len(suspicious)})")
    print("\n".join(suspicious) or "  none")

    if "--write" not in sys.argv:
        print("\n(report only — re-run with --write to apply the SAFE list)")
        return 0

    glossary = Glossary.load("names")
    added = 0
    for name, aliases in safe.items():
        entry = glossary.entries.get(name)
        if entry is None:
            continue
        for alias in aliases:
            if alias not in entry.aliases:
                entry.aliases.append(alias)
                added += 1

    # `validate()` runs inside `save()` and will reject an ambiguous table, so a bug in
    # the classifier above fails here rather than corrupting a translation run.
    path = glossary.save()
    print(f"\n✓ added {added} alias(es) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
