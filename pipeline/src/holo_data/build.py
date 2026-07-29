"""Assemble the canonical `cards.json` and validate it against the contract.

Replaces v1's `6-merge-translated.py`. This is where the Phase 0 models earn their keep:
every card is validated before anything is written, so a scraper regression or a new
enum value from the official site fails here rather than in production.

Validation is **collect-and-report**: all problems are gathered and printed together,
then the command exits non-zero. Failing on the first error would mean discovering
2,448 cards' worth of problems one run at a time.

`--allow-unknown-enums` ships the cards that validate and **drops** the ones that do
not, recording their ids in `CardCollection.dropped`. It cannot publish them: the
contract's enums are closed `Literal`s, so a card carrying an unmapped value cannot be
constructed at all. The dropped list is what `publish` and `seed` refuse on, so the
hatch unblocks `build` alone and never reaches the site (ADR 0001).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from holo_schema import Card, CardCollection, Notice, NoticeCollection
from holo_schema.enums import SOURCE_LOCALE

from . import transform
from .paths import cards_json, ensure_dirs, filter_options_json, notices_json
from .translate.cache import TranslationCache, field_keys


@dataclass
class BuildReport:
    total: int = 0
    valid: int = 0
    # Rules notices are counted separately and excluded from `total`: they are not
    # cards, so folding them in would make the card count disagree with what the site
    # and `status.json` report.
    notice_count: int = 0
    errors: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    enum_violations: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    translation_coverage: dict[str, int] = field(default_factory=dict)

    @property
    def failed(self) -> int:
        return self.total - self.valid

    @property
    def dropped_ids(self) -> list[str]:
        """Cards that failed only on an enum value, sorted.

        What `--allow-unknown-enums` leaves out of the artifact. Derived from
        `enum_violations` rather than tracked separately so the two cannot disagree; a
        card with a non-enum error too is still here, but that case never reaches the
        collection because any `errors` entry blocks the build outright.
        """
        ids = {card_id for ids in self.enum_violations.values() for card_id in ids}
        return sorted(ids, key=lambda value: (len(value), value))

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
) -> tuple[CardCollection | None, NoticeCollection | None, BuildReport]:
    """Merge translations, validate every entry, and assemble both collections.

    Rules notices are split off here rather than upstream. Everything before this point
    treats them as cards — they are scraped, extracted, transformed and translated
    identically — so the split happens at the one place that knows about the contract.
    See `holo_schema.notice` for why they are not `Card`s.
    """
    entries = cards
    cards = [entry for entry in entries if not transform.is_notice(entry)]
    notice_entries = [entry for entry in entries if transform.is_notice(entry)]

    report = BuildReport(total=len(cards), notice_count=len(notice_entries))
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

    validated_notices: list[Notice] = []
    for raw in notice_entries:
        merged = apply_translations(dict(raw), cache, locales)
        try:
            validated_notices.append(Notice.model_validate(transform.to_notice(merged)))
        except ValidationError as exc:
            # A malformed notice blocks the build exactly as a malformed card does. It
            # states a rule that affects deck legality, so shipping the card set without
            # it would be shipping cards whose format legality nothing explains.
            for error in exc.errors():
                location = ".".join(
                    str(part) for part in error["loc"] if not isinstance(part, int)
                )
                report.add_error(
                    str(raw.get("id")), f"notice {location}: {error['msg']}"
                )

    for locale in ["ja", *locales]:
        report.translation_coverage[locale] = sum(
            1 for card in cards if card.get("translations", {}).get(locale)
        )

    # `--allow-unknown-enums` **drops** the offending cards; it cannot publish them.
    # `CardTypeCode` and friends are closed `Literal`s, so a card carrying an unmapped
    # value has no way to become a `Card` object at all — there is nothing to put in the
    # collection. The flag's promise is therefore "ship the rest", not "ship anyway".
    #
    # This was the bug: the old `len(validated) != len(cards)` clause fired on exactly
    # the cards the flag was supposed to let past, so `build` returned None regardless
    # and the hatch had never once worked. F-008 reasoned that blocking was cheap
    # because this existed — it did not.
    if report.errors or (report.enum_violations and not allow_unknown_enums):
        return None, None, report

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    collection = CardCollection(
        generated_at=generated_at, cards=validated, dropped=report.dropped_ids
    )
    notices = NoticeCollection(generated_at=generated_at, notices=validated_notices)
    return collection, notices, report


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


def save_notices(collection: NoticeCollection) -> int:
    """Write `notices.json`, returning the byte size.

    Always written, even when empty: a consumer distinguishing "no notices" from "the
    artifact is missing" otherwise has to guess, and `/api/notices` would 404 on a
    perfectly valid build.
    """
    ensure_dirs()
    payload = collection.model_dump(mode="json", exclude_none=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    notices_json().write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def _best_label(ja_name: str, labels: dict[str, int]) -> str:
    """Pick one display name for a character from the spellings its cards carry.

    A spelling that differs from the ja name wins, because that is the one that was
    actually translated; among equals, the most common, then the text itself so the
    result does not depend on dict ordering. See `filter_options` for the measurements.
    """
    return max(
        labels.items(), key=lambda item: (item[0] != ja_name, item[1], item[0])
    )[0]


def filter_options(collection: CardCollection, locale: str) -> dict[str, Any]:
    """The dropdown values for one locale: names, tags and sets.

    Each entry is `{value, label}` — `value` is what the API filters on, `label` is what
    the dropdown shows.

    **Names key on the source locale.** `value` is the ja name and `label` is this
    locale's, because the ja name is the stable per-character identity while the
    localised one is not: 122 of 296 characters (41%) have an inconsistent name in at
    least one locale, so keying on the displayed text splits a character into two
    entries that each return a subset of their cards (findings F-015).

    Where a character's cards disagree on the label, a spelling that **differs from the
    ja name wins** over the most common one. Most cards leave the character name
    untranslated — only 6 of Shirakami Fubuki's 44 cards romanise it in `en` — so
    picking the majority would show Japanese text to an English reader while a perfectly
    good "Shirakami Fubuki" sat in the data. This recovers a readable label for 103 of
    296 characters in `en` and 65 in `ko`. Ties break on the label text so the artifact
    is deterministic.

    Tags and sets have no such split: tags are localised display text with no stable
    identity to preserve, and set names are language-independent.
    """
    label_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    tags: set[str] = set()
    sets: set[str] = set()

    for card in collection.cards:
        source = card.translations[SOURCE_LOCALE]
        translation = card.translations.get(locale) or source
        label_counts[source.name][translation.name] += 1
        tags.update(translation.tags or [])
        sets.update(card.card_sets)

    names = [
        {"value": ja_name, "label": _best_label(ja_name, labels)}
        for ja_name, labels in sorted(label_counts.items())
    ]

    return {
        "locale": locale,
        "generated_at": collection.generated_at,
        "names": names,
        "tags": [{"value": tag, "label": tag} for tag in sorted(tags)],
        "sets": [{"value": name, "label": name} for name in sorted(sets)],
    }


def save_filter_options(collection: CardCollection, locales: list[str]) -> dict[str, int]:
    """Write `filter-options/{locale}.json` for every locale. Returns byte sizes."""
    ensure_dirs()
    written: dict[str, int] = {}
    for locale in locales:
        path = filter_options_json(locale)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            filter_options(collection, locale), ensure_ascii=False, indent=2
        ) + "\n"
        path.write_text(text, encoding="utf-8")
        written[locale] = len(text.encode("utf-8"))
    return written


def load() -> CardCollection | None:
    path = cards_json()
    if not path.exists():
        return None
    return CardCollection.model_validate_json(path.read_text(encoding="utf-8"))


def load_notices() -> list[Notice]:
    """The built notices, or none if this working directory predates them.

    Returns a bare list rather than the collection: every caller wants the notices
    themselves, and an absent artifact is not an error — it is what a build from before
    F-020 looks like.
    """
    path = notices_json()
    if not path.exists():
        return []
    return NoticeCollection.model_validate_json(
        path.read_text(encoding="utf-8")
    ).notices
