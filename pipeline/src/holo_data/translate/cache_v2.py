"""The content-addressed translation cache.

Supersedes ADR 0002's per-card cache. The key changes from
`(locale, card_id, field_path)` to `(locale, kind, sha256(source))`, which is what makes
#20 and #21 unrepresentable rather than merely corrected: two cards printing the same
Japanese resolve to one slot, and one slot cannot hold two answers.

Everything else about ADR 0002 survives, because it was right. A field is still only
re-sent when its *source* changed. A `manual` entry with a matching hash is still never
overwritten — the value comes from the cache rather than the model, so there is nothing
to overwrite it with. Q&A still churns and card text still does not.

## Why v1 is not migrated

Re-keying the existing 82,098 entries by content produces 3,942 slots in `en`, of which
**2,277 (58%) hold conflicting values** — the same Japanese with two or more different
translations. Only 271 are the easy `{source, one translation}` case. The other 2,006
have two or more genuinely different translations and no rule picks between them; any
picker is a coin flip enshrined as the canonical answer for every card carrying that
string.

So the label and prose kinds are re-translated cold. That is affordable precisely
*because* of content addressing — 3,297 units excluding Q&A, against 2,463 whole cards
per locale under the old scheme.

## Q&A is the exception

Q&A is 596 units but **177,006 of 284,373 source characters — 62% of the corpus.** It is
also the least valuable to re-translate: official rules clarifications, read in a detail
panel, where the Japanese is authoritative anyway.

So Q&A entries are *migrated* from v1 with a winner picked by rule, and marked
`source: "legacy"`. That is a third provenance beside `machine` and `manual`, and it
exists so a later pass can find exactly these and re-translate them without guessing
which entries are old.

## Dual-read

During the migration a locale may be half-converted. `TranslationCacheV2.get` falls back
to a v1 cache on a miss, so a build always produces complete output, and
`migration_status` reports per locale how far along it is. Without that, "is this locale
consistent yet?" would be a question you answer by reading the diff of a 24 MB file.

## Manual entries live in `corrections/`, not here

This file is gitignored, so a `manual` entry written into it is durable but unreviewable —
#18. `load` folds `pipeline/corrections/{locale}.json` in and `save` holds those entries
back out again, which keeps a hand-written translation in exactly one place: the committed
file a contributor can diff. Round-tripping it into this blob as well would leave a copy
that no diff shows and deleting the correction would not remove.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from ..paths import LOCALES_DIR, ensure_dirs
from .cache import TranslationCache
from .units import Unit, unit_hash, unit_key

CACHE_VERSION = 2

# `machine` — produced by the model under the current prompt.
# `manual`  — a human wrote it. Never overwritten while the source hash matches.
# `legacy`  — carried over from the per-card cache during migration. Marks a value
#             translated under the *old* prompt, in a card-specific context, which a
#             later pass should re-do. Findable precisely because it is its own state.
Source = Literal["machine", "manual", "legacy"]


def cache_v2_file() -> Path:
    return LOCALES_DIR / "translation-cache-v2.json"


@dataclass
class Entry:
    """One cached unit translation."""

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


@dataclass
class MigrationStatus:
    """How far one locale has moved to content addressing."""

    locale: str
    total: int
    fresh: int
    legacy: int
    manual: int

    @property
    def missing(self) -> int:
        return self.total - self.fresh

    @property
    def is_complete(self) -> bool:
        return self.missing == 0

    def describe(self) -> str:
        pct = 100 * self.fresh / self.total if self.total else 100
        note = "" if self.is_complete else f", {self.missing} still on v1"
        extra = []
        if self.legacy:
            extra.append(f"{self.legacy} legacy")
        if self.manual:
            extra.append(f"{self.manual} manual")
        suffix = f" ({', '.join(extra)})" if extra else ""
        return f"{self.locale}: {self.fresh}/{self.total} units {pct:.0f}%{note}{suffix}"


@dataclass
class TranslationCacheV2:
    """Per-locale, content-addressed translation state.

    On disk:

        {
          "version": 2,
          "locales": {
            "en": {
              "art_name:9f86d081…": {"hash": "9f86d081…", "value": "Konkon"},
              "qa:e3b0c442…":       {"hash": "e3b0c442…", "value": {…},
                                     "source": "legacy"}
            }
          }
        }

    The hash is stored as well as embedded in the key. Redundant, and kept: it makes an
    entry self-describing when read in isolation, and it is the field `is_fresh` compares
    — so a key that was hand-edited to the wrong hash fails loudly instead of matching.
    """

    entries: dict[str, dict[str, Entry]] = field(default_factory=dict)
    fallback: TranslationCache | None = None

    from_corrections: dict[str, set[str]] = field(default_factory=dict)
    """Keys that came from `corrections/`, per locale. Excluded by `save`.

    Tracked rather than inferred from `source == "manual"`, because the two are not the
    same set during the one run that matters: a cache written before this mechanism
    existed still holds `manual` entries of its own, and silently dropping those on the
    next save would delete hand-written translations that have no committed home yet.
    `holo-data corrections --extract` is what moves them across; until it runs, they stay.
    """

    def mark_from_corrections(self, locale: str, key: str) -> None:
        self.from_corrections.setdefault(locale, set()).add(key)

    def orphan_manual(self, locale: str) -> list[str]:
        """`manual` keys in this locale that no committed correction accounts for.

        These are the pre-#18 entries: durable, but invisible to review. Reported by
        `holo-data corrections` so they get moved rather than discovered years later.
        """
        tracked = self.from_corrections.get(locale, set())
        return sorted(
            key
            for key, entry in self.entries.get(locale, {}).items()
            if entry.source == "manual" and key not in tracked
        )

    # --- Lookup ---

    def get(self, locale: str, key: str) -> Entry | None:
        return self.entries.get(locale, {}).get(key)

    def is_fresh(self, locale: str, unit: Unit) -> bool:
        entry = self.get(locale, unit.key)
        return entry is not None and entry.source_hash == unit_hash(unit.value)

    def value_for(self, locale: str, unit: Unit) -> Any | None:
        """The translation to use, or None. Consults the fallback on a miss."""
        entry = self.get(locale, unit.key)
        if entry is not None and entry.source_hash == unit_hash(unit.value):
            return entry.value
        return None

    def put(
        self,
        locale: str,
        unit: Unit,
        translated: Any,
        source: Source = "machine",
    ) -> None:
        self.entries.setdefault(locale, {})[unit.key] = Entry(
            source_hash=unit_hash(unit.value),
            value=translated,
            source=source,
        )

    def put_raw(
        self, locale: str, key: str, source_value: Any, translated: Any, source: Source
    ) -> None:
        """Write by key, for migration where no `Unit` object exists."""
        self.entries.setdefault(locale, {})[key] = Entry(
            source_hash=unit_hash(source_value),
            value=translated,
            source=source,
        )

    # --- Staleness ---

    def stale(self, locale: str, units: Iterable[Unit]) -> list[Unit]:
        """Units with no current translation for this locale.

        A `manual` entry whose hash still matches is never stale — a human decided it,
        the source has not moved, so it stands. Same rule ADR 0002 established; the key
        is all that changed.
        """
        return [unit for unit in units if not self.is_fresh(locale, unit)]

    def prune(self, locale: str, units: Iterable[Unit]) -> int:
        """Drop entries for units the build no longer contains. Returns the count.

        Content addressing makes this sharper than the per-card version: an entry is
        dead only when *no card anywhere* still prints that string.
        """
        locale_entries = self.entries.get(locale)
        if not locale_entries:
            return 0

        live = {unit.key for unit in units}
        dead = [key for key in locale_entries if key not in live]
        for key in dead:
            del locale_entries[key]
        return len(dead)

    # --- Reporting ---

    def status(self, locale: str, units: Iterable[Unit]) -> MigrationStatus:
        unit_list = list(units)
        fresh = legacy = manual = 0
        for unit in unit_list:
            entry = self.get(locale, unit.key)
            if entry is None or entry.source_hash != unit_hash(unit.value):
                continue
            fresh += 1
            if entry.source == "legacy":
                legacy += 1
            elif entry.source == "manual":
                manual += 1
        return MigrationStatus(
            locale=locale,
            total=len(unit_list),
            fresh=fresh,
            legacy=legacy,
            manual=manual,
        )

    def count(self, locale: str | None = None, source: Source | None = None) -> int:
        locales = [locale] if locale else list(self.entries)
        return sum(
            1
            for loc in locales
            for entry in self.entries.get(loc, {}).values()
            if source is None or entry.source == source
        )

    # --- Persistence ---

    @classmethod
    def load(
        cls,
        path: Path | None = None,
        corrections_dir: Path | None = None,
        apply_corrections: bool | None = None,
    ) -> "TranslationCacheV2":
        """Read the cache, folding the committed corrections over the working copy.

        Corrections are applied *after* the machine entries, so a hand-written value wins
        over whatever the model last produced for that string — which is the entire point
        of writing one.

        **Only for the working cache.** Reading a named file — a backup, a fixture — must
        describe *that file*, or `backup.stats_for` would verify a snapshot by loading it
        and report a `manual` count including entries the snapshot does not contain. So
        corrections are folded in when no path is given, or when a caller names a
        `corrections_dir` explicitly. Pass `apply_corrections` to override either way.
        """
        target = path or cache_v2_file()
        cache = cls()

        if apply_corrections is None:
            apply_corrections = path is None or corrections_dir is not None

        if target.exists():
            raw = json.loads(target.read_text(encoding="utf-8"))
            version = raw.get("version")
            if version != CACHE_VERSION:
                raise ValueError(
                    f"translation cache at {target} is version {version}, expected "
                    f"{CACHE_VERSION}."
                )
            cache.entries = {
                locale: {
                    key: Entry.from_json(value) for key, value in units.items()
                }
                for locale, units in raw.get("locales", {}).items()
            }

        if apply_corrections:
            cache.apply_corrections(corrections_dir)
        return cache

    def apply_corrections(self, directory: Path | None = None) -> int:
        """Fold `corrections/*.json` in as `manual` entries. Returns the count."""
        from ..corrections import load_all  # local: `corrections` imports `units`

        return sum(
            corrections.apply_to(self)
            for corrections in load_all(directory=directory).values()
        )

    def save(self, path: Path | None = None) -> None:
        """Write everything except the entries that came from `corrections/`.

        Holding those back is what keeps a hand-written translation in one place. A
        correction round-tripped into this file would survive its own deletion from the
        committed one, and nothing in a diff would show it.
        """
        target = path or cache_v2_file()
        ensure_dirs()
        payload = {
            "version": CACHE_VERSION,
            "locales": {
                locale: {
                    key: entry.to_json()
                    for key, entry in sorted(units.items())
                    if key not in self.from_corrections.get(locale, set())
                }
                for locale, units in sorted(self.entries.items())
            },
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )


def resolve(
    cache: TranslationCacheV2,
    v1: TranslationCache | None,
    locale: str,
    unit: Unit,
    card_id: str,
    field_path: str,
) -> Any | None:
    """The translation to use for one field, v2 first and v1 as fallback.

    `card_id` and `field_path` exist only to address the v1 cache, and both disappear
    when the last locale migrates. Until then this is what lets `en` be consistent and
    live while `th` is still on the old scheme — a locale ships when it is ready rather
    than all six landing together.
    """
    value = cache.value_for(locale, unit)
    if value is not None:
        return value

    if v1 is None:
        return None

    entry = v1.get(locale, card_id, field_path)
    if entry is not None and entry.source_hash == unit_hash(unit.value):
        return entry.value
    return None
