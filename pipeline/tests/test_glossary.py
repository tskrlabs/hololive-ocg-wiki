"""Tests for the proper-noun glossary.

Two things are pinned here, both of which fail silently if wrong.

**Ambiguity must be rejected.** An alias claimed by two characters would restore as
whichever entry happened to be masked first — a per-run wrong answer with no error. Three
such collisions exist in the real data (`マリン`, `ルーナ`, `シオン`, each shared between a
character and their `魔法少女` variant), so this is not hypothetical.

**The boundary rule must not eat ordinary words.** `トワ` is Tokoyami Towa and also the
first two syllables of `トワイライト` ("twilight"). Japanese has no spaces, so substring
matching alone would mask the second. The cases below are taken from the real corpus.
"""

from __future__ import annotations

import json

import pytest

from holo_data.glossary import (
    Alias,
    Entry,
    Glossary,
    GlossaryError,
    absorbed_in,
    i18n_maps,
)


class TestEntry:
    def test_display_falls_back_to_the_source_string(self):
        entry = Entry(key="白上フブキ", translations={"en": "Shirakami Fubuki"})

        assert entry.display("en") == "Shirakami Fubuki"
        assert entry.display("th") == "白上フブキ"

    def test_an_undecided_locale_is_distinguishable_from_a_deliberate_passthrough(self):
        """`FUWAMOCO` staying as-is is a decision; a missing `th` is a gap."""
        decided = Entry(key="FUWAMOCO", translations={"en": "FUWAMOCO"})

        assert decided.has("en")
        assert not decided.has("th")
        # Both display identically — the difference is only visible in coverage.
        assert decided.display("en") == decided.display("th")

    def test_maskable_puts_the_longest_first(self):
        """`ルーナ` inside `ルーナイト`: masking the short form first eats the long one.

        Only length order is asserted. Equal-length entries have no meaningful
        precedence — they cannot contain each other — so pinning their relative order
        would pin an implementation detail of `sorted`.
        """
        entry = Entry(key="姫森ルーナ", aliases=["ルーナイト", "ルーナ"])
        maskable = entry.maskable()

        assert set(maskable) == {"姫森ルーナ", "ルーナイト", "ルーナ"}
        assert maskable[-1] == "ルーナ", "the containable short form must be masked last"
        assert [len(t) for t in maskable] == sorted(
            (len(t) for t in maskable), reverse=True
        )


class TestValidation:
    def test_an_alias_claimed_by_two_entries_is_rejected(self):
        """The real collision: 宝鐘マリン and 魔法少女マリン both shorten to マリン."""
        glossary = Glossary(
            kind="names",
            entries={
                "宝鐘マリン": Entry(key="宝鐘マリン", aliases=["マリン"]),
                "魔法少女マリン": Entry(key="魔法少女マリン", aliases=["マリン"]),
            },
        )

        with pytest.raises(GlossaryError, match="claimed by both"):
            glossary.validate()

    def test_an_alias_colliding_with_another_entrys_key_is_rejected(self):
        glossary = Glossary(
            kind="names",
            entries={
                "ルーナイト": Entry(key="ルーナイト"),
                "姫森ルーナ": Entry(key="姫森ルーナ", aliases=["ルーナイト"]),
            },
        )

        with pytest.raises(GlossaryError, match="claimed by both"):
            glossary.validate()

    def test_an_empty_alias_is_rejected(self):
        """An empty mask target would match at every position."""
        glossary = Glossary(
            kind="names", entries={"X": Entry(key="X", aliases=["  "])}
        )

        with pytest.raises(GlossaryError, match="empty key or alias"):
            glossary.validate()

    def test_the_same_alias_on_one_entry_twice_is_fine(self):
        glossary = Glossary(
            kind="names", entries={"白上フブキ": Entry(key="白上フブキ", aliases=["フブキ"])}
        )

        glossary.validate()  # does not raise

    def test_saving_validates(self, tmp_path):
        """A bad table must not reach disk, where a later run would trust it."""
        glossary = Glossary(
            kind="names",
            entries={
                "A": Entry(key="A", aliases=["shared"]),
                "B": Entry(key="B", aliases=["shared"]),
            },
        )

        with pytest.raises(GlossaryError):
            glossary.save(tmp_path)


class TestBoundaryRule:
    """`absorbed_in` decides whether a katakana match is a name or part of a word."""

    @pytest.mark.parametrize(
        "alias,label",
        [
            ("トワ", "トワイライトリゾート"),   # twilight
            ("ムリン", "悪戯好きのグレムリン"),  # gremlin
            ("ローズ", "パレ・モンローズのお話"),  # Monrose
            ("フブキ", "フブキングダム"),        # Fubuki + kingdom
            ("アキ", "アキロゼ幻想曲"),          # Aki Rosenthal, contracted
        ],
    )
    def test_a_longer_katakana_word_is_left_alone(self, alias, label):
        assert absorbed_in(alias, label)

    @pytest.mark.parametrize(
        "alias,label",
        [
            ("トワ", "トワにしか出せない色"),      # name + particle
            ("トワ", "トワとお家デートしたっていい"),
            ("フブキ", "フブキは特別な存在"),
            ("スバル", "おはようスバル"),          # name at end of string
            ("リス", "こんリス"),
        ],
    )
    def test_a_name_followed_by_a_particle_is_a_name(self, alias, label):
        assert not absorbed_in(alias, label)

    def test_kanji_names_are_not_subject_to_the_rule(self):
        """Kanji compounds do not extend a proper noun the way a katakana run does."""
        assert not absorbed_in("白上", "白上から目をそらしちゃ")
        assert not absorbed_in("大空", "大空スマイル")

    def test_every_occurrence_must_be_absorbed_for_the_answer_to_be_yes(self):
        """One standalone use is enough to make the alias worth masking."""
        assert absorbed_in("トワ", "トワイライト")
        assert not absorbed_in("トワ", "トワイライトとトワの話")

    def test_absent_text_is_not_absorbed(self):
        assert not absorbed_in("トワ", "まったく別の話")
        assert not absorbed_in("", "anything")


class TestMaskTable:
    def test_orders_globally_not_per_entry(self):
        """Names from *different* entries nest too, so one entry at a time is wrong."""
        glossary = Glossary(
            kind="names",
            entries={
                "ルーナイト": Entry(key="ルーナイト"),
                "姫森ルーナ": Entry(key="姫森ルーナ"),
            },
        )

        table = glossary.mask_table()
        lengths = [len(text) for text, _ in table]

        assert lengths == sorted(lengths, reverse=True)

    def test_every_alias_maps_back_to_its_entry(self):
        glossary = Glossary(
            kind="names",
            entries={"白上フブキ": Entry(key="白上フブキ", aliases=["フブキ", "白上"])},
        )

        assert dict(glossary.mask_table()) == {
            "白上フブキ": "白上フブキ",
            "フブキ": "白上フブキ",
            "白上": "白上フブキ",
        }


class TestPersistence:
    def test_round_trips(self, tmp_path):
        original = Glossary(
            kind="names",
            entries={
                "白上フブキ": Entry(
                    key="白上フブキ",
                    translations={"en": "Shirakami Fubuki", "tc": "白上狐狸"},
                    aliases=["フブキ"],
                    note="fanbase is フブキング",
                )
            },
        )
        original.save(tmp_path)

        loaded = Glossary.load("names", tmp_path)
        entry = loaded.entries["白上フブキ"]

        assert entry.translations == {"en": "Shirakami Fubuki", "tc": "白上狐狸"}
        assert entry.alias_texts() == ["フブキ"]
        assert entry.note == "fanbase is フブキング"

    def test_an_alias_keeps_its_own_translations_across_a_round_trip(self, tmp_path):
        """Register-preserving short forms: `モココ` -> "Mococo", not the full name."""
        Glossary(
            kind="names",
            entries={
                "モココ・アビスガード": Entry(
                    key="モココ・アビスガード",
                    translations={"en": "Mococo Abyssgard"},
                    aliases=[Alias(text="モココ", translations={"en": "Mococo"})],
                )
            },
        ).save(tmp_path)

        entry = Glossary.load("names", tmp_path).entries["モココ・アビスガード"]

        assert entry.display("en") == "Mococo Abyssgard"
        assert entry.display("en", surface="モココ") == "Mococo"

    def test_a_bare_string_alias_stays_bare_on_disk(self, tmp_path):
        """An alias with nothing to say should not become an object in the diff."""
        Glossary(
            kind="names", entries={"白上フブキ": Entry(key="白上フブキ", aliases=["フブキ"])}
        ).save(tmp_path)

        raw = json.loads((tmp_path / "names.json").read_text(encoding="utf-8"))

        assert raw["entries"]["白上フブキ"]["aliases"] == ["フブキ"]

    def test_a_missing_file_is_an_empty_glossary_not_an_error(self, tmp_path):
        """A fresh clone before seeding should not crash the build."""
        assert Glossary.load("names", tmp_path).entries == {}

    def test_written_sorted_for_review(self, tmp_path):
        """This file is read as a PR diff (#18); key order must be stable."""
        glossary = Glossary(
            kind="tags",
            entries={k: Entry(key=k) for k in ["歌", "EN", "0期生"]},
        )
        path = glossary.save(tmp_path)

        keys = list(json.loads(path.read_text(encoding="utf-8"))["entries"])
        assert keys == sorted(keys)

    def test_an_unknown_kind_is_refused(self, tmp_path):
        with pytest.raises(GlossaryError, match="unknown glossary kind"):
            Glossary.load("nicknames", tmp_path)


class TestCoverage:
    def test_reports_decided_against_total(self):
        glossary = Glossary(
            kind="names",
            entries={
                "A": Entry(key="A", translations={"en": "Ay"}),
                "B": Entry(key="B"),
            },
        )

        assert glossary.coverage("en") == (1, 2)
        assert glossary.coverage("th") == (0, 2)
        assert glossary.missing("en") == ["B"]


class TestI18nMaps:
    def test_emits_every_key_including_undecided_ones(self):
        """A complete map means a frontend miss is a genuinely absent key."""
        glossaries = {
            "names": Glossary(
                kind="names",
                entries={
                    "白上フブキ": Entry(key="白上フブキ", translations={"en": "Shirakami Fubuki"}),
                    "AZKi": Entry(key="AZKi"),
                },
            ),
            "sets": Glossary(kind="sets"),
            "tags": Glossary(kind="tags"),
        }

        maps = i18n_maps(glossaries, "en")

        assert maps["names"] == {"白上フブキ": "Shirakami Fubuki", "AZKi": "AZKi"}
