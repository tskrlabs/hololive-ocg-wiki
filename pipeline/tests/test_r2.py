"""Tests for the R2 layer: config parsing, the upload diff, and key mapping.

No network. `boto3` is an optional dependency, so nothing here imports it — the diff and
the config are pure functions over local state, which is most of what can actually be
wrong. The parts that need a live bucket are exercised by `publish --dry-run` against the
real account, documented in docs/infra.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from holo_data import r2


class TestJsoncParsing:
    def test_reads_bucket_names(self, tmp_path):
        config = tmp_path / "wrangler.jsonc"
        config.write_text(
            """
            {
              // a line comment
              "name": "x",
              "r2_buckets": [
                { "binding": "IMAGES", "bucket_name": "img-bucket" },
                { "binding": "ARTIFACTS", "bucket_name": "art-bucket" }
              ]
            }
            """,
            encoding="utf-8",
        )
        assert r2.bucket_names(config) == ("img-bucket", "art-bucket")

    def test_preserves_urls_inside_strings(self, tmp_path):
        """`//` in a URL must not be treated as the start of a comment."""
        config = tmp_path / "wrangler.jsonc"
        config.write_text(
            """
            {
              "site": "https://img.example.com/path",
              "r2_buckets": [
                { "binding": "IMAGES", "bucket_name": "i" },
                { "binding": "ARTIFACTS", "bucket_name": "a" }
              ]
            }
            """,
            encoding="utf-8",
        )
        assert r2.bucket_names(config) == ("i", "a")

    def test_handles_block_comments_and_trailing_commas(self, tmp_path):
        config = tmp_path / "wrangler.jsonc"
        config.write_text(
            """
            {
              /* block
                 comment */
              "r2_buckets": [
                { "binding": "IMAGES", "bucket_name": "i" },
                { "binding": "ARTIFACTS", "bucket_name": "a" },
              ],
            }
            """,
            encoding="utf-8",
        )
        assert r2.bucket_names(config) == ("i", "a")

    def test_missing_file_explains_itself(self, tmp_path):
        with pytest.raises(r2.R2Error, match="no wrangler config"):
            r2.bucket_names(tmp_path / "absent.jsonc")

    def test_missing_binding_names_the_binding(self, tmp_path):
        config = tmp_path / "wrangler.jsonc"
        config.write_text(
            '{"r2_buckets": [{"binding": "IMAGES", "bucket_name": "i"}]}',
            encoding="utf-8",
        )
        with pytest.raises(r2.R2Error, match="ARTIFACTS"):
            r2.bucket_names(config)


class TestRealConfig:
    def test_committed_wrangler_config_is_parseable(self):
        """The real file must parse — it is the only place buckets are named."""
        images, artifacts = r2.bucket_names()
        assert images == "hololive-ocg-wiki-images"
        assert artifacts == "hololive-ocg-wiki-artifacts"


def write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class TestDiff:
    def test_new_object_uploads(self, tmp_path):
        local = {"a.webp": write(tmp_path / "a.webp", b"hello")}
        uploads, unchanged = r2.diff(local, {})
        assert [u.reason for u in uploads] == ["new"]
        assert unchanged == 0

    def test_identical_object_is_skipped(self, tmp_path):
        path = write(tmp_path / "a.webp", b"hello")
        remote = {
            "a.webp": r2.RemoteObject("a.webp", len(b"hello"), r2.md5_of(path))
        }
        uploads, unchanged = r2.diff({"a.webp": path}, remote)
        assert uploads == []
        assert unchanged == 1

    def test_different_size_uploads_without_hashing(self, tmp_path):
        path = write(tmp_path / "a.webp", b"hello")
        remote = {"a.webp": r2.RemoteObject("a.webp", 999, "whatever")}
        uploads, _ = r2.diff({"a.webp": path}, remote)
        assert [u.reason for u in uploads] == ["changed"]

    def test_same_size_different_content_is_caught_by_etag(self, tmp_path):
        """The case size alone cannot see — same length, different bytes."""
        path = write(tmp_path / "a.webp", b"hello")
        remote = {
            "a.webp": r2.RemoteObject("a.webp", 5, r2.md5_of(write(tmp_path / "b", b"world")))
        }
        uploads, _ = r2.diff({"a.webp": path}, remote)
        assert [u.reason for u in uploads] == ["changed"]

    def test_force_reuploads_identical_objects(self, tmp_path):
        path = write(tmp_path / "a.webp", b"hello")
        remote = {"a.webp": r2.RemoteObject("a.webp", 5, r2.md5_of(path))}
        uploads, unchanged = r2.diff({"a.webp": path}, remote, force=True)
        assert [u.reason for u in uploads] == ["forced"]
        assert unchanged == 0

    def test_remote_only_objects_are_left_alone(self, tmp_path):
        """publish never deletes. An extra object in the bucket is not our business."""
        remote = {"gone.webp": r2.RemoteObject("gone.webp", 1, "x")}
        uploads, unchanged = r2.diff({}, remote)
        assert uploads == []
        assert unchanged == 0


class TestLocalImages:
    def test_keys_include_the_set_folder(self, tmp_path):
        webp = tmp_path / "webp"
        write(webp / "hSD01" / "hSD01-001_OSR.webp", b"x")
        assert r2.local_images(webp) == {
            "hSD01/hSD01-001_OSR.webp": webp / "hSD01" / "hSD01-001_OSR.webp"
        }

    def test_same_name_in_two_sets_gives_two_keys(self, tmp_path):
        """F-006 — the collision that a flat layout hid."""
        webp = tmp_path / "webp"
        write(webp / "hBP03" / "hBP03-044_SR.webp", b"a")
        write(webp / "hCO01" / "hBP03-044_SR.webp", b"b")

        keys = set(r2.local_images(webp))
        assert keys == {"hBP03/hBP03-044_SR.webp", "hCO01/hBP03-044_SR.webp"}

    def test_absent_directory_is_empty_not_an_error(self, tmp_path):
        assert r2.local_images(tmp_path / "nope") == {}


class TestCoverageHelper:
    def test_reports_cards_without_images(self, tmp_path):
        local = {"hSD01/a.webp": tmp_path / "a"}
        missing = r2.iter_missing_images(iter(["hSD01/a", "hSD01/b"]), local)
        assert missing == ["hSD01/b"]


class TestContentTypes:
    def test_webp_and_json(self):
        assert r2.content_type_for(Path("a.webp")) == "image/webp"
        assert "application/json" in r2.content_type_for(Path("cards.json"))

    def test_cache_control_differs_by_kind(self):
        """Images are immutable; artifacts are replaced every build."""
        assert "immutable" in r2.IMAGE_CACHE_CONTROL
        assert "31536000" in r2.IMAGE_CACHE_CONTROL
        assert r2.ARTIFACT_CACHE_CONTROL == "no-cache"
