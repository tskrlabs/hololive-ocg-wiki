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

## Three kinds of rule, and why they are separate

`RULES` is per-locale literal substitution — one word spelled several ways, where the right
answer is a constant.

`GLOBAL_PATTERNS` is regex, every locale. It exists for the bracket defect (#27): the source
writes card references in CJK angle brackets **6,804 times and ASCII `<>` zero times**, so an
ASCII `<X>` in a translation is always model output. That one is not cosmetic —
`CardDataDetailBlocks.vue` renders `ability_text` through `v-html`, so a browser parses
`<Hakui Koyori>` as an unknown tag and **drops the name from the page**. 54 character names
were invisible on 24 live card pages before this rule existed.

Quote substitution is neither: it needs the *cache*, not a constant. A card's rules text
quotes another card's skill or art name in `「…」`, and the model sometimes leaves it in
Japanese while the same string has a canonical translation one entry away. The fix is to look
that answer up rather than to hard-code it, so it lives in `substitute_quotes` and takes the
unit map as an argument.

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

#: Regex rewrites applied to **every** locale, as `(pattern, replacement, label)`.
#:
#: The label is what a report names, since a compiled pattern reads badly in a diff.
#:
#: **The bracket rule is a rendering fix, not a tidy-up.** `ability_text` reaches the page
#: through `v-html` (`CardDataDetailBlocks.vue`), so an ASCII `<Hakui Koyori>` is parsed as
#: an unknown HTML tag and silently dropped — the rule then reads "attached to 1st or
#: higher" with no name at all. `〈` and `〉` are not HTML metacharacters and render.
#:
#: The inner match is bounded (`{1,40}`, no `<>` inside) so a stray bracket cannot swallow a
#: sentence. Measured before writing it: every `<` in the cache already forms a closed pair,
#: in all six locales, so the bound is a guard against future data rather than current.
GLOBAL_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"<([^<>]{1,40})>"),
        r"〈\1〉",
        "<X> -> 〈X〉 (a card reference the model rendered in ASCII)",
    ),
)

#: The bracket a card reference is written with in the source, and the only correct one.
QUOTE_OPEN, QUOTE_CLOSE = "「", "」"

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
    """Apply one locale's rules, plus the global patterns, to one string.

    Returns the rewritten text and a count per rule, so a caller can report what it did
    rather than only that it did something.

    Both rule kinds run **inside** the protected substitution, so a protected phrase is
    invisible to a regex for the same reason it is invisible to a literal rule: it is not
    in the string while they execute.
    """
    rules = RULES.get(locale, ())
    if not text or (not rules and not GLOBAL_PATTERNS):
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

    for pattern, replacement, label in GLOBAL_PATTERNS:
        working, found = pattern.subn(replacement, working)
        if found:
            counts[(label, "")] = counts.get((label, ""), 0) + found

    for index, phrase in enumerate(protected):
        working = working.replace(_SENTINEL.format(index), phrase)

    return working, counts


#: Label a quote substitution reports under. One label rather than one per string: a
#: report naming 19 individual names would bury the count that matters.
QUOTE_LABEL = "「name」 -> the canonical translation already in the cache"


def substitute_quotes(
    text: str, quotes: dict[str, str]
) -> tuple[str, int]:
    """Replace `「X」` with `「<X translated>」` when X is a string the cache has an answer for.

    Card text quotes another card's skill or art name, and the model sometimes leaves the
    quote in Japanese while translating everything around it — so a card's rules say
    `「人生リセットボタン」` while the skill's own entry says `Tombol Reset Kehidupan`. The
    answer already exists; nothing was looking it up.

    **Exact matches only.** `quotes` is keyed on the whole quoted string, and a substring
    or fuzzy match here would rewrite a quotation into a different card's name — the
    failure mode #78 is a record of, arriving by a different route. A quoted string with
    no entry is left exactly as it is.

    Returns the rewritten text and the number of substitutions.
    """
    if not text or not quotes or QUOTE_OPEN not in text:
        return text, 0

    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        inner = match.group(1)
        translated = quotes.get(inner)
        # `translated == inner` is a decision, not a gap — a name that stays Japanese in
        # this locale. Substituting it would be a no-op that inflates the count.
        if not translated or translated == inner:
            return match.group(0)
        count += 1
        return f"{QUOTE_OPEN}{translated}{QUOTE_CLOSE}"

    pattern = re.compile(
        f"{re.escape(QUOTE_OPEN)}([^{re.escape(QUOTE_CLOSE)}]{{1,60}}){re.escape(QUOTE_CLOSE)}"
    )
    return pattern.sub(replace, text), count


def _normalise_value(
    value: Any, locale: str, quotes: dict[str, str] | None = None
) -> tuple[Any, dict[tuple[str, str], int]]:
    """Rewrite a cache value of either shape — a string, or a Q&A dict."""

    def one(text: str) -> tuple[str, dict[tuple[str, str], int]]:
        out, counts = normalise_text(text, locale)
        if quotes:
            out, n = substitute_quotes(out, quotes)
            if n:
                counts = {**counts, (QUOTE_LABEL, ""): n}
        return out, counts

    if isinstance(value, str):
        return one(value)

    if isinstance(value, dict):
        out = dict(value)
        totals: dict[tuple[str, str], int] = {}
        for name in PROSE_FIELDS:
            text = value.get(name)
            if not isinstance(text, str):
                continue
            out[name], counts = one(text)
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
    entries: dict[str, Any], locale: str, quotes: dict[str, str] | None = None
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

        new_value, counts = _normalise_value(value, locale, quotes)

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

    Covers the global patterns as well as the locale's literal rules. It has to: a regex
    that half-applies leaves exactly the same kind of residue, and a check that silently
    ignores a whole rule kind reports `✓` for a pass that did not finish.

    Quote substitution is deliberately **not** checked here. A `「…」` with no cache answer
    is a normal, permanent state — most quoted strings are flavour prose, not names — so
    counting them would report failure on every run for something that is not a defect.
    """
    rules = RULES.get(locale, ())
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
            for pattern, _, label in GLOBAL_PATTERNS:
                found = len(pattern.findall(text))
                if found:
                    counts[label] = counts.get(label, 0) + found

    return counts
