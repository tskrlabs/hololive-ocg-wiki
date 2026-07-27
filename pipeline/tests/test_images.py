"""Tests for the image tree layout and PNG → WebP conversion.

The layout is the subject here, not the pixels. `images/png/{set}/{stem}.png` and
`images/webp/{set}/{stem}.webp` mirror `Card.image_key` exactly, and that equivalence is
what lets `publish` treat a WebP path as an R2 object key with no lookup. A regression to
a flat tree would be silent — it would still convert and still upload, just to the wrong
keys, and would re-introduce the F-006 data loss — so it is pinned by test.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    """A pipeline rooted in a tmpdir, with the image trees redirected there.

    `paths` reads its directories from the environment at import time, so the modules
    that hold references to them are reloaded after the env is set.
    """
    monkeypatch.setenv("HOLO_IMAGES_DIR", str(tmp_path / "images"))

    from holo_data import paths as paths_module

    paths = importlib.reload(paths_module)

    import holo_data.images as images_module

    images = importlib.reload(images_module)

    paths.ensure_dirs()
    yield paths, images

    # Leave the modules bound to the real directories for any later test.
    monkeypatch.delenv("HOLO_IMAGES_DIR", raising=False)
    importlib.reload(paths_module)
    importlib.reload(images_module)


def write_png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), color).save(path, "PNG")


class TestPathHelpers:
    def test_key_round_trips_through_webp_path(self, tree):
        paths, _ = tree
        key = "hBP08/hBP01-028_C_02"
        assert paths.key_for_webp_path(paths.webp_path_for_key(key)) == key

    def test_png_and_webp_paths_agree_on_layout(self, tree):
        paths, _ = tree
        key = "hSD01/hSD01-001_OSR"
        png = paths.png_path_for_key(key)
        webp = paths.webp_path_for_key(key)

        assert png.relative_to(paths.PNG_DIR).with_suffix("") == webp.relative_to(
            paths.WEBP_DIR
        ).with_suffix("")

    def test_object_key_is_posix_on_every_platform(self, tree):
        """R2 keys are not filesystem paths — a backslash would be part of the name."""
        paths, _ = tree
        key = paths.key_for_webp_path(paths.webp_path_for_key("hCO01/hBP03-044_SR"))
        assert "\\" not in key
        assert key == "hCO01/hBP03-044_SR"


class TestConversionLayout:
    def test_mirrors_set_folders_into_webp_tree(self, tree):
        paths, images = tree
        write_png(paths.PNG_DIR / "hSD01" / "hSD01-001_OSR.png", (255, 0, 0))
        write_png(paths.PNG_DIR / "hBP08" / "hBP01-028_C_02.png", (0, 255, 0))

        result = images.convert_all()

        assert result.converted == 2
        assert (paths.WEBP_DIR / "hSD01" / "hSD01-001_OSR.webp").exists()
        assert (paths.WEBP_DIR / "hBP08" / "hBP01-028_C_02.webp").exists()

    def test_same_filename_in_two_sets_stays_two_files(self, tree):
        """F-006: hBP03-044_SR is different artwork in hBP03 and hCO01.

        A flat tree collapsed these to one file and shipped one card's art for both.
        """
        paths, images = tree
        write_png(paths.PNG_DIR / "hBP03" / "hBP03-044_SR.png", (255, 0, 0))
        write_png(paths.PNG_DIR / "hCO01" / "hBP03-044_SR.png", (0, 0, 255))

        result = images.convert_all()
        assert result.converted == 2

        original = paths.WEBP_DIR / "hBP03" / "hBP03-044_SR.webp"
        reprint = paths.WEBP_DIR / "hCO01" / "hBP03-044_SR.webp"
        assert original.exists() and reprint.exists()
        assert original.read_bytes() != reprint.read_bytes()

    def test_finds_nested_pngs(self, tree):
        """A flat glob would report zero files and convert nothing."""
        paths, images = tree
        write_png(paths.PNG_DIR / "hSD01" / "a.png", (1, 2, 3))

        assert images.convert_all().converted == 1

    def test_rerun_is_idempotent(self, tree):
        paths, images = tree
        write_png(paths.PNG_DIR / "hSD01" / "a.png", (1, 2, 3))

        assert images.convert_all().converted == 1
        second = images.convert_all()
        assert second.converted == 0
        assert second.skipped == 1

    def test_directory_size_counts_nested_files(self, tree):
        paths, images = tree
        write_png(paths.PNG_DIR / "hSD01" / "a.png", (1, 2, 3))
        write_png(paths.PNG_DIR / "hBP08" / "b.png", (4, 5, 6))

        assert images.directory_size(paths.PNG_DIR, "*.png") > 0
