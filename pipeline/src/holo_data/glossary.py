"""The proper-noun glossary — committed, reviewed, and the source of truth for names.

**Why this exists.** Everything else the pipeline translates is prose, and prose can be
machine-translated per string. Proper nouns cannot: `一伊那尓栖` is "Ninomae Ina'nis", and
no model reliably produces that. They also need to be *identical everywhere they appear*,
which is the defect #20 and #21 record — 41% of characters are spelled inconsistently
across their own cards because each card's name was translated independently.

So names, sets and tags are curated here instead, keyed on the source-language string.
Three consumers read this one file:

- **`translate`** masks these strings out of text before it goes to the model and
  restores them afterwards, so the model never sees a character name and cannot render it
  differently on two cards.
- **`build`** labels the filter dropdowns from it.
- **The site** displays from it — `apps/web/i18n/locales/*.json`'s `names`, `sets` and
  `tags` maps are *generated* from this file, not maintained separately.

This is also the reviewable translation surface #18 asked for. `pipeline/locales/` is
gitignored and 24 MB, so a contributor cannot open it, let alone diff it. This file is
small, committed, and a one-line PR against it is a legible contribution.

**Identity is the source string; display is per-locale.** The same rule `Card.tags` and
`name_ja` already follow — a Japanese string is the stable key, and each locale supplies
what to show. That is why the tag entries key on `Card.tags` (`"0期生"`) rather than the
prefixed display text (`"#0期生"`): the prefix is presentation, and keying on it is what
made the tag filter match nothing (#26).

## Aliases

Characters are referred to by short forms in art and keyword names — `おつルーナ`,
`おつムーナ`, `おつリスー`. A calibration run translated `おつルーナ` as "OtsuLuna" because
only the full name `姫森ルーナ` was a glossary key, so the bare `ルーナ` was never masked.

`aliases` covers those. They are masked longest-first together with full names, which
matters because they nest: `ルーナ` is a substring of `ルーナイト` (the fanbase name, itself
a character-adjacent term). Masking the short one first would corrupt the long one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .paths import PIPELINE_ROOT, _env_path

# Katakana, including the long-vowel mark and the small kana that only occur mid-word.
_KATAKANA = r"[ァ-ヶー]"


def absorbed_in(text: str, haystack: str, at: int | None = None) -> bool:
    """Whether `text` occurs in `haystack` only as part of a longer katakana word.

    Japanese has no spaces, so a substring match is not a word match. `トワ` is the
    character Tokoyami Towa, but it is also the first two syllables of `トワイライト`
    ("twilight") — masking the second would produce "[[Towa]]light".

    The cue is katakana adjacency. A katakana name followed by more katakana is one
    word; followed by a particle, a kanji, or the end of the string, it is a name:

        トワにしか出せない色      -> トワ + に (particle)      -> a name
        トワイライトリゾート       -> トワ + イライト (katakana) -> one word

    Purely mechanical, and it does not attempt semantics: `魔法の森のリスの女の子` — "the
    squirrel girl of the magic forest" — reads as a name reference under this rule,
    because a squirrel and a character named Squirrel are the same characters followed
    by the same particle. That one is a glossary override, not a rule.

    Args:
        text: the candidate name or alias.
        haystack: the string it was found in.
        at: check only the occurrence at this index. When None, returns True only if
            *every* occurrence is absorbed.
    """
    if not text or not haystack:
        return False

    # Only katakana runs are ambiguous this way. A kanji name like `白上` bounds itself,
    # because kanji compounds do not extend a proper noun the way a katakana run does.
    if not re.fullmatch(f"{_KATAKANA}+", text):
        return False

    positions = [at] if at is not None else [
        m.start() for m in re.finditer(re.escape(text), haystack)
    ]
    if not positions:
        return False

    for start in positions:
        end = start + len(text)
        before = haystack[start - 1] if start > 0 else ""
        after = haystack[end] if end < len(haystack) else ""
        adjacent = bool(re.match(_KATAKANA, after)) or bool(
            before and re.match(_KATAKANA, before)
        )
        if not adjacent:
            return False  # at least one occurrence stands alone
    return True

# Committed, unlike everything else the pipeline writes. This is source.
GLOSSARY_DIR = _env_path("HOLO_GLOSSARY_DIR", PIPELINE_ROOT / "glossary")

# The three kinds of proper noun, each keyed on its source-language identity.
#
# `names`  — card names (`Card.translations['ja'].name`), 296 distinct.
# `sets`   — set names (`Card.card_sets`), 35 distinct. Language-independent identity.
# `tags`   — tag identities (`Card.tags`, unprefixed), 41 distinct. NOT the display
#            spelling: `Translation.tags` carries the `#` and is what a locale shows.
KINDS = ("names", "sets", "tags")


class GlossaryError(RuntimeError):
    """Raised for a malformed or inconsistent glossary, with the entry named."""


@dataclass
class Entry:
    """One proper noun: its per-locale display text, and how else it is written.

    `translations` omits the source locale — the key *is* the source-locale text, so
    storing it again would be a second place for it to drift.

    An absent locale means "not yet decided", and callers fall back to the key. That is
    deliberately distinguishable from an entry whose value equals the key, which means
    "reviewed, and it stays in Japanese" — `FUWAMOCO` is not translated because it is
    already the official spelling, and that is a decision, not a gap.
    """

    key: str
    translations: dict[str, str] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    note: str | None = None

    def display(self, locale: str) -> str:
        """What this locale shows. Falls back to the source string."""
        return self.translations.get(locale) or self.key

    def has(self, locale: str) -> bool:
        """Whether a decision has been recorded for this locale."""
        return bool(self.translations.get(locale))

    def maskable(self) -> list[str]:
        """Every string that should be masked for this entry, longest first.

        Longest-first is not a preference. `ルーナ` is a substring of `ルーナイト`, so
        masking the short form first would eat the long one and restore it wrongly.
        """
        return sorted({self.key, *self.aliases}, key=len, reverse=True)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"translations": dict(sorted(self.translations.items()))}
        if self.aliases:
            out["aliases"] = sorted(self.aliases)
        if self.note:
            out["note"] = self.note
        return out

    @classmethod
    def from_json(cls, key: str, raw: dict[str, Any]) -> "Entry":
        if not isinstance(raw, dict):
            raise GlossaryError(f"entry {key!r} must be an object, got {type(raw).__name__}")
        return cls(
            key=key,
            translations={k: v for k, v in (raw.get("translations") or {}).items() if v},
            aliases=list(raw.get("aliases") or []),
            note=raw.get("note"),
        )


@dataclass
class Glossary:
    """One kind of proper noun, for every locale.

    On disk, `glossary/names.json`:

        {
          "白上フブキ": {
            "translations": {"en": "Shirakami Fubuki", "tc": "白上狐狸"},
            "aliases": ["フブキ"]
          }
        }
    """

    kind: str
    entries: dict[str, Entry] = field(default_factory=dict)

    def display(self, key: str, locale: str) -> str:
        """What `locale` shows for `key`. Unknown keys pass through unchanged."""
        entry = self.entries.get(key)
        return entry.display(locale) if entry else key

    def coverage(self, locale: str) -> tuple[int, int]:
        """(decided, total) for one locale — how much of this glossary is filled in."""
        return sum(1 for e in self.entries.values() if e.has(locale)), len(self.entries)

    def missing(self, locale: str) -> list[str]:
        """Keys with no decision recorded for this locale."""
        return sorted(k for k, e in self.entries.items() if not e.has(locale))

    def mask_table(self) -> list[tuple[str, str]]:
        """Every maskable string paired with the entry key it belongs to, longest first.

        Flattened across entries and re-sorted globally, because names from *different*
        entries also nest — masking has to consider the whole table at once, not each
        entry in isolation.
        """
        pairs = [(text, e.key) for e in self.entries.values() for text in e.maskable()]
        return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)

    def validate(self) -> None:
        """Fail on the inconsistencies that would silently corrupt a translation.

        Raises:
            GlossaryError: naming the offending entry.
        """
        seen: dict[str, str] = {}
        for entry in self.entries.values():
            for text in {entry.key, *entry.aliases}:
                if not text.strip():
                    raise GlossaryError(
                        f"{self.kind}: entry {entry.key!r} has an empty key or alias"
                    )
                owner = seen.get(text)
                if owner is not None and owner != entry.key:
                    # An alias claimed by two characters would restore as whichever
                    # entry happened to be masked first — a silent, per-run wrong answer.
                    raise GlossaryError(
                        f"{self.kind}: {text!r} is claimed by both {owner!r} and "
                        f"{entry.key!r}. An alias must identify exactly one entry."
                    )
                seen[text] = entry.key

    # --- Persistence ---

    def path(self, directory: Path | None = None) -> Path:
        return (directory or GLOSSARY_DIR) / f"{self.kind}.json"

    @classmethod
    def load(cls, kind: str, directory: Path | None = None) -> "Glossary":
        if kind not in KINDS:
            raise GlossaryError(f"unknown glossary kind {kind!r}; expected one of {KINDS}")

        target = (directory or GLOSSARY_DIR) / f"{kind}.json"
        if not target.exists():
            return cls(kind=kind)

        raw = json.loads(target.read_text(encoding="utf-8"))
        glossary = cls(
            kind=kind,
            entries={k: Entry.from_json(k, v) for k, v in raw.get("entries", {}).items()},
        )
        glossary.validate()
        return glossary

    def save(self, directory: Path | None = None) -> Path:
        """Write sorted and indented — this file is reviewed as a diff."""
        self.validate()
        target = self.path(directory)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": self.kind,
            "entries": {
                key: self.entries[key].to_json() for key in sorted(self.entries)
            },
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        return target


def load_all(directory: Path | None = None) -> dict[str, Glossary]:
    """Every glossary, keyed by kind."""
    return {kind: Glossary.load(kind, directory) for kind in KINDS}


def i18n_maps(
    glossaries: dict[str, Glossary], locale: str
) -> dict[str, dict[str, str]]:
    """The `names` / `sets` / `tags` maps for one locale's web i18n file.

    Every key is emitted, including those with no decision yet — the value falls back to
    the source string. A complete map means the frontend's lookup either hits or the key
    genuinely does not exist, rather than silently falling back for two different
    reasons.
    """
    return {
        kind: {
            key: entry.display(locale)
            for key, entry in sorted(glossary.entries.items())
        }
        for kind, glossary in glossaries.items()
    }


def coverage_report(
    glossaries: dict[str, Glossary], locales: Iterable[str]
) -> list[str]:
    """Human-readable per-kind, per-locale coverage. Used by `holo-data glossary`."""
    lines = []
    for kind in KINDS:
        glossary = glossaries[kind]
        lines.append(f"{kind} ({len(glossary.entries)} entries)")
        for locale in locales:
            decided, total = glossary.coverage(locale)
            gap = total - decided
            suffix = f", {gap} undecided" if gap else ""
            lines.append(f"  {locale}: {decided}/{total}{suffix}")
    return lines
