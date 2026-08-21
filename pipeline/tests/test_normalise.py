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
    substitute_quotes,
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


class TestTheBracketRule:
    """#27 part 2 — and it is a rendering fix, not a cosmetic one.

    `ability_text` reaches the page through `v-html`, so a browser parses an ASCII
    `<Hakui Koyori>` as an unknown tag and **drops the name**. 54 character names were
    invisible on 24 live card pages: the rule read "attached to 1st or higher" and then
    stopped. `〈` and `〉` are not HTML metacharacters, so they survive the same path.
    """

    def test_an_ascii_reference_becomes_a_cjk_one(self):
        text, counts = normalise_text("attached to <Hakui Koyori>", "en")

        assert text == "attached to 〈Hakui Koyori〉"
        assert sum(counts.values()) == 1

    def test_it_applies_to_every_locale_not_just_th(self):
        """Unlike RULES, which is per-locale. The source writes 〈〉 6,804 times and ASCII
        zero times, so an ASCII reference is model output whatever the language."""
        for locale in ("en", "tc", "id", "ko", "th", "es"):
            text, _ = normalise_text("<Natsuiro Matsuri>", locale)
            assert text == "〈Natsuiro Matsuri〉", locale

    def test_a_correct_reference_is_left_alone(self):
        text, counts = normalise_text("attached to 〈Hakui Koyori〉", "en")

        assert text == "attached to 〈Hakui Koyori〉"
        assert counts == {}

    def test_several_references_in_one_string_all_convert(self):
        text, counts = normalise_text("<A> and <B> and <C>", "en")

        assert text == "〈A〉 and 〈B〉 and 〈C〉"
        assert sum(counts.values()) == 3

    def test_an_unclosed_bracket_is_left_alone(self):
        """The bound is what stops a stray `<` swallowing the rest of a sentence. No such
        string exists in the cache today — every `<` forms a closed pair in all six
        locales — so this guards against future data, not current."""
        original = "gets Arts +10 if HP < 100 and the holomem is ready"

        text, counts = normalise_text(original, "en")

        assert text == original
        assert counts == {}

    def test_a_reference_longer_than_the_bound_is_left_alone(self):
        original = "<" + "x" * 41 + ">"

        text, _ = normalise_text(original, "en")

        assert text == original

    def test_the_protected_name_survives_the_pattern(self):
        """The pattern runs inside the sentinel substitution, like every literal rule."""
        text, _ = normalise_text("ชิโรกาเนะ โนเอล ส่ง <A> เอール", "th")

        assert "โนเอล" in text
        assert "〈A〉" in text
        assert CORRECT in text

    def test_remaining_reports_an_unconverted_reference(self):
        """`remaining` must cover the global patterns too. A check that silently ignores
        a whole rule kind reports ✓ for a pass that did not finish."""
        left = remaining({"a": "attached to <Hakui Koyori>"}, "en")

        assert sum(left.values()) == 1

    def test_a_completed_bracket_pass_leaves_nothing(self):
        entries = {"a": "<A>", "b": "〈B〉", "c": "plain text"}

        changed, _ = normalise_locale(entries, "en")

        assert remaining({**entries, **changed}, "en") == {}

    def test_the_bracket_pass_is_idempotent(self):
        entries = {"a": "attached to <Hakui Koyori>"}

        changed, _ = normalise_locale(entries, "en")
        again, report = normalise_locale({**entries, **changed}, "en")

        assert again == {}
        assert report.total_replacements == 0


class TestQuoteSubstitution:
    """#27 part 1 — the answer is already in the cache, nothing was looking it up.

    A card's rules text quotes another card's skill or art name in `「…」`. The model
    sometimes leaves that quote in Japanese while translating everything around it, so
    the card says `「人生リセットボタン」` and the skill's own entry says
    `Tombol Reset Kehidupan`.
    """

    QUOTES = {
        "人生リセットボタン": "Tombol Reset Kehidupan",
        "神秘の儀式": "Ritual Misterius",
    }

    def test_a_quoted_name_is_replaced_with_its_canonical_translation(self):
        text, n = substitute_quotes(
            "If you used 「人生リセットボタン」 this game", self.QUOTES
        )

        assert text == "If you used 「Tombol Reset Kehidupan」 this game"
        assert n == 1

    def test_the_brackets_are_kept(self):
        """They are the source's own punctuation, not an artifact of the leak."""
        text, _ = substitute_quotes("「神秘の儀式」", self.QUOTES)

        assert text.startswith("「") and text.endswith("」")

    def test_a_quote_with_no_cache_answer_is_left_exactly_as_it_is(self):
        """Most quoted strings are flavour prose, not names — `あやふぶみの「あや」担当`.
        Leaving them is the normal, permanent case, not a failure."""
        original = "あやふぶみの「あや」担当"

        text, n = substitute_quotes(original, self.QUOTES)

        assert text == original
        assert n == 0

    def test_only_an_exact_match_substitutes(self):
        """A substring or fuzzy match would rewrite one card's quotation into another
        card's name — #78's failure arriving by a different route."""
        original = "「人生リセットボタンのようなもの」"

        text, n = substitute_quotes(original, self.QUOTES)

        assert text == original
        assert n == 0

    def test_a_translation_equal_to_the_source_is_not_counted(self):
        """A name that stays Japanese in this locale is a decision, not a gap.
        Substituting it is a no-op that would inflate the count."""
        text, n = substitute_quotes("「FUWAMOCO」", {"FUWAMOCO": "FUWAMOCO"})

        assert text == "「FUWAMOCO」"
        assert n == 0

    def test_several_quotes_in_one_string(self):
        text, n = substitute_quotes(
            "「人生リセットボタン」 and 「神秘の儀式」", self.QUOTES
        )

        assert "Tombol Reset Kehidupan" in text and "Ritual Misterius" in text
        assert n == 2

    def test_it_runs_through_normalise_locale(self):
        entries = {"a": "If you used 「人生リセットボタン」 this game"}

        changed, report = normalise_locale(entries, "id", quotes=self.QUOTES)

        assert "Tombol Reset Kehidupan" in changed["a"]
        assert report.total_replacements == 1

    def test_it_is_idempotent(self):
        entries = {"a": "「人生リセットボタン」"}

        changed, _ = normalise_locale(entries, "id", quotes=self.QUOTES)
        again, _ = normalise_locale({**entries, **changed}, "id", quotes=self.QUOTES)

        assert again == {}

    def test_no_quotes_map_means_no_substitution(self):
        """The map is optional — `normalise-cache` can run without a build."""
        entries = {"a": "「人生リセットボタン」"}

        changed, _ = normalise_locale(entries, "id")

        assert changed == {}


class TestTheManualEntryBlindSpot:
    """`manual` entries are not rewritten, so they must at least be *checked*.

    The pass excludes them deliberately — a human decided that string and a blanket rule
    does not overrule them (ADR 0002). But excluding them from the completeness check as
    well meant a bad variant inside a committed correction was invisible to both the pass
    and its guard, and `normalise-cache` still printed ✓.

    Harmless when it was written — `corrections/` held only `tc` while `RULES` held only
    `th` — but that was a property of the data, not of the code. These pin the reporting
    path so the next correction in a rule-carrying locale is loud.
    """

    def test_remaining_finds_a_variant_in_a_manual_entry(self):
        """What the CLI now runs over the excluded set, so a bad correction is named."""
        manual = {"art_name:x": "ส่งเอール 1 ใบ"}

        assert remaining(manual, "th") == {"เอール": 1}

    def test_a_clean_manual_entry_reports_nothing(self):
        manual = {"art_name:x": f"ส่ง{CORRECT} 1 ใบ"}

        assert remaining(manual, "th") == {}

    def test_the_committed_corrections_are_clean(self):
        """The real files, against the real rules. This is the check that would have
        fired had a correction been written in a locale with rules."""
        from holo_data import corrections as C

        for locale, corrections in C.load_all().items():
            entries = {c.key: c.value for c in corrections.items}
            assert remaining(entries, locale) == {}, locale
