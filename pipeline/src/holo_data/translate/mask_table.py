"""Assembling the mask table from every glossary that contributes to it.

Names were the obvious case. Calibration surfaced a second one: **25% of prose strings
(323 of 1,312) contain a `#tag` reference**, and the model rendered them three different
ways in a single run — `#3期生` became "#3rd Generation", `#こよラボ` stayed Japanese, and
"#KoyoLabo" was invented. Meanwhile the tag chips and the filter dropdown render the
glossary's translation, so a card's own rules text disagreed with its own chips.

That is the same defect as names, one layer down, so it gets the same mechanism.

**Tags are safer to mask than names.** The `#` prefix is an explicit delimiter, so `#ID`
cannot be absorbed into a longer word the way a bare katakana run can — the boundary rule
that `トワ`/`トワイライト` needs does not have to carry tags. Three real pairs still nest
(`#ID` inside `#ID1期生`), which longest-first ordering already handles.

**Sets are deliberately not masked.** They appear as `card_sets`, which is
language-independent data the API serves directly — never inside translated prose. Adding
them would grow the table for no occurrences.
"""

from __future__ import annotations

from ..glossary import Glossary

# What a tag looks like inside rules text. `Card.tags` stores `0期生`; every locale's
# `Translation.tags` and every prose reference writes `#0期生`.
TAG_PREFIX = "#"


def combined_table(
    names: Glossary, tags: Glossary | None = None
) -> list[tuple[str, str]]:
    """Every maskable string across the glossaries, longest first.

    Returns `(surface, "kind:key")` pairs. The kind is folded into the value so `unmask`
    knows which glossary to restore from — two glossaries can legitimately hold the same
    key, and a bare key would be ambiguous.

    Sorted globally rather than per glossary, because a name and a tag can nest just as
    two names can.
    """
    pairs: list[tuple[str, str]] = [
        (surface, f"names:{key}") for surface, key in names.mask_table()
    ]

    if tags is not None:
        pairs.extend(
            (surface, f"tags:{key}")
            for surface, key in tags.prefixed_mask_table(TAG_PREFIX)
        )

    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def split_qualified(qualified: str) -> tuple[str, str]:
    """`"tags:0期生"` -> `("tags", "0期生")`.

    Splits on the first colon only: glossary keys contain colons in the wild (a set name
    like `【使用可能カード】…`), so `str.split(":")` would truncate them.
    """
    kind, _, key = qualified.partition(":")
    return kind, key


class Restorer:
    """Resolves a qualified key back to display text, from the right glossary."""

    def __init__(self, names: Glossary, tags: Glossary | None = None) -> None:
        self._by_kind = {"names": names}
        if tags is not None:
            self._by_kind["tags"] = tags

    def display(self, qualified: str, locale: str, surface: str | None = None) -> str:
        kind, key = split_qualified(qualified)
        glossary = self._by_kind.get(kind)
        if glossary is None:
            raise KeyError(f"no glossary for {kind!r}")

        entry = glossary.entries.get(key)
        if entry is None:
            raise KeyError(f"{key!r} is not in the {kind} glossary")

        if kind == "tags":
            # Tags are stored unprefixed but always render with their prefix, exactly as
            # `filter_options` normalises it — the `#` lives in one place, not in 41
            # glossary values where every future entry could forget it.
            text = entry.display(locale)
            return text if text.startswith(TAG_PREFIX) else f"{TAG_PREFIX}{text}"

        # Names pass the surface through so an alias restores to its own short form.
        return entry.display(locale, surface=surface)

    def has(self, qualified: str) -> bool:
        kind, key = split_qualified(qualified)
        glossary = self._by_kind.get(kind)
        return glossary is not None and key in glossary.entries
