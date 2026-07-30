"""Tests for name masking.

Masking rewrites text on its way to the model and puts names back afterwards, so a bug
here **corrupts** translations rather than failing them — the output is plausible, cached,
published, and found by a reader months later. Every case below is either a rule the real
data forces or a failure mode that would be silent.

The cases use real strings from the 2,463-card corpus wherever one exists.
"""

from __future__ import annotations

import pytest

from holo_data.glossary import Entry, Glossary
from holo_data.translate.masking import (
    MaskError,
    MaskReport,
    mask,
    token_for,
    unmask,
    verify_roundtrip,
)


@pytest.fixture
def glossary():
    """A small glossary carrying every structural trap the real one has."""
    return Glossary(
        kind="names",
        entries={
            "白上フブキ": Entry(
                key="白上フブキ",
                translations={"en": "Shirakami Fubuki", "tc": "白上狐狸"},
                aliases=["フブキ", "白上"],
            ),
            "常闇トワ": Entry(
                key="常闇トワ", translations={"en": "Tokoyami Towa"}, aliases=["トワ"]
            ),
            "森カリオペ": Entry(key="森カリオペ", translations={"en": "Mori Calliope"}),
            # Nests inside the entry above — 75 such pairs exist in the real table.
            "森カリオペの鎌": Entry(
                key="森カリオペの鎌", translations={"en": "Mori Calliope's Scythe"}
            ),
            # ASCII, like `35P` and `Otomo` — the case that can collide with a token.
            "35P": Entry(key="35P", translations={"en": "35P"}),
            # No `en` decision: display falls back to the source string.
            "AZKi": Entry(key="AZKi"),
        },
    )


@pytest.fixture
def table(glossary):
    return glossary.mask_table()


class TestMasking:
    def test_replaces_a_name_with_a_token(self, table):
        result = mask("白上フブキのこんこん", table)

        assert result.text == "[[N0]]のこんこん"
        assert result.tokens == {"[[N0]]": "白上フブキ"}

    def test_text_with_no_name_is_untouched(self, table):
        result = mask("エールを1枚送る", table)

        assert result.text == "エールを1枚送る"
        assert not result.is_masked

    def test_an_alias_resolves_to_its_entry(self, table):
        """`トワ` is masked, but the token means `常闇トワ` — so it restores canonically."""
        result = mask("トワにしか出せない色", table)

        assert result.text == "[[N0]]にしか出せない色"
        assert result.tokens == {"[[N0]]": "常闇トワ"}
        assert result.surfaces == {"[[N0]]": "トワ"}

    def test_the_longest_match_wins(self, table):
        """`森カリオペ` nests inside `森カリオペの鎌`; the short one must not win."""
        result = mask("森カリオペの鎌", table)

        assert result.text == "[[N0]]"
        assert result.tokens == {"[[N0]]": "森カリオペの鎌"}

    def test_a_repeated_name_reuses_one_token(self, table):
        result = mask("35Pと35Pの話", table)

        assert result.text == "[[N0]]と[[N0]]の話"
        assert len(result.tokens) == 1

    def test_a_name_and_its_alias_get_separate_tokens(self, table):
        """Both restore to the same translation, but the *source* differs.

        One token would restore `フブキ` as `白上フブキ` and make `verify_roundtrip` fail
        for a reason that has nothing to do with masking being wrong.
        """
        result = mask("白上フブキとフブキ", table)

        assert result.text == "[[N0]]と[[N1]]"
        assert result.tokens == {"[[N0]]": "白上フブキ", "[[N1]]": "白上フブキ"}
        assert result.surfaces == {"[[N0]]": "白上フブキ", "[[N1]]": "フブキ"}

    def test_an_ascii_name_cannot_match_inside_a_token(self, table):
        """`35P` is ASCII and so is `[[N0]]`; a second pass could match within one.

        Masking walks the string once and never re-examines what it emitted, so this is
        structural rather than something the table has to be ordered to avoid.
        """
        result = mask("35P", table)

        assert result.text == "[[N0]]"
        assert "[[N" not in result.text[6:]

    def test_a_name_inside_angle_brackets_is_masked(self, table):
        """1,228 `〈…〉` card references live in rules text (F-015 territory)."""
        result = mask("自分の〈白上フブキ〉1人を選ぶ", table)

        assert result.text == "自分の〈[[N0]]〉1人を選ぶ"

    def test_empty_text_is_returned_unchanged(self, table):
        assert mask("", table).text == ""


class TestBoundaries:
    """The katakana word-boundary rule, applied per occurrence."""

    def test_a_name_absorbed_into_a_longer_word_is_left_alone(self, table):
        """`トワイライト` is "twilight", not Tokoyami Towa."""
        result = mask("トワイライトリゾート", table)

        assert result.text == "トワイライトリゾート"
        assert not result.is_masked

    def test_the_same_string_can_mask_one_occurrence_and_skip_another(self, table):
        """Per-occurrence, not per-string — the reason `absorbed_in` takes an index."""
        result = mask("トワとトワイライト", table)

        assert result.text == "[[N0]]とトワイライト"


class TestRoundTrip:
    def test_masking_is_reversible(self, table):
        for text in (
            "白上フブキのこんこん",
            "トワにしか出せない色",
            "白上フブキとフブキ",
            "森カリオペの鎌",
            "35Pと35Pの話",
            "トワとトワイライト",
            "名前のない文字列",
        ):
            verify_roundtrip(text, table)  # raises on failure

    def test_a_lossy_mask_is_caught_and_names_both_strings(self, monkeypatch, table):
        """`verify_roundtrip` is the guard, so it has to be able to fail.

        Asserting a guard by hand-raising the error it is supposed to raise proves
        nothing, so the masker itself is made lossy: `restore_source` returns something
        other than the input, exactly as a real bug in the token bookkeeping would.
        """
        from holo_data.translate import masking as module

        def lossy(self):
            return self.text  # never substitutes the surfaces back

        monkeypatch.setattr(module.Masked, "restore_source", lossy)

        with pytest.raises(MaskError, match="not reversible") as caught:
            verify_roundtrip("白上フブキのこんこん", table)

        message = str(caught.value)
        assert "白上フブキのこんこん" in message, "the original must be reported"
        assert "[[N0]]" in message, "the masked form must be reported"


class TestUnmasking:
    def test_substitutes_the_locale_translation(self, glossary, table):
        masked = mask("白上フブキのこんこん", table)

        assert unmask("[[N0]]'s Konkon", masked, glossary, "en") == (
            "Shirakami Fubuki's Konkon"
        )
        assert unmask("[[N0]]的Konkon", masked, glossary, "tc") == "白上狐狸的Konkon"

    def test_an_alias_restores_to_the_canonical_name(self, glossary, table):
        """The whole point: `トワ` in, "Tokoyami Towa" out — the same on every card."""
        masked = mask("トワにしか出せない色", table)

        assert unmask("A colour only [[N0]] can produce", masked, glossary, "en") == (
            "A colour only Tokoyami Towa can produce"
        )

    def test_an_undecided_locale_falls_back_to_the_source_name(self, glossary, table):
        masked = mask("AZKi", table)

        assert unmask("[[N0]]", masked, glossary, "en") == "AZKi"

    def test_a_dropped_token_raises_rather_than_returning_partial_text(
        self, glossary, table
    ):
        """The critical failure. A silently half-restored string enters the cache."""
        masked = mask("白上フブキのこんこん", table)

        with pytest.raises(MaskError, match="dropped"):
            unmask("Fubuki's Konkon", masked, glossary, "en")

    def test_an_invented_token_raises(self, glossary, table):
        masked = mask("白上フブキのこんこん", table)

        with pytest.raises(MaskError, match="invented"):
            unmask("[[N0]] and [[N9]]", masked, glossary, "en")

    def test_a_key_missing_from_the_glossary_raises(self, glossary, table):
        masked = mask("白上フブキのこんこん", table)
        del glossary.entries["白上フブキ"]

        with pytest.raises(MaskError, match="not in the glossary"):
            unmask("[[N0]]'s Konkon", masked, glossary, "en")

    def test_unmasked_text_passes_through(self, glossary, table):
        masked = mask("エールを1枚送る", table)

        assert unmask("Send 1 cheer", masked, glossary, "en") == "Send 1 cheer"

    def test_every_occurrence_of_a_token_is_replaced(self, glossary, table):
        masked = mask("35Pと35Pの話", table)

        assert unmask("[[N0]] and [[N0]]", masked, glossary, "en") == "35P and 35P"


class TestTokenFormat:
    def test_tokens_are_double_bracketed(self):
        """Single brackets occur in real game text — `[ターンに1回]`."""
        assert token_for(0) == "[[N0]]"
        assert token_for(12) == "[[N12]]"

    def test_a_token_survives_alongside_real_bracketed_game_text(self, table):
        result = mask("[ターンに1回]白上フブキを選ぶ", table)

        assert result.text == "[ターンに1回][[N0]]を選ぶ"


class TestAgainstTheRealGlossary:
    """The real 337-entry table over the real corpus — the rehearsal, in `make check`.

    The hand-built fixture above covers the structural rules. This covers the thing no
    fixture can: that the *actual* glossary, with its 41 aliases and 75 nested pairs,
    does not lose information on the *actual* card text.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def real_table(cls):
        real = Glossary.load("names")
        if not real.entries:
            pytest.skip("pipeline/glossary/names.json is not seeded")
        return real.mask_table()

    @pytest.fixture(scope="class")
    @classmethod
    def corpus(cls):
        from holo_data import build as build_module

        collection = build_module.load()
        if collection is None:
            pytest.skip("no build output — run `holo-data build`")
        return collection

    def test_every_source_string_round_trips(self, real_table, corpus):
        from holo_data.cli import _translatable_strings

        report = MaskReport()
        for card in corpus.cards:
            for text in _translatable_strings(card.translations["ja"]):
                report.record(text, real_table)

        assert not report.failures, (
            f"{len(report.failures)} string(s) do not survive masking: "
            f"{report.failures[:3]}"
        )
        assert report.masked > 0, "the real glossary matched nothing — table is wrong"

    def test_the_table_is_ordered_longest_first(self, real_table):
        """75 real pairs nest, so a mis-ordered table silently strands fragments."""
        lengths = [len(text) for text, _ in real_table]

        assert lengths == sorted(lengths, reverse=True)

    def test_no_entry_is_masked_out_from_under_a_longer_one(self, real_table):
        """For every nested pair, the longer text must come first."""
        order = {text: index for index, (text, _) in enumerate(real_table)}

        for shorter, _ in real_table:
            for longer, _ in real_table:
                if shorter != longer and shorter in longer:
                    assert order[longer] < order[shorter], (
                        f"{shorter!r} is ordered before {longer!r} that contains it"
                    )


class TestReport:
    def test_counts_masked_strings_and_names(self, table):
        report = MaskReport()
        for text in ("白上フブキのこんこん", "エールを1枚送る", "トワにしか出せない色"):
            report.record(text, table)

        assert report.total == 3
        assert report.masked == 2
        assert report.occurrences == {"白上フブキ": 1, "常闇トワ": 1}

    def test_a_non_round_tripping_string_is_recorded(self, table):
        report = MaskReport()
        report.record("白上フブキのこんこん", table)

        assert not report.failures
        assert "✓ every string round-trips exactly" in "\n".join(report.lines())
