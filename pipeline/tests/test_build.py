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
from holo_data.translate.cache import TranslationCache

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

    def test_sets_key_on_the_set_name(self, collection):
        options = build_module.filter_options(collection, "ja")
        expected_sets = {name for card in collection.cards for name in card.card_sets}
        assert {entry["value"] for entry in options["sets"]} == expected_sets

    def test_tags_key_on_the_identity_not_the_display_text(self, collection):
        """`Card.tags` is what the junction holds; `Translation.tags` carries the `#`.

        Emitting the display spelling as `value` sent `#0期生` to a `WHERE tag = ?`
        matching `0期生`, so **the tag filter returned zero cards for every tag in every
        locale** (#26). Measured against the deployed site: 0 rows for the prefixed
        value, 165 for the unprefixed one.

        Same shape as the name split in F-015 — the filter keys on the stable identity,
        and the localised text is a label.
        """
        expected = {tag for card in collection.cards for tag in (card.tags or [])}

        for locale in LOCALE_VALUES:
            options = build_module.filter_options(collection, locale)
            values = {entry["value"] for entry in options["tags"]}
            assert values == expected
            assert not any(value.startswith("#") for value in values), (
                "a `#`-prefixed value is display text, and matches nothing in card_tags"
            )

    def test_a_tag_label_is_the_locale_display_text(self, collection):
        """The prefix belongs on the label, where it is presentation rather than a key."""
        options = build_module.filter_options(collection, "ja")
        by_value = {entry["value"]: entry["label"] for entry in options["tags"]}

        for card in collection.cards:
            shown = card.translations["ja"].tags or []
            for index, identity in enumerate(card.tags or []):
                if index < len(shown):
                    assert by_value[identity] == shown[index]

    def test_every_tag_label_carries_the_prefix(self, collection):
        """Uniformly — not "if someone curated this one".

        All 5,481 tag occurrences carry `#` in every locale, but the glossary stores the
        bare text (`"0th Gen"`). Taking the curated value verbatim gave `"#0期生"` in `ja`
        and `"0th Gen"` in `en`, so a tag's prefix depended on whether it happened to be
        curated. The prefix is normalised in one place instead.
        """
        for locale in LOCALE_VALUES:
            labels = [e["label"] for e in build_module.filter_options(collection, locale)["tags"]]
            assert labels, f"{locale} produced no tags"
            assert all(label.startswith("#") for label in labels), locale
            assert not any(label.startswith("##") for label in labels), locale

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


def _buildable_card(card_id: str, **overrides) -> dict:
    """The smallest dict that validates as a `Card`, for the escape-hatch tests."""
    card = {
        "id": card_id,
        "card_number": f"hBP01-{card_id.zfill(3)}",
        "card_type_code": "character",
        "rarity_code": "C",
        "image_key": f"hBP01/{card_id}",
        "source_image_url": f"https://example.invalid/{card_id}.png",
        "card_sets": ["hBP01"],
        "bloom_level_code": "debut",
        "translations": {"ja": {"name": f"card {card_id}"}},
    }
    card.update(overrides)
    return card


class TestUnknownEnumEscapeHatch:
    """`--allow-unknown-enums` — what it does, and that it does anything at all.

    It had never worked. `build()` computed a `blocking` flag that honoured the
    argument, then discarded it: the very next condition was
    `len(validated) != len(cards)`, which is true precisely when a card failed
    validation — the case the flag exists for. So the collection came back `None`
    whatever the caller passed, and no test covered it.

    That mattered beyond the dead code path. F-008 settled `サポート・ロケーション`
    partly on the ground that a blocked build is "recoverable in minutes and has
    `--allow-unknown-enums` as an escape hatch", and issue #19 weighed blocking against
    the same premise. Neither was true when written.
    """

    def test_an_unmapped_enum_value_blocks_by_default(self):
        collection, _notices, report = build_module.build(
            [_buildable_card("1"), _buildable_card("2", bloom_level_code="新形態")],
            TranslationCache(),
            [],
        )
        assert collection is None, "an unrecognised enum value must stop the build"
        assert report.enum_violations
        assert not report.errors, "an enum value is not a structural error"

    def test_the_flag_ships_the_valid_cards_and_drops_the_rest(self):
        """The regression test for the bug above: this returned `None` before.

        Note what the flag cannot do. The contract's enums are closed `Literal`s, so a
        card carrying an unmapped value cannot be constructed as a `Card` at all —
        "publish anyway", which is what the docstring promised for four phases, was
        never implementable. Dropping is the only coherent reading.
        """
        collection, _notices, report = build_module.build(
            [_buildable_card("1"), _buildable_card("2", bloom_level_code="新形態")],
            TranslationCache(),
            [],
            allow_unknown_enums=True,
        )
        assert collection is not None, "the flag must actually produce a collection"
        assert [card.id for card in collection.cards] == ["1"]
        assert collection.dropped == ["2"]
        assert report.valid == 1

    def test_a_structural_error_blocks_even_with_the_flag(self):
        """The hatch is for unmapped enum values, not for malformed cards.

        A missing required field means the scraper broke, and there is no mapping to
        add that would fix it — so the flag must not become a way to ship past it.
        """
        broken = _buildable_card("2")
        del broken["rarity_code"]

        collection, _notices, report = build_module.build(
            [_buildable_card("1"), broken],
            TranslationCache(),
            [],
            allow_unknown_enums=True,
        )
        assert collection is None
        assert report.errors

    def test_an_ordinary_build_records_no_dropped_cards(self):
        """`dropped` is empty on every normal build, which is what the gates key on."""
        collection, _notices, _report = build_module.build(
            [_buildable_card("1")], TranslationCache(), []
        )
        assert collection is not None
        assert collection.dropped == []
