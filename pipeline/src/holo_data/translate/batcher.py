"""Batching translatable units into API calls.

Replaces v1's one-card-per-call loop. The old code sent one card per request **per
locale**, so a cold full run was 2,463 × 6 = **14,778 calls**. Batching distinct units by
kind brings that to roughly 600, because the distinct-unit corpus is 284 KB against 1.42
MB of whole-card text and each string is sent once rather than once per card printing it.

## Why batches are per kind

A batch shares one prompt, and the prompt is per kind (see `prompts_v2`). Mixing an art
name and an effect into one call means one instruction has to cover both, which is the
compromise the old whole-card prompt made.

## Why a character budget rather than a unit count

Units are wildly uneven: a tag is 4 characters and a Q&A entry averages 297. A fixed count
would send 50 tags in one tiny call and 50 Q&A entries in one that risks the reply limit.
Packing to a character budget makes every call roughly the same size.

## Failure is per batch, not per run

A batch whose reply is unparseable, or whose units come back with lost mask tokens, is
reported and skipped — the other batches still land. A partial run is fine because the
cache is the unit of progress: whatever succeeded is cached, and a re-run sends only what
is still stale. That is the same property ADR 0002 established, now at unit granularity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable

from .masking import MaskError, Masked, mask, unmask
from .prompts_v2 import build_prompt, is_prose
from .units import Unit

# Characters of source text per call. Chosen so a batch's *reply* stays well inside a
# single response: the largest kind (Q&A) averages ~297 chars per unit, so 4,000 is ~13
# Q&A entries or ~400 tags. Larger batches are cheaper per unit but lose more work when
# one reply is malformed.
DEFAULT_CHAR_BUDGET = 4000


@dataclass
class BatchItem:
    """One unit inside a batch, with its masked form."""

    unit: Unit
    masked: Masked

    @property
    def context(self) -> dict[str, str]:
        return self.unit.context.as_dict()


@dataclass
class Batch:
    """One API call: units of a single kind, for a single locale."""

    kind: str
    locale: str
    items: list[BatchItem] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.items)

    @property
    def char_count(self) -> int:
        return sum(item.unit.char_count for item in self.items)

    @property
    def has_context(self) -> bool:
        return any(item.context for item in self.items)

    def payload(self) -> str:
        """The JSON the model receives: `{id: text}`, or `{id: {text, context}}`.

        Ids are positional strings rather than content hashes — a 64-character key
        repeated 40 times is pure token cost, and the mapping back is positional anyway.
        """
        entries: dict[str, object] = {}
        for index, item in enumerate(self.items):
            value = item.masked.text if isinstance(item.unit.value, str) else item.unit.value
            if item.context and is_prose(self.kind):
                entries[str(index)] = {"text": value, "context": item.context}
            else:
                entries[str(index)] = value
        return json.dumps(entries, ensure_ascii=False, indent=2)

    def prompt(self) -> str:
        return build_prompt(
            kind=self.kind,
            locale=self.locale,
            payload=self.payload(),
            with_context=self.has_context and is_prose(self.kind),
        )


@dataclass
class BatchResult:
    """What came back from one batch."""

    batch: Batch
    translations: dict[str, object] = field(default_factory=dict)
    """unit key -> translated value, for units that came back intact."""
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> int:
        return len(self.translations)


def build_batches(
    units: Iterable[Unit],
    locale: str,
    table: list[tuple[str, str]],
    char_budget: int = DEFAULT_CHAR_BUDGET,
) -> list[Batch]:
    """Group units into per-kind batches, masking each on the way in.

    Units are sorted within a kind by their content address, so batch composition is
    deterministic — a re-run after a partial failure sends the same groupings, which
    makes "batch 7 failed" a reproducible statement rather than a coincidence of dict
    ordering.
    """
    by_kind: dict[str, list[Unit]] = {}
    for unit in units:
        by_kind.setdefault(unit.kind, []).append(unit)

    batches: list[Batch] = []
    for kind in sorted(by_kind):
        current = Batch(kind=kind, locale=locale)
        for unit in sorted(by_kind[kind], key=lambda u: u.key):
            # Only strings are masked. Q&A units are dicts, and their nested text is
            # masked field-by-field at send time rather than here.
            masked = (
                mask(unit.value, table)
                if isinstance(unit.value, str)
                else Masked(text="", original="")
            )
            if current.items and current.char_count + unit.char_count > char_budget:
                batches.append(current)
                current = Batch(kind=kind, locale=locale)
            current.items.append(BatchItem(unit=unit, masked=masked))
        if current.items:
            batches.append(current)

    return batches


def parse_reply(text: str) -> dict[str, object]:
    """Pull the JSON object out of a model reply.

    Models sometimes wrap JSON in prose or a fence despite being told not to, so this
    takes everything between the first `{` and the last `}` — v1's approach, kept because
    it has worked against this endpoint for a year.
    """
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("no JSON object found in the reply")
    return json.loads(text[start:end])


def collect_result(
    batch: Batch, reply: dict[str, object], restorer: object
) -> BatchResult:
    """Match a reply back to its units, unmasking and validating each.

    A unit whose mask tokens did not survive is **dropped, not stored**. It stays stale
    and is retried on the next run, which is strictly better than caching a name-mangled
    string that would then need a human to notice it.
    """
    result = BatchResult(batch=batch)

    for index, item in enumerate(batch.items):
        raw = reply.get(str(index))
        if raw is None:
            result.failures.append(f"{item.unit.key}: missing from the reply")
            continue

        if not isinstance(item.unit.value, str):
            # Q&A and other structured units come back as objects; nothing to unmask.
            result.translations[item.unit.key] = raw
            continue

        if not isinstance(raw, str):
            result.failures.append(
                f"{item.unit.key}: expected a string, got {type(raw).__name__}"
            )
            continue

        try:
            result.translations[item.unit.key] = unmask(
                raw, item.masked, restorer, batch.locale
            )
        except MaskError as exc:
            result.failures.append(f"{item.unit.key}: {str(exc).splitlines()[0]}")

    return result


@dataclass
class BatchPlan:
    """What a run would send, for `--dry-run`."""

    batches: list[Batch]

    @property
    def call_count(self) -> int:
        return len(self.batches)

    @property
    def unit_count(self) -> int:
        return sum(batch.size for batch in self.batches)

    @property
    def char_count(self) -> int:
        return sum(batch.char_count for batch in self.batches)

    def by_kind(self) -> dict[str, tuple[int, int, int]]:
        """kind -> (batches, units, chars)"""
        out: dict[str, tuple[int, int, int]] = {}
        for batch in self.batches:
            calls, units, chars = out.get(batch.kind, (0, 0, 0))
            out[batch.kind] = (calls + 1, units + batch.size, chars + batch.char_count)
        return out

    def lines(self) -> list[str]:
        out = []
        for kind, (calls, units, chars) in sorted(self.by_kind().items()):
            out.append(f"  {kind:15s} {calls:3d} calls  {units:5d} units  {chars:7,d} chars")
        return out
