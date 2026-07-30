"""Translatable units: the distinct strings a build contains, addressed by content.

**The change this makes.** ADR 0002 keys a translation on `(locale, card_id, field_key)`
— so the same Japanese string, printed on five cards, is translated five times and may
come back five different ways. Measured over the real 2,463-card build, it does: 362 of
926 distinct art names have two or more `en` translations, and 1,055 of 1,305 distinct
effect texts do.

Here a translation is keyed on `(kind, sha256(source))`. Two cards printing the same
Japanese resolve to one slot, so divergence stops being something to *correct* and
becomes something that **cannot be represented**.

It is also cheaper. The 2,463 cards hold 15,463 translatable field occurrences but only
3,942 distinct units — 294 KB against 1.42 MB of whole-card text, or 21%.

## Why the kind is part of the key

Only 15 of 3,942 distinct strings appear under more than one field kind, so folding them
together would save almost nothing. What the split buys is a *prompt per kind*: an art
name wants "translate this title, keep it punchy" and an effect wants "use TCG-idiomatic
rules language". One prompt covering every field at once is what the current pipeline
does, and the uneven results are the evidence against it.

## Context, not cards

A unit carries the card name and art name it was found under, as reference-only fields.
Prose needs that — `そのホロメン` ("that holomem") is ambiguous without knowing whose card
it is — but a whole card is 6x the tokens for context that three lines supply.

Context is *not* part of the key. The same sentence on two cards is still one unit; the
context recorded is simply the first occurrence's. That is deliberate: if context changed
the key, identical rules text would fragment again and the whole point would be lost.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal

# Every field kind that gets translated, and whether it is a short label or prose.
#
# The distinction drives prompt selection: labels are titles (keep them punchy, preserve
# tone marks), prose is rules text (use the locale's established TCG vocabulary).
LABEL_KINDS = (
    "card_name",
    "tag",
    "art_name",
    "keyword_name",
    "skill_name",
    "skill_timing",
)
PROSE_KINDS = (
    "ability_text",
    "extra",
    "art_effect",
    "keyword_effect",
    "skill_effect",
)
QA_KIND = "qa"

ALL_KINDS = (*LABEL_KINDS, *PROSE_KINDS, QA_KIND)

Kind = Literal[
    "card_name", "tag", "art_name", "keyword_name", "skill_name", "skill_timing",
    "ability_text", "extra", "art_effect", "keyword_effect", "skill_effect", "qa",
]


def unit_hash(value: Any) -> str:
    """Content address for one source value.

    `sort_keys` matters for Q&A, which hashes a dict: key ordering must not change the
    address or every run would look stale.
    """
    content = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def unit_key(kind: str, value: Any) -> str:
    """The cache key: `art_name:9f86d081…`.

    Readable prefix on purpose — a 3,942-line cache of bare hashes is impossible to scan,
    and `grep '^art_name:'` is how you audit one kind.
    """
    return f"{kind}:{unit_hash(value)}"


@dataclass
class Context:
    """Reference-only fields sent alongside a prose unit. Never translated.

    Recorded from the first card a unit was seen on. Not part of the key — see the
    module docstring.
    """

    card_name: str | None = None
    art_name: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in (
                ("card_name", self.card_name),
                ("art_name", self.art_name),
            )
            if value
        }


@dataclass
class Unit:
    """One distinct translatable string, and where it came from."""

    kind: str
    value: Any
    context: Context = field(default_factory=Context)
    occurrences: int = 0

    @property
    def key(self) -> str:
        return unit_key(self.kind, self.value)

    @property
    def is_label(self) -> bool:
        return self.kind in LABEL_KINDS

    @property
    def is_qa(self) -> bool:
        return self.kind == QA_KIND

    @property
    def char_count(self) -> int:
        if isinstance(self.value, str):
            return len(self.value)
        return len(json.dumps(self.value, ensure_ascii=False))


def iter_fields(translation: dict[str, Any]) -> Iterator[tuple[str, Any, Context]]:
    """Yield `(kind, value, context)` for every translatable field on one translation.

    Mirrors `cache.field_keys`, but yields kinds rather than addressable paths — the
    path is what a per-card cache needs and exactly what a content-addressed one must
    not use.
    """
    card_name = translation.get("name")
    base = Context(card_name=card_name)

    if card_name:
        yield "card_name", card_name, Context()

    for tag in translation.get("tags") or []:
        yield "tag", tag, Context()

    for name in ("ability_text", "extra"):
        if value := translation.get(name):
            yield name, value, base

    for art in translation.get("arts") or []:
        if not isinstance(art, dict):
            continue
        art_name = art.get("name")
        if art_name:
            yield "art_name", art_name, Context(card_name=card_name)
        if effect := art.get("effect"):
            yield "art_effect", effect, Context(card_name=card_name, art_name=art_name)

    keyword = translation.get("keyword")
    if isinstance(keyword, dict):
        if value := keyword.get("name"):
            yield "keyword_name", value, Context(card_name=card_name)
        if value := keyword.get("effect"):
            yield "keyword_effect", value, Context(
                card_name=card_name, art_name=keyword.get("name")
            )

    for skill_key in ("oshi_skill", "sp_oshi_skill"):
        skill = translation.get(skill_key)
        if not isinstance(skill, dict):
            continue
        skill_name = skill.get("name")
        if skill_name:
            yield "skill_name", skill_name, Context(card_name=card_name)
        if value := skill.get("effect"):
            yield "skill_effect", value, Context(
                card_name=card_name, art_name=skill_name
            )
        if value := skill.get("timing"):
            yield "skill_timing", value, Context()

    for qa in translation.get("qa_items") or []:
        if isinstance(qa, dict):
            yield QA_KIND, qa, base


def collect(cards: list[dict[str, Any]], source_locale: str = "ja") -> dict[str, Unit]:
    """Every distinct unit in a build, keyed by content address.

    The first occurrence supplies the context; later ones only bump the count. Occurrence
    counts are what make the saving legible in `--dry-run` — "926 units covering 1,991
    art occurrences" is the number worth reporting.
    """
    units: dict[str, Unit] = {}

    for card in cards:
        translation = (card.get("translations") or {}).get(source_locale)
        if not translation:
            continue

        for kind, value, context in iter_fields(translation):
            key = unit_key(kind, value)
            existing = units.get(key)
            if existing is None:
                units[key] = Unit(
                    kind=kind, value=value, context=context, occurrences=1
                )
            else:
                existing.occurrences += 1

    return units


@dataclass
class UnitStats:
    """Per-kind totals, for `--dry-run` and the phase reports."""

    by_kind: dict[str, tuple[int, int, int]]
    """kind -> (distinct units, total occurrences, source characters)"""

    @property
    def distinct(self) -> int:
        return sum(units for units, _, _ in self.by_kind.values())

    @property
    def occurrences(self) -> int:
        return sum(count for _, count, _ in self.by_kind.values())

    @property
    def chars(self) -> int:
        return sum(chars for _, _, chars in self.by_kind.values())

    def lines(self, exclude: tuple[str, ...] = ()) -> list[str]:
        out = []
        for kind in ALL_KINDS:
            if kind in exclude or kind not in self.by_kind:
                continue
            units, count, chars = self.by_kind[kind]
            saved = f"{100 * (1 - units / count):.0f}%" if count else "—"
            out.append(
                f"  {kind:15s} {units:5d} units  {count:6d} occurrences  "
                f"{chars:7,d} chars  {saved} saved"
            )
        return out


def stats(units: dict[str, Unit]) -> UnitStats:
    by_kind: dict[str, tuple[int, int, int]] = {}
    for unit in units.values():
        distinct, occurrences, chars = by_kind.get(unit.kind, (0, 0, 0))
        by_kind[unit.kind] = (
            distinct + 1,
            occurrences + unit.occurrences,
            chars + unit.char_count,
        )
    return UnitStats(by_kind=by_kind)
