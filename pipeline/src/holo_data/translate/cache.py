"""Field-level translation cache.

This replaces v1's whole-card `_source_hash` and is the main design change in Phase 1.

**The problem.** v1 stored one SHA-256 of the entire JP card in `_source_hash`. Any
change to any part of the card invalidated the whole thing, re-translating name, tags,
every art, every skill and every Q&A entry.

Measured across v1's three dated snapshots (2026-04-26 -> 2026-05-28 -> latest), over
2,131 cards common to all three:

| what changed        | cards |
|---------------------|-------|
| JP `qa_items`       | 37-39 |
| JP `arts`           |     2 |
| JP `name`           |     2 |
| everything else JP  |   0-1 |

Once a card is published its printed text does not change; **Q&A is the only real
churn**. So v1 re-translated roughly 50x more than necessary.

**The fix.** Hash each translatable unit separately:

    2314.name              -> sha256(JP value) -> translated value
    2314.arts[0].effect    -> ...
    2314.qa_items[2]       -> ...

A changed Q&A entry invalidates that entry alone.

**Why this also fixes manual corrections.** Since a field's value comes from the cache
rather than from the model, a human-edited value with a matching source hash is never
overwritten — there is nothing to overwrite it with. A correction is just an entry with
`source: "manual"`. This supersedes D14's `corrections/` overlay: no separate merge
layer, no post-translation patching, and no scripts 7/8 (which were never used).

The Poe prompt is deliberately unchanged — the whole card goes in and the whole card
comes back. Only *stale* fields are read out of the response; the rest is discarded.
That is what makes a correction durable even when the card is re-translated for some
other reason.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal

from ..paths import cache_file, ensure_dirs

CACHE_VERSION = 1

Source = Literal["machine", "manual"]

# The JP fields worth translating. Everything else on a card is either a code
# (card_type_code), a number (hp), or a proper noun that should not be touched.
TRANSLATABLE_SCALARS = ("name", "ability_text", "extra")


def hash_value(value: Any) -> str:
    """Deterministic SHA-256 of one source value.

    `sort_keys` matters: dict ordering must not change the hash, or every run would
    invalidate everything.
    """
    content = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class Entry:
    """One cached field translation."""

    source_hash: str
    value: Any
    source: Source = "machine"

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"hash": self.source_hash, "value": self.value}
        if self.source != "machine":
            out["source"] = self.source
        return out

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "Entry":
        return cls(
            source_hash=raw["hash"],
            value=raw["value"],
            source=raw.get("source", "machine"),
        )


def field_keys(jp_card: dict[str, Any]) -> Iterator[tuple[str, Any]]:
    """Yield every translatable (field_key, source_value) pair for a JP card.

    Field keys are stable, addressable paths — `name`, `arts[0].effect`, `qa_items[2]`.
    Indexed keys mean an added Q&A entry does not shift the identity of existing ones,
    as long as the site appends rather than inserts (which it does; entries are dated
    and ordered).

    Q&A entries hash as a whole rather than per sub-field: question, answer and title
    are translated together as one unit of prose, and splitting them would let a title
    fix silently desync from its answer.
    """
    for name in TRANSLATABLE_SCALARS:
        if jp_card.get(name):
            yield name, jp_card[name]

    if jp_card.get("tags"):
        yield "tags", jp_card["tags"]

    for index, art in enumerate(jp_card.get("arts") or []):
        if not isinstance(art, dict):
            continue
        for sub in ("name", "effect"):
            if art.get(sub):
                yield f"arts[{index}].{sub}", art[sub]

    keyword = jp_card.get("keyword")
    if isinstance(keyword, dict):
        for sub in ("name", "effect"):
            if keyword.get(sub):
                yield f"keyword.{sub}", keyword[sub]

    for skill_key in ("oshi_skill", "sp_oshi_skill"):
        skill = jp_card.get(skill_key)
        if isinstance(skill, dict):
            for sub in ("name", "effect", "timing"):
                if skill.get(sub):
                    yield f"{skill_key}.{sub}", skill[sub]

    for index, qa in enumerate(jp_card.get("qa_items") or []):
        if isinstance(qa, dict):
            yield f"qa_items[{index}]", qa


@dataclass
class TranslationCache:
    """Per-locale, per-field translation state.

    On disk:

        {
          "version": 1,
          "locales": {
            "en": {
              "2314": {
                "name": {"hash": "abc…", "value": "IRyS"},
                "qa_items[0]": {"hash": "def…", "value": {…}, "source": "manual"}
              }
            }
          }
        }
    """

    entries: dict[str, dict[str, dict[str, Entry]]] = field(default_factory=dict)

    # --- Lookup ---

    def get(self, locale: str, card_id: str, field_key: str) -> Entry | None:
        return self.entries.get(locale, {}).get(card_id, {}).get(field_key)

    def is_fresh(self, locale: str, card_id: str, field_key: str, source_value: Any) -> bool:
        """True when this field's cached translation matches the current JP source."""
        entry = self.get(locale, card_id, field_key)
        return entry is not None and entry.source_hash == hash_value(source_value)

    def put(
        self,
        locale: str,
        card_id: str,
        field_key: str,
        source_value: Any,
        translated: Any,
        source: Source = "machine",
    ) -> None:
        self.entries.setdefault(locale, {}).setdefault(card_id, {})[field_key] = Entry(
            source_hash=hash_value(source_value),
            value=translated,
            source=source,
        )

    # --- Staleness ---

    def stale_fields(
        self, locale: str, card_id: str, jp_card: dict[str, Any]
    ) -> list[str]:
        """Field keys whose cached translation is missing or out of date.

        A **manual** entry whose hash still matches is never stale — that is the whole
        point: a human corrected it, the JP source has not moved, so it stands.
        """
        return [
            key
            for key, value in field_keys(jp_card)
            if not self.is_fresh(locale, card_id, key, value)
        ]

    def prune(self, locale: str, jp_cards: dict[str, dict[str, Any]]) -> int:
        """Drop entries for cards or fields that no longer exist.

        Returns the number of entries removed. Manual entries are pruned too — if the
        field is gone from the source, a correction to it is meaningless.
        """
        locale_entries = self.entries.get(locale)
        if not locale_entries:
            return 0

        removed = 0
        for card_id in list(locale_entries):
            jp_card = jp_cards.get(card_id)
            if jp_card is None:
                removed += len(locale_entries.pop(card_id))
                continue

            live_keys = {key for key, _ in field_keys(jp_card)}
            for field_key in list(locale_entries[card_id]):
                if field_key not in live_keys:
                    del locale_entries[card_id][field_key]
                    removed += 1

        return removed

    # --- Stats ---

    def manual_count(self, locale: str | None = None) -> int:
        locales = [locale] if locale else list(self.entries)
        return sum(
            1
            for loc in locales
            for card in self.entries.get(loc, {}).values()
            for entry in card.values()
            if entry.source == "manual"
        )

    # --- Persistence ---

    @classmethod
    def load(cls, path: Path | None = None) -> "TranslationCache":
        target = path or cache_file()
        if not target.exists():
            return cls()

        raw = json.loads(target.read_text(encoding="utf-8"))
        version = raw.get("version")
        if version != CACHE_VERSION:
            raise ValueError(
                f"translation cache at {target} is version {version}, expected "
                f"{CACHE_VERSION}. Migrate it or delete it (deleting costs a full "
                "re-translation)."
            )

        entries: dict[str, dict[str, dict[str, Entry]]] = {}
        for locale, cards in raw.get("locales", {}).items():
            entries[locale] = {
                card_id: {
                    field_key: Entry.from_json(value)
                    for field_key, value in fields.items()
                }
                for card_id, fields in cards.items()
            }
        return cls(entries=entries)

    def save(self, path: Path | None = None) -> None:
        target = path or cache_file()
        ensure_dirs()
        payload = {
            "version": CACHE_VERSION,
            "locales": {
                locale: {
                    card_id: {
                        field_key: entry.to_json()
                        for field_key, entry in sorted(fields.items())
                    }
                    for card_id, fields in sorted(cards.items())
                }
                for locale, cards in sorted(self.entries.items())
            },
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
