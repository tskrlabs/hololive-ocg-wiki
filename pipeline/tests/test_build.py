"""The `filter-options` artifacts — the dropdown values `/api/filter-options` serves.

These moved off D1 in Phase 4: the answer is identical for every user until the next
reseed, and v1 recomputed it with four `SELECT DISTINCT` full scans per call on the
endpoint family whose read count breached the free tier (findings F-014).

The interesting behaviour is entirely in how *names* are keyed and labelled, because the
data disagrees with itself about what a character is called. See F-015.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from holo_schema import CardCollection
from holo_schema.enums import LOCALE_VALUES, SOURCE_LOCALE
from holo_data import build as build_module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_JSON = REPO_ROOT / "fixtures" / "cards.json"


@pytest.fixture(scope="module")
def collection() -> CardCollection:
    return CardCollection.model_validate_json(
        FIXTURES_JSON.read_text(encoding="utf-8")
    )


class TestFilterOptions:
    def test_every_locale_produces_the_same_character_count(self, collection):
        """Names are keyed on the ja name, so the count cannot vary by locale.

        This is the F-015 fix in one assertion. v1 keyed on the *displayed* name, and
        because 41% of characters are spelled inconsistently in at least one locale, its
        dropdown had more entries in some languages than others — each returning a
        subset of the character's cards. Measured on the real set: 381 entries in `en`
        against 296 in `ja`.
        """
        counts = {
            locale: len(build_module.filter_options(collection, locale)["names"])
            for locale in LOCALE_VALUES
        }
        assert len(set(counts.values())) == 1, (
            f"name count varies by locale — {counts}. Names must key on the ja name."
        )

    def test_names_key_on_the_source_locale(self, collection):
        expected = {card.translations[SOURCE_LOCALE].name for card in collection.cards}
        for locale in LOCALE_VALUES:
            options = build_module.filter_options(collection, locale)
            assert {entry["value"] for entry in options["names"]} == expected

    def test_a_translated_label_beats_the_majority_spelling(self):
        """Most cards leave the character name untranslated; the minority is the useful one.

        Only 6 of Shirakami Fubuki's 44 cards romanise the name in `en`. Picking the
        most common spelling would show Japanese text to an English reader while
        "Shirakami Fubuki" sat unused in the data.
        """
        assert build_module._best_label("白上フブキ", {"白上フブキ": 38, "Shirakami Fubuki": 6}) == (
            "Shirakami Fubuki"
        )
        # With nothing translated, the ja spelling is all there is.
        assert build_module._best_label("白上フブキ", {"白上フブキ": 44}) == "白上フブキ"
        # Two translated spellings: the more common one wins.
        assert build_module._best_label("X", {"X": 9, "Alpha": 2, "Beta": 5}) == "Beta"

    def test_labels_are_deterministic(self, collection):
        """The artifact is content-addressed by `publish`'s MD5 diff.

        A label that depended on dict ordering would upload a "changed" file on every
        build and defeat the idempotence Phase 2 exists to provide.
        """
        for locale in ("en", "ko"):
            first = build_module.filter_options(collection, locale)
            second = build_module.filter_options(collection, locale)
            assert json.dumps(first, ensure_ascii=False) == json.dumps(
                second, ensure_ascii=False
            )

    def test_tags_and_sets_come_from_the_requested_locale(self, collection):
        options = build_module.filter_options(collection, "ja")
        expected_sets = {name for card in collection.cards for name in card.card_sets}
        assert {entry["value"] for entry in options["sets"]} == expected_sets

        expected_tags = {
            tag
            for card in collection.cards
            for tag in (card.translations["ja"].tags or [])
        }
        assert {entry["value"] for entry in options["tags"]} == expected_tags

    def test_entries_are_sorted(self, collection):
        options = build_module.filter_options(collection, "tc")
        for key in ("names", "tags", "sets"):
            values = [entry["value"] for entry in options[key]]
            assert values == sorted(values), f"{key} is not sorted"

    def test_save_writes_one_file_per_locale(self, collection, tmp_path, monkeypatch):
        # Same redirect-and-reload pattern as test_publish.py's `pipeline_dirs`: the
        # path helpers are resolved at import time, so the module has to be reloaded
        # after the environment changes.
        monkeypatch.setenv("HOLO_BUILD_DIR", str(tmp_path))
        from holo_data import paths as paths_module

        importlib.reload(paths_module)
        build = importlib.reload(build_module)
        try:
            written = build.save_filter_options(collection, list(LOCALE_VALUES))
        finally:
            monkeypatch.delenv("HOLO_BUILD_DIR", raising=False)
            importlib.reload(paths_module)
            importlib.reload(build_module)

        assert set(written) == set(LOCALE_VALUES)
        for locale in LOCALE_VALUES:
            path = tmp_path / "filter-options" / f"{locale}.json"
            assert path.exists()
            parsed = json.loads(path.read_text(encoding="utf-8"))
            assert parsed["locale"] == locale
            assert parsed["names"] and parsed["sets"]
