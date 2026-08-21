"""Hand-written translation fixes — committed, reviewed, and the only home for `manual`.

**Why this exists.** D14 promised outside contributors a reviewable path for the fix people
actually want to make: correcting a bad translation. ADR 0002 replaced the `corrections/`
overlay with cache entries, which was strictly better for *durability* — a `manual` entry
is never overwritten because the value comes from the cache rather than the model — but it
moved the editable file into `pipeline/locales/`, which is gitignored and 8.5 MB. So the
file a contributor would edit did not exist in a clone, and a translation fix could only be
reported, never sent. That gap is #18, and this closes it.

The proper-noun half closed earlier: `glossary/` holds names, sets and tags. This is the
other half — a correction to an arbitrary *field*, a badly worded effect or a wrong Q&A
answer, which the glossary has nothing to say about.

## The key is derived, never written

An entry names its `kind` and its Japanese `source`. The cache key — `art_name:b8ad10fc…` —
is computed from those by `unit_key`, exactly as `translate` computes it. It is deliberately
**not** stored:

- A contributor must not have to run sha256 to send a one-line PR. That alone would make
  this as unusable as the gitignored cache it replaces.
- A stored key is a second place for the same fact to live, and `resolve`'s whole lesson
  (#78) is that a translation keyed to one source and holding another is invisible until a
  reader finds it.

The check that replaces it is stronger and needs no API key: `holo-data corrections` looks
up every `(kind, source)` in the current build and reports any that no card prints. A typo
in the Japanese is then a loud "no card prints this string", not a silent no-op.

## Corrections are the cache's only `manual` entries

`TranslationCacheV2.load` folds this in and `save` writes it back out, so a correction
lives in exactly one place: here. That is what makes removing one *work* — delete the lines,
and the entry is gone on the next build. Persisting into the cache as well would leave a
copy behind that no diff shows and nothing removes.

The durability guarantee is unchanged. `stale()` still never returns a `manual` unit whose
source hash matches, so `translate` never re-sends it and no model reply can overwrite it.
A human decided it; the source has not moved; it stands.

## What a correction is not

It is not a place to pin machine output you happen to like. `manual` means a human decided
this string, and a later pass looking for "what did a person actually choose?" has to be
able to trust it — the same reason `glossary.Entry.review` exists. Re-translated text that
came back correct is `machine`, and should stay that way.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from .paths import CORRECTIONS_DIR, corrections_file
from .translate.units import ALL_KINDS, Unit, unit_hash, unit_key

if TYPE_CHECKING:  # pragma: no cover - import only for annotations
    from .translate.cache_v2 import TranslationCacheV2


class CorrectionError(RuntimeError):
    """Raised for a malformed corrections file, with the offending entry named."""


@dataclass
class Correction:
    """One hand-written translation, addressed by what it translates.

    `source` is the Japanese as the card prints it — byte-identical, because it is hashed.
    A trailing `～` or a `…` written as three dots is a different string and will not match.
    """

    kind: str
    source: Any
    value: Any
    note: str | None = None

    @property
    def key(self) -> str:
        """The cache key this correction fills. Derived, never stored — see the module."""
        return unit_key(self.kind, self.source)

    @property
    def source_hash(self) -> str:
        return unit_hash(self.source)

    def validate(self) -> None:
        if self.kind not in ALL_KINDS:
            raise CorrectionError(
                f"unknown kind {self.kind!r}; expected one of {', '.join(ALL_KINDS)}"
            )
        if not self.source or (isinstance(self.source, str) and not self.source.strip()):
            raise CorrectionError(f"{self.kind}: `source` is empty")
        if self.value is None or (isinstance(self.value, str) and not self.value.strip()):
            raise CorrectionError(f"{self.kind} {self.source!r}: `value` is empty")

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "source": self.source,
            "value": self.value,
        }
        if self.note:
            out["note"] = self.note
        return out

    @classmethod
    def from_json(cls, raw: Any) -> "Correction":
        if not isinstance(raw, dict):
            raise CorrectionError(
                f"each correction must be an object, got {type(raw).__name__}"
            )
        missing = [k for k in ("kind", "source", "value") if k not in raw]
        if missing:
            raise CorrectionError(
                f"correction is missing {', '.join(missing)}: {raw!r}"
            )
        correction = cls(
            kind=raw["kind"],
            source=raw["source"],
            value=raw["value"],
            note=raw.get("note"),
        )
        correction.validate()
        return correction


@dataclass
class Corrections:
    """Every hand-written fix for one locale.

    On disk, `corrections/tc.json`:

        {
          "locale": "tc",
          "corrections": [
            {
              "kind": "art_name",
              "source": "おつルーナ",
              "value": "辛苦啦露娜～",
              "note": "F-003"
            }
          ]
        }

    A list rather than an object keyed by hash, so nothing here requires a tool to write.
    """

    locale: str
    items: list[Correction] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def validate(self) -> None:
        """Fail on the shapes that would silently do the wrong thing.

        Raises:
            CorrectionError: naming the offending entry.
        """
        seen: dict[str, Correction] = {}
        for item in self.items:
            item.validate()
            existing = seen.get(item.key)
            if existing is not None:
                # Two corrections for one string is two answers for a slot that holds
                # one. Whichever is applied last would win, silently and by file order.
                raise CorrectionError(
                    f"{self.locale}: {item.kind} {item.source!r} is corrected twice "
                    f"(to {existing.value!r} and {item.value!r}). One string, one answer."
                )
            seen[item.key] = item

    def apply_to(self, cache: "TranslationCacheV2") -> int:
        """Write every correction into `cache` as a `manual` entry. Returns the count.

        Applied after load, so a correction wins over whatever the model last produced for
        that string — which is the point of writing one.
        """
        self.validate()
        for item in self.items:
            cache.put_raw(
                self.locale, item.key, item.source, item.value, "manual"
            )
            cache.mark_from_corrections(self.locale, item.key)
        return len(self.items)

    def unknown(self, units: Iterable[Unit]) -> list[Correction]:
        """Corrections whose `(kind, source)` no card in the build prints.

        The check that replaces a stored hash. A typo in the Japanese, or a correction left
        behind after the official site reworded a card, shows up here rather than as an
        entry that quietly matches nothing.
        """
        live = {unit.key for unit in units}
        return [item for item in self.items if item.key not in live]

    # --- Persistence ---

    @classmethod
    def load(cls, locale: str, directory: Path | None = None) -> "Corrections":
        target = (
            (directory / f"{locale}.json") if directory else corrections_file(locale)
        )
        if not target.exists():
            return cls(locale=locale)

        raw = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise CorrectionError(f"{target}: expected an object at the top level")

        declared = raw.get("locale")
        if declared and declared != locale:
            # The filename is what every caller addresses; a mismatched `locale` key
            # means the file was copied and half-edited.
            raise CorrectionError(
                f"{target} declares locale {declared!r} but is named {locale!r}"
            )

        corrections = cls(
            locale=locale,
            items=[Correction.from_json(item) for item in raw.get("corrections", [])],
        )
        corrections.validate()
        return corrections

    def save(self, directory: Path | None = None) -> Path:
        """Write indented and stably ordered — this file exists to be read as a diff."""
        self.validate()
        target = (
            (directory / f"{self.locale}.json")
            if directory
            else corrections_file(self.locale)
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "locale": self.locale,
            "corrections": [
                item.to_json()
                for item in sorted(
                    self.items,
                    key=lambda c: (c.kind, json.dumps(c.source, ensure_ascii=False)),
                )
            ],
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        return target


def load_all(
    locales: Iterable[str] | None = None, directory: Path | None = None
) -> dict[str, Corrections]:
    """Corrections for every locale that has a file.

    With no `locales`, discovers them from the directory — which is what `cache_v2.load`
    wants, since it has no locale list of its own and must not need one.
    """
    if locales is None:
        source = directory or CORRECTIONS_DIR
        locales = (
            sorted(path.stem for path in source.glob("*.json"))
            if source.exists()
            else []
        )
    return {locale: Corrections.load(locale, directory) for locale in locales}
