"""Tests for the deterministic spelling pass (#28).

What this has to get right is narrow and sharp: it rewrites 360 strings in a cache that
costs real money to rebuild, using blind substring replacement. Two things can go wrong,
and both are silent.

**It can eat a name.** `โนเอล` is Shirogane Noel, and a bare `เอล` -> `เยล` turns her into
`โนเยล` in nine places. Nothing downstream would notice; a Thai reader would.

**It can invent a fifth variant.** The four spellings nest — `เอล` is a prefix of `เอลล์`
and a substring of `เอール` — so applying the short rule first leaves `ล์` or `ール`
stranded and produces a new wrong string rather than fixing the old ones.

So the tests are mostly about those, not about the happy path.
"""

from __future__ import annotations

import pytest

from holo_data.translate.normalise import (
    PROTECTED,
    RULES,
    normalise_locale,
    normalise_text,
    remaining,
)

# The glossary's answer, from all six cheer cards: `黄エール` -> `เยลสีเหลือง`.
CORRECT = "เยล"


class TestTheRules:
    @pytest.mark.parametrize(
        "wrong",
        [
            "เอール",  # Thai เอ + katakana ール — not a word in any language
            "เอลล์",  # a final ล์ on the same word
            "เอล",  # the bare third variant
        ],
    )
    def test_every_variant_becomes_the_glossary_spelling(self, wrong: str):
        text, counts = normalise_text(f"ส่ง{wrong} 1 ใบ", "th")

        assert text == f"ส่ง{CORRECT} 1 ใบ"
        assert sum(counts.values()) == 1

    def test_the_correct_spelling_is_left_alone(self):
        text, counts = normalise_text(f"ส่ง{CORRECT} 1 ใบ", "th")

        assert text == f"ส่ง{CORRECT} 1 ใบ"
        assert counts == {}

    def test_a_locale_with_no_rules_is_untouched(self):
        """Only `th` has rules. Every other locale must pass through byte-identical."""
        original = "Archive 1 Cheer from your Holomem"

        text, counts = normalise_text(original, "en")

        assert text == original
        assert counts == {}

    def test_no_rule_precedes_one_it_is_a_prefix_of(self):
        """The ordering property the module depends on, stated precisely.

        Written first as "longest first" — copying `mask_table` — and it failed: `เอลล์`
        is 5 codepoints and `เอール` is 4, so length ordering ranks them and means
        nothing, because they do not overlap. The real constraint is prefix containment,
        and there is one pair with it: `เอล` ⊂ `เอลล์`. Running the short one first
        leaves `ล์` stranded and yields `เยลล์` — a fifth spelling.

        Every other test here would still pass under a bad order, because each rule in
        isolation is correct. This is the only one that catches it.
        """
        for locale, rules in RULES.items():
            wrongs = [wrong for wrong, _ in rules]
            for index, short in enumerate(wrongs):
                for long in wrongs[index + 1 :]:
                    assert not long.startswith(short), (
                        f"{locale}: {short!r} runs before {long!r}, which it is a "
                        f"prefix of — {long!r} would never match."
                    )


class TestTheProtectedName:
    """`โนเอล` — Shirogane Noel — contains `เอล` and must survive untouched."""

    def test_a_protected_name_is_not_rewritten(self):
        text, _ = normalise_text("ชิโรกาเนะ โนเอล ใช้ความสามารถ", "th")

        assert "โนเอล" in text
        assert "โนเยล" not in text

    def test_the_name_survives_beside_a_real_occurrence(self):
        """The case a naive implementation gets wrong: both in one string."""
        text, _ = normalise_text("ชิโรกาเนะ โนเอล ส่งเอール 1 ใบ", "th")

        assert text == f"ชิโรกาเนะ โนเอล ส่ง{CORRECT} 1 ใบ"

    def test_a_rule_cannot_match_across_a_protected_boundary(self, monkeypatch):
        """Protection is by substitution, and that turns out to be the stronger half.

        Tried to trip the count guard with a rule spanning the phrase's edge (`"ะ โ"`,
        the join between `ชิโรกาเนะ` and `โนเอล`). It does not fire, and the reason is
        the point: the phrase is replaced by a sentinel *before* any rule runs, so the
        boundary a spanning rule would need no longer exists. A protected phrase is not
        merely restored afterwards — it is invisible while the rules execute.

        So the count check in `normalise_locale` is a backstop, not the mechanism. What
        actually protects the name is being in `PROTECTED` at all.
        """
        monkeypatch.setitem(RULES, "th", (("ะ โ", "ะX"),))
        monkeypatch.setitem(PROTECTED, "th", ("โนเอล",))

        text, counts = normalise_text("ชิโรกาเนะ โนเอล", "th")

        assert text == "ชิโรกาเนะ โนเอล"
        assert counts == {}

    def test_removing_a_protection_is_what_the_guard_cannot_see(self, monkeypatch):
        """⚠️ The guard's blind spot, pinned so it is known rather than assumed.

        It compares counts of the phrases in `PROTECTED`. Delete an entry and there is
        nothing left to count, so the corruption it existed to prevent happens silently —
        which is exactly what `PROTECTED` removal looks like in a diff.

        So `PROTECTED` is the load-bearing list, not the guard. This test is the thing
        that fails if `โนเอล` is ever dropped from it.
        """
        monkeypatch.setitem(PROTECTED, "th", ())

        changed, _ = normalise_locale({"card_name:x": "ชิโรกาเนะ โนเอล"}, "th")

        # No exception — the guard is silent, and Shirogane Noel is corrupted.
        assert changed["card_name:x"] == "ชิโรกาเนะ โนเยล"

    def test_shirogane_noel_is_protected(self):
        """The specific entry the above depends on. 9 occurrences in the shipped cache."""
        assert "โนเอล" in PROTECTED["th"]


class TestAcrossTheCache:
    def test_only_changed_entries_come_back(self):
        """The caller writes these back individually, leaving every other entry's
        `source` and `source_hash` untouched."""
        entries = {
            "a": "ส่งเอール 1 ใบ",
            "b": f"ส่ง{CORRECT} 1 ใบ",
            "c": "ไม่มีคำนี้",
        }

        changed, report = normalise_locale(entries, "th")

        assert set(changed) == {"a"}
        assert report.entries_changed == 1

    def test_qa_dicts_are_rewritten_field_by_field(self):
        """Q&A values are dicts. `title` and `related_cards` must not be touched —
        `related_cards.raw_html` is source markup the site parses."""
        qa = {
            "title": "Q527（2026.06.26）",
            "question": "ส่งเอール ได้ไหม?",
            "answer": "ได้ ส่งเอลล์ ได้",
            "related_cards": {"card_number": ["hSD01-001"], "raw_html": "[x ： เอล]"},
        }

        changed, _ = normalise_locale({"qa:1": qa}, "th")
        out = changed["qa:1"]

        assert out["question"] == f"ส่ง{CORRECT} ได้ไหม?"
        assert out["answer"] == f"ได้ ส่ง{CORRECT} ได้"
        assert out["title"] == qa["title"]
        assert out["related_cards"] == qa["related_cards"]

    def test_nothing_survives_a_completed_pass(self):
        """`remaining` is the check that the pass finished rather than merely ran."""
        entries = {
            "a": "เอール",
            "b": "เอลล์",
            "c": "เอล",
            "d": "ชิโรกาเนะ โนเอล",
        }

        changed, _ = normalise_locale(entries, "th")

        assert remaining({**entries, **changed}, "th") == {}

    def test_the_pass_is_idempotent(self):
        """Re-running must be a no-op — it is re-runnable by design, and a rule that
        matched its own output would loop the corpus into a different string each time."""
        entries = {"a": "ส่งเอール 1 ใบ", "b": "โนเอล"}

        changed, _ = normalise_locale(entries, "th")
        again, report = normalise_locale({**entries, **changed}, "th")

        assert again == {}
        assert report.total_replacements == 0
