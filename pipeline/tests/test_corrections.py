"""Tests for the committed corrections surface — #18.

Three properties carry it:

**A correction is addressed by what it translates, not by a hash.** A contributor writes
the Japanese; the key is derived. Nobody computes sha256 to send a PR.

**A correction wins, and keeps winning.** It is folded in after the machine entries and is
never stale, so no translation run can overwrite it. ADR 0002's durability guarantee,
applied to an entry that now lives somewhere reviewable.

**A correction lives in exactly one place.** `save` holds it back out of the cache blob, so
deleting the committed lines actually removes it rather than leaving an invisible copy.
"""

from __future__ import annotations

import json

import pytest

from holo_data import corrections as C
from holo_data.translate import units as U
from holo_data.translate.cache_v2 import TranslationCacheV2


def unit(kind="art_name", value="おつルーナ"):
    return U.Unit(kind=kind, value=value, occurrences=1)


def write(tmp_path, locale, items, declared=None):
    payload = {"locale": declared or locale, "corrections": items}
    path = tmp_path / f"{locale}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class TestAddressing:
    def test_the_key_is_derived_from_kind_and_source(self):
        """A contributor writes Japanese, not a hash — or this is as unusable as the
        gitignored cache it replaces."""
        correction = C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")

        assert correction.key == U.unit_key("art_name", "おつルーナ")

    def test_it_matches_the_unit_the_build_collects(self):
        correction = C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")

        assert correction.key == unit().key

    def test_a_different_source_is_a_different_key(self):
        """Byte-identical or it does not match: `～` and `~` are different strings."""
        a = C.Correction(kind="art_name", source="おつルーナ", value="x")
        b = C.Correction(kind="art_name", source="おつルーナ～", value="x")

        assert a.key != b.key

    def test_the_kind_is_part_of_the_key(self):
        a = C.Correction(kind="art_name", source="同じ", value="x")
        b = C.Correction(kind="card_name", source="同じ", value="x")

        assert a.key != b.key


class TestApplying:
    def test_a_correction_becomes_a_manual_cache_entry(self):
        cache = TranslationCacheV2()
        corrections = C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")],
        )

        assert corrections.apply_to(cache) == 1
        assert cache.value_for("tc", unit()) == "辛苦啦露娜～"
        assert cache.count("tc", source="manual") == 1

    def test_it_overrides_what_the_model_produced(self):
        """Applied after the machine entries — the entire point of writing one."""
        cache = TranslationCacheV2()
        cache.put("tc", unit(), "OtsuLuna")
        C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")],
        ).apply_to(cache)

        assert cache.value_for("tc", unit()) == "辛苦啦露娜～"

    def test_a_corrected_unit_is_never_stale(self):
        """So `translate` plans no work for it and no model reply can overwrite it."""
        cache = TranslationCacheV2()
        C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")],
        ).apply_to(cache)

        assert cache.stale("tc", [unit()]) == []

    def test_locales_are_independent(self):
        cache = TranslationCacheV2()
        C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")],
        ).apply_to(cache)

        assert cache.value_for("en", unit()) is None


class TestOneHome:
    """A correction lives in the committed file, and nowhere else."""

    def test_save_holds_corrections_out_of_the_cache_blob(self, tmp_path):
        cache = TranslationCacheV2()
        cache.put("tc", unit(value="機械"), "Machine")
        C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")],
        ).apply_to(cache)

        path = tmp_path / "v2.json"
        cache.save(path)

        written = json.loads(path.read_text(encoding="utf-8"))["locales"]["tc"]
        assert unit(value="機械").key in written
        assert unit().key not in written

    def test_deleting_a_correction_removes_it(self, tmp_path):
        """The property the whole design turns on. A copy left in the blob would survive
        its own deletion from the file a reviewer reads."""
        cache_path = tmp_path / "v2.json"
        write(tmp_path, "tc", [
            {"kind": "art_name", "source": "おつルーナ", "value": "辛苦啦露娜～"}
        ])

        cache = TranslationCacheV2.load(cache_path, corrections_dir=tmp_path)
        assert cache.value_for("tc", unit()) == "辛苦啦露娜～"
        cache.save(cache_path)

        write(tmp_path, "tc", [])  # the contributor's fix is reverted
        reloaded = TranslationCacheV2.load(cache_path, corrections_dir=tmp_path)

        assert reloaded.value_for("tc", unit()) is None

    def test_reading_a_named_file_describes_that_file(self, tmp_path):
        """`backup.stats_for` verifies a snapshot by loading it and counting `manual`
        entries. Folding the repo's corrections into that read would report a count
        including entries the snapshot does not contain — breaking the one check that
        proves a backup is restorable."""
        path = tmp_path / "snapshot.json"
        TranslationCacheV2().save(path)

        assert TranslationCacheV2.load(path).entries == {}

    def test_a_pre_existing_manual_entry_is_not_dropped(self, tmp_path):
        """Entries written before this mechanism existed have no committed home yet.
        Silently discarding them on the next save would delete hand-written work."""
        cache = TranslationCacheV2()
        cache.put("tc", unit(), "辛苦啦露娜～", source="manual")

        path = tmp_path / "v2.json"
        cache.save(path)

        written = json.loads(path.read_text(encoding="utf-8"))["locales"]["tc"]
        assert unit().key in written

    def test_those_entries_are_reported_as_orphans(self):
        cache = TranslationCacheV2()
        cache.put("tc", unit(), "辛苦啦露娜～", source="manual")
        cache.put("tc", unit(value="機械"), "Machine")

        assert cache.orphan_manual("tc") == [unit().key]

    def test_orphans_are_found_when_there_are_no_corrections_at_all(self, tmp_path):
        """The pre-migration state, and the one `--extract` exists for. An early return
        on "no corrections recorded" made exactly this case silent — every `manual` entry
        is an orphan precisely when no committed file exists yet."""
        cache = TranslationCacheV2()
        cache.put("tc", unit(), "辛苦啦露娜～", source="manual")
        assert cache.apply_corrections(directory=tmp_path) == 0

        assert cache.orphan_manual("tc") == [unit().key]

    def test_a_committed_correction_is_not_an_orphan(self):
        cache = TranslationCacheV2()
        C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")],
        ).apply_to(cache)

        assert cache.orphan_manual("tc") == []


class TestUnknownSources:
    """The check that replaces a stored hash."""

    def test_a_correction_no_card_prints_is_reported(self):
        corrections = C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="打ち間違い", value="typo")],
        )

        unknown = corrections.unknown([unit()])

        assert [c.source for c in unknown] == ["打ち間違い"]

    def test_a_matching_correction_is_not(self):
        corrections = C.Corrections(
            locale="tc",
            items=[C.Correction(kind="art_name", source="おつルーナ", value="辛苦啦露娜～")],
        )

        assert corrections.unknown([unit()]) == []

    def test_the_right_source_under_the_wrong_kind_is_reported(self):
        """#78's shape: a value keyed to something the build never asks for is silent
        by construction. This is what makes it loud."""
        corrections = C.Corrections(
            locale="tc",
            items=[C.Correction(kind="card_name", source="おつルーナ", value="x")],
        )

        assert len(corrections.unknown([unit()])) == 1


class TestValidation:
    def test_an_unknown_kind_is_refused(self):
        with pytest.raises(C.CorrectionError, match="unknown kind"):
            C.Correction(kind="not_a_field", source="x", value="y").validate()

    def test_an_empty_source_is_refused(self):
        with pytest.raises(C.CorrectionError, match="`source` is empty"):
            C.Correction(kind="art_name", source="  ", value="y").validate()

    def test_an_empty_value_is_refused(self):
        with pytest.raises(C.CorrectionError, match="`value` is empty"):
            C.Correction(kind="art_name", source="x", value="").validate()

    def test_a_missing_field_names_what_is_missing(self):
        with pytest.raises(C.CorrectionError, match="missing value"):
            C.Correction.from_json({"kind": "art_name", "source": "x"})

    def test_correcting_one_string_twice_is_refused(self):
        """Two answers for a slot that holds one — whichever came last would win, by
        file order, silently."""
        corrections = C.Corrections(
            locale="tc",
            items=[
                C.Correction(kind="art_name", source="おつルーナ", value="第一"),
                C.Correction(kind="art_name", source="おつルーナ", value="第二"),
            ],
        )

        with pytest.raises(C.CorrectionError, match="corrected twice"):
            corrections.validate()

    def test_a_mismatched_locale_key_is_refused(self, tmp_path):
        """The filename is what callers address; a mismatch means a half-edited copy."""
        write(tmp_path, "tc", [], declared="en")

        with pytest.raises(C.CorrectionError, match="declares locale"):
            C.Corrections.load("tc", tmp_path)


class TestPersistence:
    def test_round_trips(self, tmp_path):
        corrections = C.Corrections(
            locale="tc",
            items=[
                C.Correction(
                    kind="art_name", source="おつルーナ", value="辛苦啦露娜～", note="F-003"
                )
            ],
        )
        corrections.save(tmp_path)

        loaded = C.Corrections.load("tc", tmp_path)

        assert len(loaded) == 1
        assert loaded.items[0].value == "辛苦啦露娜～"
        assert loaded.items[0].note == "F-003"

    def test_a_missing_file_is_no_corrections(self, tmp_path):
        assert len(C.Corrections.load("tc", tmp_path)) == 0

    def test_written_in_a_stable_order(self, tmp_path):
        """This file is reviewed as a diff; re-ordering on save would make every PR
        against it unreadable."""
        corrections = C.Corrections(
            locale="tc",
            items=[
                C.Correction(kind="art_name", source=s, value=s)
                for s in ("う", "あ", "い")
            ],
        )
        corrections.save(tmp_path)

        raw = json.loads((tmp_path / "tc.json").read_text(encoding="utf-8"))
        sources = [c["source"] for c in raw["corrections"]]
        assert sources == sorted(sources)

    def test_load_all_discovers_locales_from_the_directory(self, tmp_path):
        """`cache_v2.load` has no locale list of its own and must not need one."""
        write(tmp_path, "tc", [
            {"kind": "art_name", "source": "おつルーナ", "value": "辛苦啦露娜～"}
        ])
        write(tmp_path, "en", [
            {"kind": "art_name", "source": "おつルーナ", "value": "Otsu Luna"}
        ])

        found = C.load_all(directory=tmp_path)

        assert sorted(found) == ["en", "tc"]

    def test_load_all_on_an_absent_directory_is_empty(self, tmp_path):
        assert C.load_all(directory=tmp_path / "nope") == {}


class TestTheCommittedFile:
    """The four F-003 strings, which waited from Phase 0 for a reviewable home."""

    def test_the_repo_corrections_are_valid(self):
        for locale, corrections in C.load_all().items():
            corrections.validate()  # raises, naming the entry, if not

    def test_the_f003_strings_are_committed(self):
        tc = C.Corrections.load("tc")
        by_source = {c.source: c.value for c in tc.items}

        assert by_source["おつルーナ"] == "辛苦啦露娜～"
        assert by_source["ぐっどないと～"] == "晚安～"
        assert by_source["ぬんぬんしよう"] == "來ぬんぬん吧"
        assert by_source["あなたの心は…くもりのち晴れ！"] == "你的心情是……陰轉晴！"
