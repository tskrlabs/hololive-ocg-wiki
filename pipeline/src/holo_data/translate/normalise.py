"""Deterministic spelling fixes applied to cached translations, with no API call.

Some defects are not translation *judgements* — they are one word spelled several ways by
the same model in the same run. #28 is the case this exists for: `エール`, the game's cheer
resource, came back from the Thai run as four different strings, one of which
(`เอール`) is Thai `เอ` followed by katakana `ール` and is not a word in any language.

The glossary already settles the term — all six cheer cards render it `เยล` (`黄エール`
-> `เยลสีเหลือง`) — but the glossary only masks *card names*, so nothing constrains the
same word appearing mid-sentence in an effect. This module is that constraint, applied
after the fact.

## Why rewrite the cache rather than re-translate

A re-translation costs an API call per batch and would not fix it: the model produced the
inconsistency in the first place, and nothing about a second run makes it choose one
spelling. A rewrite is deterministic, free, reviewable as a diff, and re-runnable.

## Why an ordered list rather than a regex alternation

The variants nest — `เอล` is a prefix of `เอลล์` and a substring of `เอール`. Applying the
short one first would leave `ล์` or `ール` stranded, producing a *fifth* variant rather
than fixing the four. Longest-first is the same rule `mask_table` uses, for the same
reason.

## The guard that matters

**`โนเอล` is Shirogane Noel.** A blind `เอล` -> `เยล` turns her into `โนเยล` in nine
places. The glossary says `白銀ノエル` -> `ชิโรกาเนะ โนเอล`, so this is not a judgement
call — it is a name the rewrite must not touch.

`PROTECTED` is the mechanism, and it works by *substitution*: the phrase is replaced by a
sentinel before any rule runs, so it is invisible while they execute — a rule cannot match
inside it, and cannot match across its boundary either. `normalise_locale`'s before/after
count is a backstop for a rule that damages a phrase some other way, not the thing doing
the protecting.

⚠️ Which means the list is load-bearing and the guard cannot cover for it: **delete an
entry from `PROTECTED` and the corruption becomes silent**, because there is no longer
anything to count. `test_removing_a_protection_is_what_the_guard_cannot_see` pins that
blind spot deliberately, and `test_shirogane_noel_is_protected` fails if this specific
name is ever dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Fields of a structured (Q&A) unit that carry prose. Mirrors `masking.MASKABLE_FIELDS`
# and exists for the same reason: `title` is a question number and `related_cards` is
# source markup the site parses.
PROSE_FIELDS = ("question", "answer")

#: Strings that must survive a rewrite untouched, because a rule would otherwise corrupt
#: them. Substituted out before the rules run and restored after — the same shape as
#: masking, at a much smaller scale.
PROTECTED: dict[str, tuple[str, ...]] = {
    # Shirogane Noel. `เอล` -> `เยล` would make her `โนเยล` in 9 places.
    "th": ("โนเอล",),
}

#: `locale -> [(wrong, right), ...]`. **A rule must never precede one it is a prefix of.**
#:
#: Not simply "longest first", which is what `mask_table` needs and what this looked like
#: it needed: `เอลล์` is 5 codepoints and `เอール` is 4, so length ordering would put the
#: 5 first and say nothing useful — they do not overlap at all. The property that actually
#: matters is prefix containment, and there is exactly one pair with it: `เอล` ⊂ `เอลล์`.
#: Running the short one first would leave `ล์` stranded, producing `เยลล์` — a *fifth*
#: spelling rather than a fix. `test_no_rule_precedes_one_it_is_a_prefix_of` pins it.
RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "th": (
        # Thai `เอ` + katakana `ール` — the clearest defect of the four. Every occurrence
        # is byte-identical, so it is one systematic slip rather than N judgements.
        ("เอール", "เยล"),
        # A final `ล์` on the same word. Must precede the bare form below.
        ("เอลล์", "เยล"),
        ("เอล", "เยล"),
    ),
}

# `\x00` is not in any translation and cannot be produced by the rules, so it is safe as
# a placeholder. Indexed, because a locale may protect more than one string.
_SENTINEL = "\x00{}\x00"


@dataclass
class NormaliseReport:
    """What a normalisation pass did, for review before it is saved."""

    locale: str
    entries_changed: int = 0
    #: `(wrong, right) -> count`. Keyed on the rule rather than the string, so a
    #: report says which rule fired rather than only that something changed.
    replacements: dict[tuple[str, str], int] = field(default_factory=dict)
    examples: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total_replacements(self) -> int:
        return sum(self.replacements.values())

    def lines(self) -> list[str]:
        if not self.replacements:
            return [f"{self.locale}: nothing to normalise"]

        out = [
            f"{self.locale}: {self.total_replacements} replacement(s) "
            f"across {self.entries_changed} cache entr(ies)"
        ]
        out.extend(
            f"    {count:4d}  {wrong!r} -> {right!r}"
            for (wrong, right), count in sorted(
                self.replacements.items(), key=lambda kv: -kv[1]
            )
        )
        for before, after in self.examples[:3]:
            out.append(f"    before: {before}")
            out.append(f"    after : {after}")
        return out


def normalise_text(text: str, locale: str) -> tuple[str, dict[tuple[str, str], int]]:
    """Apply one locale's rules to one string.

    Returns the rewritten text and a count per rule, so a caller can report what it did
    rather than only that it did something.
    """
    rules = RULES.get(locale)
    if not rules or not text:
        return text, {}

    protected = PROTECTED.get(locale, ())
    working = text
    for index, phrase in enumerate(protected):
        working = working.replace(phrase, _SENTINEL.format(index))

    counts: dict[tuple[str, str], int] = {}
    for wrong, right in rules:
        found = working.count(wrong)
        if found:
            counts[(wrong, right)] = found
            working = working.replace(wrong, right)

    for index, phrase in enumerate(protected):
        working = working.replace(_SENTINEL.format(index), phrase)

    return working, counts


def _normalise_value(value: Any, locale: str) -> tuple[Any, dict[tuple[str, str], int]]:
    """Rewrite a cache value of either shape — a string, or a Q&A dict."""
    if isinstance(value, str):
        return normalise_text(value, locale)

    if isinstance(value, dict):
        out = dict(value)
        totals: dict[tuple[str, str], int] = {}
        for name in PROSE_FIELDS:
            text = value.get(name)
            if not isinstance(text, str):
                continue
            out[name], counts = normalise_text(text, locale)
            for rule, n in counts.items():
                totals[rule] = totals.get(rule, 0) + n
        return out, totals

    return value, {}


def _count(value: Any, needle: str) -> int:
    """Occurrences of `needle` across every prose string in a cache value."""
    if isinstance(value, str):
        return value.count(needle)
    if isinstance(value, dict):
        return sum(
            text.count(needle)
            for name in PROSE_FIELDS
            if isinstance(text := value.get(name), str)
        )
    return 0


def normalise_locale(
    entries: dict[str, Any], locale: str
) -> tuple[dict[str, Any], NormaliseReport]:
    """Rewrite every entry of one locale, returning the new values and a report.

    Only changed entries appear in the returned mapping, so a caller can write exactly
    those back and leave every other entry's `source` and hash alone.

    Raises:
        ValueError: if a protected phrase's count changed. That is the failure this
            module is most at risk of — a rule that eats a character name — and it is
            checked rather than reasoned about, because the ordering that prevents it is
            easy to break with a well-meant new rule.
    """
    report = NormaliseReport(locale=locale)
    changed: dict[str, Any] = {}
    protected = PROTECTED.get(locale, ())
    before_counts = {phrase: 0 for phrase in protected}
    after_counts = {phrase: 0 for phrase in protected}

    for key, value in entries.items():
        for phrase in protected:
            before_counts[phrase] += _count(value, phrase)

        new_value, counts = _normalise_value(value, locale)

        for phrase in protected:
            after_counts[phrase] += _count(new_value, phrase)

        if not counts:
            continue

        changed[key] = new_value
        report.entries_changed += 1
        for rule, n in counts.items():
            report.replacements[rule] = report.replacements.get(rule, 0) + n

        if len(report.examples) < 3 and isinstance(value, str):
            report.examples.append((value[:90], new_value[:90]))

    for phrase in protected:
        if before_counts[phrase] != after_counts[phrase]:
            raise ValueError(
                f"normalising {locale!r} changed the count of the protected phrase "
                f"{phrase!r}: {before_counts[phrase]} -> {after_counts[phrase]}. "
                "A rule is eating a name it must not touch."
            )

    return changed, report


def remaining(entries: dict[str, Any], locale: str) -> dict[str, int]:
    """Variants still present after a pass — the check that it actually finished.

    A pass that reports replacements but leaves variants behind has produced a fifth
    spelling rather than removing four, which is the specific way an ordered rewrite goes
    wrong.
    """
    rules = RULES.get(locale)
    if not rules:
        return {}

    protected = PROTECTED.get(locale, ())
    counts: dict[str, int] = {}
    for value in entries.values():
        texts: list[str] = []
        if isinstance(value, str):
            texts = [value]
        elif isinstance(value, dict):
            texts = [
                text
                for name in PROSE_FIELDS
                if isinstance(text := value.get(name), str)
            ]

        for text in texts:
            for phrase in protected:
                text = text.replace(phrase, "")
            for wrong, _ in rules:
                found = len(re.findall(re.escape(wrong), text))
                if found:
                    counts[wrong] = counts.get(wrong, 0) + found

    return counts
