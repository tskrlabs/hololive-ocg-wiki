"""Tests for publish's gates and the image migration.

`publish` has no `--confirm`, so these two checks are the whole safety story: a stale
artifact must not reach R2, and a card must not ship without an image. Both are pinned
here because both fail silently in production if they regress — a stale publish looks
exactly like a successful one.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from holo_schema import CardCollection

from holo_data import publish as publish_module
from holo_data import migrate_images


@pytest.fixture()
def pipeline_dirs(tmp_path, monkeypatch):
    """Redirect every pipeline directory into a tmpdir and reload the path consumers."""
    monkeypatch.setenv("HOLO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOLO_LOCALES_DIR", str(tmp_path / "locales"))
    monkeypatch.setenv("HOLO_IMAGES_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("HOLO_BUILD_DIR", str(tmp_path / "build"))

    from holo_data import paths as paths_module

    paths = importlib.reload(paths_module)
    publish = importlib.reload(publish_module)
    migrate = importlib.reload(migrate_images)
    paths.ensure_dirs()

    yield paths, publish, migrate

    for name in ("HOLO_DATA_DIR", "HOLO_LOCALES_DIR", "HOLO_IMAGES_DIR", "HOLO_BUILD_DIR"):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(paths_module)
    importlib.reload(publish_module)
    importlib.reload(migrate_images)


def touch(path: Path, mtime: float, content: str = "{}") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    import os

    os.utime(path, (mtime, mtime))
    return path


class TestStalenessGate:
    def test_fresh_build_passes(self, pipeline_dirs):
        paths, publish, _ = pipeline_dirs
        touch(paths.i18n_file(), 1000)
        touch(paths.cache_file(), 1000)
        touch(paths.cards_json(), 2000)

        assert not publish.check_staleness().is_stale

    def test_build_older_than_scrape_is_stale(self, pipeline_dirs):
        """The realistic failure: scrape ran, build did not, publish would ship old data."""
        paths, publish, _ = pipeline_dirs
        touch(paths.cards_json(), 1000)
        touch(paths.i18n_file(), 2000)

        report = publish.check_staleness()
        assert report.is_stale
        assert paths.i18n_file() in report.newer_inputs

    def test_build_older_than_translation_cache_is_stale(self, pipeline_dirs):
        paths, publish, _ = pipeline_dirs
        touch(paths.cards_json(), 1000)
        touch(paths.cache_file(), 2000)

        assert publish.check_staleness().is_stale

    def test_absent_build_is_not_reported_as_stale(self, pipeline_dirs):
        """A missing artifact is a different error, raised later with a better message."""
        _, publish, _ = pipeline_dirs
        assert not publish.check_staleness().is_stale


class TestCoverageGate:
    def test_missing_image_is_detected(self, pipeline_dirs):
        _, publish, _ = pipeline_dirs
        local = {"hSD01/a.webp": Path("a")}
        missing, orphans = publish.check_coverage(["hSD01/a", "hSD01/b"], local)
        assert missing == ["hSD01/b"]
        assert orphans == []

    def test_orphan_is_reported_but_separate(self, pipeline_dirs):
        _, publish, _ = pipeline_dirs
        local = {"hSD01/a.webp": Path("a"), "hOLD/x.webp": Path("x")}
        missing, orphans = publish.check_coverage(["hSD01/a"], local)
        assert missing == []
        assert orphans == ["hOLD/x.webp"]

    def test_complete_set_is_clean(self, pipeline_dirs):
        _, publish, _ = pipeline_dirs
        local = {"hSD01/a.webp": Path("a")}
        assert publish.check_coverage(["hSD01/a"], local) == ([], [])


class TestCompletenessGate:
    """A build that dropped cards must not reach R2 (issue #19).

    `--allow-unknown-enums` exists so an unmapped card type does not strand an entire
    refresh, but the artifact it writes is short a card the official site prints. The
    seeder refuses it too; both gates are needed because `publish` and `seed` are
    separate commands reading the same file, and either alone leaves a path through.
    """

    def _collection(self, dropped: list[str]) -> CardCollection:
        return CardCollection(
            generated_at="2026-07-30T00:00:00Z", cards=[], dropped=dropped
        )

    def test_a_dropped_card_is_refused(self, pipeline_dirs):
        _, publish, _ = pipeline_dirs
        message = publish.check_dropped(self._collection(["2480"]))
        assert message is not None
        assert "2480" in message
        assert "mappings.py" in message, "the refusal must say how to clear it"

    def test_an_ordinary_build_passes(self, pipeline_dirs):
        _, publish, _ = pipeline_dirs
        assert publish.check_dropped(self._collection([])) is None

    def test_many_dropped_cards_are_summarised(self, pipeline_dirs):
        _, publish, _ = pipeline_dirs
        message = publish.check_dropped(self._collection([str(n) for n in range(2470, 2478)]))
        assert "+3 more" in message


class TestMigrationPlan:
    def test_maps_flat_file_to_set_scoped_key(self, tmp_path):
        source = tmp_path / "flat"
        source.mkdir()
        (source / "hSD01-001_OSR.png").write_bytes(b"art")

        key_map = {
            "hSD01/hSD01-001_OSR": "https://x/cardlist/hSD01/hSD01-001_OSR.png"
        }
        plan = migrate_images.plan(source, key_map)

        assert plan.copies == {"hSD01/hSD01-001_OSR": source / "hSD01-001_OSR.png"}
        assert plan.fetches == {}

    def test_contested_filename_is_fetched_never_copied(self, tmp_path):
        """F-006: the flat file is one of the two prints and we cannot tell which.

        Copying it to both keys would assign one card's artwork to the other — the exact
        bug being fixed. Both must come from source.
        """
        source = tmp_path / "flat"
        source.mkdir()
        (source / "hBP03-044_SR.png").write_bytes(b"one of them")

        key_map = {
            "hBP03/hBP03-044_SR": "https://x/cardlist/hBP03/hBP03-044_SR.png",
            "hCO01/hBP03-044_SR": "https://x/cardlist/hCO01/hBP03-044_SR.png",
        }
        plan = migrate_images.plan(source, key_map)

        assert plan.copies == {}
        assert set(plan.fetches) == {"hBP03/hBP03-044_SR", "hCO01/hBP03-044_SR"}
        assert plan.contested["hBP03-044_SR.png"] == [
            "hBP03/hBP03-044_SR",
            "hCO01/hBP03-044_SR",
        ]

    def test_missing_local_file_falls_back_to_fetch(self, tmp_path):
        source = tmp_path / "flat"
        source.mkdir()

        key_map = {"hSD01/new": "https://x/cardlist/hSD01/new.png"}
        plan = migrate_images.plan(source, key_map)

        assert plan.copies == {}
        assert plan.fetches == {"hSD01/new": "https://x/cardlist/hSD01/new.png"}

    def test_orphan_files_are_reported(self, tmp_path):
        source = tmp_path / "flat"
        source.mkdir()
        (source / "hSD01-001_OSR.png").write_bytes(b"art")
        (source / "ent01_teaching.png").write_bytes(b"not a card")

        key_map = {"hSD01/hSD01-001_OSR": "https://x/cardlist/hSD01/hSD01-001_OSR.png"}
        plan = migrate_images.plan(source, key_map)

        assert plan.orphan_files == ["ent01_teaching.png"]

    def test_apply_copies_without_removing_the_source(self, tmp_path, pipeline_dirs):
        """The source directory is the only complete image set — never move from it."""
        paths, _, migrate = pipeline_dirs
        source = tmp_path / "flat"
        source.mkdir()
        original = source / "hSD01-001_OSR.png"
        original.write_bytes(b"art")

        plan = migrate.plan(
            source, {"hSD01/hSD01-001_OSR": "https://x/cardlist/hSD01/hSD01-001_OSR.png"}
        )
        copied, fetched, failures = migrate.apply(plan)

        assert (copied, fetched, failures) == (1, 0, [])
        assert original.exists(), "source must survive the migration"
        assert paths.png_path_for_key("hSD01/hSD01-001_OSR").read_bytes() == b"art"


class TestKeyMapLoading:
    def test_reads_v1_camel_case(self, tmp_path):
        mapping = tmp_path / "v1.json"
        mapping.write_text(
            json.dumps(
                [
                    {
                        "id": "1",
                        "imageUrl": "https://x/cardlist/hSD01/hSD01-001_OSR.png",
                    }
                ]
            ),
            encoding="utf-8",
        )
        assert migrate_images.load_key_map(mapping) == {
            "hSD01/hSD01-001_OSR": "https://x/cardlist/hSD01/hSD01-001_OSR.png"
        }

    def test_reads_v2_wrapper_and_snake_case(self, tmp_path):
        mapping = tmp_path / "v2.json"
        mapping.write_text(
            json.dumps(
                {
                    "cards": [
                        {
                            "image_key": "hSD01/hSD01-001_OSR",
                            "source_image_url": "https://x/cardlist/hSD01/hSD01-001_OSR.png",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        assert migrate_images.load_key_map(mapping) == {
            "hSD01/hSD01-001_OSR": "https://x/cardlist/hSD01/hSD01-001_OSR.png"
        }

    def test_skips_cards_without_an_image(self, tmp_path):
        mapping = tmp_path / "v1.json"
        mapping.write_text(json.dumps([{"id": "1"}]), encoding="utf-8")
        assert migrate_images.load_key_map(mapping) == {}
