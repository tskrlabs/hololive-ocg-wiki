"""Assemble the canonical `cards.json` and validate it against the contract.

Replaces v1's `6-merge-translated.py`. This is where the Phase 0 models earn their keep:
every card is validated before anything is written, so a scraper regression or a new
enum value from the official site fails here rather than in production.

Validation is **collect-and-report**: all problems are gathered and printed together,
then the command exits non-zero. Failing on the first error would mean discovering
2,448 cards' worth of problems one run at a time. `--allow-unknown-enums` publishes
anyway and prints what it let through — deliberately ugly so it does not become the
default path (ADR 0001).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from holo_schema import Card, CardCollection

from .paths import cards_json, ensure_dirs
from .translate.cache import TranslationCache, field_keys


@dataclass
class BuildReport:
    total: int = 0
    valid: int = 0
    errors: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    enum_violations: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    translation_coverage: dict[str, int] = field(default_factory=dict)

    @property
    def failed(self) -> int:
        return self.total - self.valid

    def add_error(self, card_id: str, message: str, is_enum: bool = False) -> None:
        target = self.enum_violations if is_enum else self.errors
        target[message].append(card_id)


def apply_translations(
    card: dict[str, Any], cache: TranslationCache, locales: list[str]
) -> dict[str, Any]:
    """Fill in each locale's translation from the cache.

    The JP translation is already present from `transform`; this adds the rest. A field
    with no cache entry is simply absent from that locale — better than shipping a
    placeholder, and `localize()` falls back to JP for anything missing.
    """
    jp = card.get("translations", {}).get("ja", {})
    if not jp:
        return card

    for locale in locales:
        translation: dict[str, Any] = {}

        for field_key, _source in field_keys(jp):
            entry = cache.get(locale, card["id"], field_key)
            if entry is None:
                continue
            _assign(translation, field_key, entry.value)

        if translation:
            card.setdefault("translations", {})[locale] = translation

    return card


def _assign(target: dict[str, Any], field_key: str, value: Any) -> None:
    """Write a value into a nested dict by cache key (`arts[0].effect`)."""
    parts = field_key.split(".")
    node: Any = target

    for index, part in enumerate(parts):
        name, _, bracket = part.partition("[")
        is_last = index == len(parts) - 1

        if bracket:
            position = int(bracket.rstrip("]"))
            container = node.setdefault(name, []) if name else node
            while len(container) <= position:
                container.append({})
            if is_last:
                container[position] = value
            else:
                node = container[position]
        else:
            if is_last:
                node[name] = value
            else:
                node = node.setdefault(name, {})


def build(
    cards: list[dict[str, Any]],
    cache: TranslationCache,
    locales: list[str],
    allow_unknown_enums: bool = False,
) -> tuple[CardCollection | None, BuildReport]:
    """Merge translations, validate every card, and assemble the collection."""
    report = BuildReport(total=len(cards))
    validated: list[Card] = []

    for raw in cards:
        merged = apply_translations(dict(raw), cache, locales)
        try:
            validated.append(Card.model_validate(merged))
            report.valid += 1
        except ValidationError as exc:
            for error in exc.errors():
                location = ".".join(
                    str(part) for part in error["loc"] if not isinstance(part, int)
                )
                is_enum = error["type"] == "literal_error"
                message = f"{location}: {error['msg']}"
                report.add_error(str(raw.get("id")), message, is_enum=is_enum)

    for locale in ["ja", *locales]:
        report.translation_coverage[locale] = sum(
            1 for card in cards if card.get("translations", {}).get(locale)
        )

    blocking = bool(report.errors) or (report.enum_violations and not allow_unknown_enums)
    if blocking or len(validated) != len(cards):
        return None, report

    collection = CardCollection(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        cards=validated,
    )
    return collection, report


def save(collection: CardCollection) -> int:
    """Write `cards.json`, returning the byte size.

    `exclude_none=True` matters: absent fields are omitted rather than serialised as
    null, which is what the census over 2,448 cards showed the data actually does, and
    what the generated TypeScript claims (`hp?: number`, not `hp?: number | null`).
    """
    ensure_dirs()
    payload = collection.model_dump(mode="json", exclude_none=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    cards_json().write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def load() -> CardCollection | None:
    path = cards_json()
    if not path.exists():
        return None
    return CardCollection.model_validate_json(path.read_text(encoding="utf-8"))
