"""Removing proper nouns from text before translation, and putting them back after.

**This is the mechanism the whole rework turns on.** The current prompt asks the model not
to translate character names; it complies 47-81% of the time, unpredictably, and that
inconsistency *is* issues #20 and #21. A request the model can ignore is replaced here by
one it cannot: the name is not in the text it receives.

    白上フブキのこんこん     ->  [[N7]]のこんこん     ->  [[N7]]'s Konkon
                                                     ->  Shirakami Fubuki's Konkon

The name comes back from the glossary, so every occurrence on every card gets the same
spelling by construction. There is no path by which two cards disagree.

## Three rules, each forced by the data

**Longest first.** 75 pairs in the real mask table nest: `森カリオペ` inside `森カリオペの鎌`,
`Promise` inside `時の支配者 -Promise-`, `クレイジー` inside `クレイジー・オリー`. Masking the
short one first leaves a fragment of the long one stranded, and the restored text is
subtly wrong rather than obviously broken.

**Katakana word boundaries.** Japanese has no spaces, so a substring match is not a word
match. `トワ` is Tokoyami Towa and also the first two syllables of `トワイライト`
("twilight"). `glossary.absorbed_in` decides, and this module simply obeys it.

**Already-masked regions are untouchable.** A token like `[[N7]]` is ASCII, and a glossary
key such as `35P` or `Otomo` is also ASCII — so a naive second pass can match *inside* a
token it already placed. Masking therefore walks the string once and never re-examines
what it has emitted.

## Failure is loud

`unmask` raises on a token the model dropped, mangled, or invented. That is deliberate and
it is the reason this module exists as its own phase: a silently half-restored string
would enter the cache, be published, and be discovered by a reader months later. A run
that stops is recoverable; a corrupted cache entry is not distinguishable from a bad
translation after the fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from ..glossary import Glossary, absorbed_in

# `[[N0]]`, `[[N1]]`, ... ASCII and bracket-delimited so it survives a model that
# reflows CJK text around it. Two brackets rather than one because single brackets
# appear in the source data (`[ターンに1回]`), and a token that collides with real
# game text would be mangled by the model as a matter of course.
TOKEN_PATTERN = re.compile(r"\[\[N(\d+)\]\]")


def token_for(index: int) -> str:
    return f"[[N{index}]]"


class MaskError(RuntimeError):
    """Raised when a masked string cannot be restored exactly.

    Always fatal for the unit it concerns. The caller drops that unit rather than
    caching a partially-restored value.
    """


@dataclass
class Masked:
    """One masked string and everything needed to restore it.

    Two maps, because restoring has two different jobs.

    `tokens` maps each placeholder to its **glossary key**. An alias and its full name
    resolve to the same entry, so `[[N3]]` placed over `フブキ` restores as the canonical
    "Shirakami Fubuki" rather than a translated fragment. That is the whole point: the
    alias is how the *source* refers to them; the glossary decides how the translation
    does.

    `surfaces` maps each placeholder to the **text actually matched**. Needed because
    the first is deliberately lossy — a check that `mask` preserves information cannot
    use a map that canonicalises `トワ` to `常闇トワ` and calls the difference success.
    Found by testing: `verify_roundtrip` passed vacuously for every full name and failed
    for every alias, for a reason that had nothing to do with masking being wrong.
    """

    text: str
    tokens: dict[str, str] = field(default_factory=dict)
    surfaces: dict[str, str] = field(default_factory=dict)
    original: str = ""

    @property
    def is_masked(self) -> bool:
        return bool(self.tokens)

    def restore_source(self) -> str:
        """Put the original Japanese back, exactly — used to verify losslessness."""
        out = self.text
        for token, surface in self.surfaces.items():
            out = out.replace(token, surface)
        return out


def mask(text: str, table: Iterable[tuple[str, str]]) -> Masked:
    """Replace every glossary name in `text` with a placeholder.

    Args:
        text: the source string.
        table: `(matchable_text, glossary_key)` pairs, longest first — as produced by
            `Glossary.mask_table()`. Order is the caller's responsibility because it is
            a property of the whole table, not of any one entry.

    Returns:
        A `Masked` carrying the placeholder text and the token map.
    """
    if not text:
        return Masked(text=text, original=text)

    pairs = list(table)
    tokens: dict[str, str] = {}
    surfaces: dict[str, str] = {}
    # Keyed on the *surface*, not the glossary key: a string carrying both `白上フブキ`
    # and `フブキ` needs two tokens, or restoring the source would put the full name
    # where the alias was. Both still resolve to the same translation.
    by_surface: dict[str, str] = {}

    # Walk left to right, emitting either a token or one source character. Regions
    # already emitted are never re-examined, which is what stops a later ASCII name
    # from matching inside a token this pass just wrote.
    out: list[str] = []
    position = 0

    while position < len(text):
        matched = None
        for candidate, key in pairs:
            if not text.startswith(candidate, position):
                continue
            # `absorbed_in` asks about the whole string; ask it about *this* occurrence,
            # so `トワとトワイライト` masks the first and leaves the second.
            if absorbed_in(candidate, text, at=position):
                continue
            matched = (candidate, key)
            break

        if matched is None:
            out.append(text[position])
            position += 1
            continue

        candidate, key = matched
        token = by_surface.get(candidate)
        if token is None:
            token = token_for(len(tokens))
            tokens[token] = key
            surfaces[token] = candidate
            by_surface[candidate] = token
        out.append(token)
        position += len(candidate)

    return Masked(
        text="".join(out), tokens=tokens, surfaces=surfaces, original=text
    )


def unmask(text: str, masked: Masked, glossary: Glossary, locale: str) -> str:
    """Substitute each placeholder with the glossary's translation for that locale.

    Args:
        text: the model's reply, still carrying the placeholders.
        masked: what `mask` produced, for the token map.
        glossary: the names glossary.
        locale: which translation to restore.

    Returns:
        The reply with every placeholder replaced.

    Raises:
        MaskError: if a token is missing, duplicated into existence, or unrecognised.
            Never returns a partially-restored string.
    """
    expected = set(masked.tokens)
    found = {match.group(0) for match in TOKEN_PATTERN.finditer(text)}

    if missing := expected - found:
        raise MaskError(
            f"the model dropped {len(missing)} placeholder(s): {sorted(missing)}\n"
            f"  sent:     {masked.text!r}\n"
            f"  received: {text!r}\n"
            "The name would be lost, so this unit is not cached."
        )

    if unknown := found - expected:
        # A model that invents `[[N9]]` has misunderstood the instruction badly enough
        # that the rest of its output is not trustworthy either.
        raise MaskError(
            f"the model invented {len(unknown)} placeholder(s): {sorted(unknown)}\n"
            f"  sent:     {masked.text!r}\n"
            f"  received: {text!r}"
        )

    out = text
    for token, key in masked.tokens.items():
        entry = glossary.entries.get(key)
        if entry is None:
            raise MaskError(
                f"{token} maps to {key!r}, which is not in the glossary. "
                "The glossary changed between masking and unmasking."
            )
        # The surface is passed so an alias can restore to its own short form —
        # `モココ` -> "Mococo", not "Mococo Abyssgard". Falls back to the full name
        # when the alias has no decision for this locale.
        out = out.replace(token, entry.display(locale, surface=masked.surfaces.get(token)))

    return out


def verify_roundtrip(text: str, table: Iterable[tuple[str, str]]) -> None:
    """Assert that masking is reversible for one string.

    Restoring the *source* text — rather than a translation — isolates masking from
    everything else. If this fails, the masker is losing information regardless of what
    any model does with the output.

    Raises:
        MaskError: with both strings, when they differ.
    """
    masked = mask(text, table)
    restored = masked.restore_source()
    if restored != text:
        raise MaskError(
            "masking is not reversible for this string:\n"
            f"  original: {text!r}\n"
            f"  masked:   {masked.text!r}\n"
            f"  restored: {restored!r}"
        )


@dataclass
class MaskReport:
    """What masking would do across a corpus, for review before any spend."""

    total: int = 0
    masked: int = 0
    occurrences: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def record(self, text: str, table: Iterable[tuple[str, str]]) -> None:
        self.total += 1
        pairs = list(table)
        result = mask(text, pairs)

        if result.is_masked:
            self.masked += 1
            for key in result.tokens.values():
                self.occurrences[key] = self.occurrences.get(key, 0) + 1

        if result.restore_source() != text:
            self.failures.append(text)

    def lines(self, top: int = 25) -> list[str]:
        out = [
            f"{self.masked}/{self.total} strings carry at least one name "
            f"({100 * self.masked / self.total:.0f}%)" if self.total else "no strings",
            f"{len(self.occurrences)} distinct names matched",
        ]
        if self.failures:
            out.append(f"⚠ {len(self.failures)} string(s) do NOT round-trip:")
            out.extend(f"    {text!r}" for text in self.failures[:10])
        else:
            out.append("✓ every string round-trips exactly")

        out.append("")
        out.append(f"most-masked names (top {top}):")
        ranked = sorted(self.occurrences.items(), key=lambda kv: (-kv[1], kv[0]))
        out.extend(f"  {count:4d}  {key}" for key, count in ranked[:top])
        return out
