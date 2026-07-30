"""Tests for the translation-cache backup.

What is pinned here is the difference between a backup and a file that looks like one:
the copy is read back and compared, a mismatch removes the bad copy rather than leaving
it to be trusted later, and pruning cannot empty the directory.

The cache is the only irreplaceable artifact the pipeline holds — 82,098 entries of paid
API output, gitignored and unpublished — so the failure this suite exists to prevent is a
backup that silently was not one.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from holo_data.translate import backup
from holo_data.translate.cache import CACHE_VERSION, TranslationCache


def write_cache(path, locales=None):
    """Write a small but structurally real cache file."""
    locales = locales or {
        "en": {"1": {"name": {"hash": "a" * 64, "value": "IRyS"}}},
        "tc": {
            "1": {"name": {"hash": "a" * 64, "value": "IRyS"}},
            "2": {
                "name": {"hash": "b" * 64, "value": "白上フブキ"},
                "arts[0].name": {
                    "hash": "c" * 64,
                    "value": "こんこんきーつね",
                    "source": "manual",
                },
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": CACHE_VERSION, "locales": locales}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


class TestStats:
    def test_counts_entries_cards_and_manuals(self, tmp_path):
        stats = backup.stats_for(write_cache(tmp_path / "cache.json"))

        assert stats.locales == {"en": 1, "tc": 3}
        assert stats.entry_count == 4
        assert stats.card_count == 3  # en:1 + tc:2
        assert stats.manual_count == 1

    def test_a_corrupt_file_fails_here_not_at_restore(self, tmp_path):
        """Loading, not stat-ing. A present-but-unparseable file is not a backup."""
        path = tmp_path / "cache.json"
        path.write_text("{ this is not json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            backup.stats_for(path)

    def test_byte_size_is_excluded_from_equality(self, tmp_path):
        """`save()` re-serialises, so a round-trip is semantically — not byte — equal."""
        original = write_cache(tmp_path / "cache.json")
        before = backup.stats_for(original)

        # Round-trip through the cache's own writer, which reformats.
        TranslationCache.load(original).save(tmp_path / "round-tripped.json")
        after = backup.stats_for(tmp_path / "round-tripped.json")

        assert after.byte_size != before.byte_size
        assert before.matches(after)


class TestWriteLocal:
    def test_writes_a_dated_snapshot_and_verifies_it(self, tmp_path):
        source = write_cache(tmp_path / "locales" / "translation-cache.json")
        when = datetime(2026, 8, 8, 9, 30, 0, tzinfo=timezone.utc)

        path, stats = backup.write_local(
            source=source, backup_dir=tmp_path / "backups", when=when
        )

        assert path.name == "translation-cache-20260808T093000Z.json"
        assert stats.entry_count == 4
        assert backup.stats_for(path).matches(backup.stats_for(source))

    def test_a_missing_cache_says_what_that_means(self, tmp_path):
        """A fresh clone has no cache; the error should not read like data loss."""
        with pytest.raises(backup.BackupError, match="nothing to back up"):
            backup.write_local(
                source=tmp_path / "absent.json", backup_dir=tmp_path / "backups"
            )

    def test_an_unverifiable_copy_is_deleted_rather_than_kept(self, tmp_path, monkeypatch):
        """A copy that does not match must not be left looking like a restore point."""
        source = write_cache(tmp_path / "cache.json")
        backup_dir = tmp_path / "backups"

        real_copy = backup.shutil.copy2

        def truncating_copy(src, dst):
            real_copy(src, dst)
            # Simulate a short write — the failure mode a byte-count check would miss
            # but an entry-count check catches.
            payload = json.loads(backup.Path(dst).read_text(encoding="utf-8"))
            payload["locales"].pop("tc")
            backup.Path(dst).write_text(json.dumps(payload), encoding="utf-8")

        monkeypatch.setattr(backup.shutil, "copy2", truncating_copy)

        with pytest.raises(backup.BackupError, match="verification failed"):
            backup.write_local(source=source, backup_dir=backup_dir)

        assert list(backup_dir.glob("*.json")) == []


class TestPrune:
    def test_keeps_the_newest_and_removes_the_rest(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        for day in range(1, 6):
            (backup_dir / f"translation-cache-2026080{day}T000000Z.json").write_text("{}")

        removed = backup.prune_local(backup_dir, keep=2)

        remaining = sorted(p.name for p in backup_dir.glob("*.json"))
        assert remaining == [
            "translation-cache-20260804T000000Z.json",
            "translation-cache-20260805T000000Z.json",
        ]
        assert len(removed) == 3

    def test_leaves_unrelated_files_alone(self, tmp_path):
        """A user's own file in the backup directory is not ours to delete."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "translation-cache-20260801T000000Z.json").write_text("{}")
        (backup_dir / "notes.md").write_text("mine")

        backup.prune_local(backup_dir, keep=1)

        assert (backup_dir / "notes.md").exists()

    def test_pruning_to_zero_is_refused(self, tmp_path):
        """`--keep 0` would delete the backup just taken. Never intended."""
        with pytest.raises(ValueError, match="at least 1"):
            backup.prune_local(tmp_path, keep=0)

    def test_a_missing_directory_is_not_an_error(self, tmp_path):
        assert backup.prune_local(tmp_path / "never-created") == []


class TestVerifyRestore:
    def test_a_fresh_backup_matches_the_live_cache(self, tmp_path):
        source = write_cache(tmp_path / "cache.json")
        path, _ = backup.write_local(source=source, backup_dir=tmp_path / "backups")

        assert backup.verify_restore(path, against=source).entry_count == 4

    def test_a_drifted_backup_is_reported_not_silently_accepted(self, tmp_path):
        source = write_cache(tmp_path / "cache.json")
        path, _ = backup.write_local(source=source, backup_dir=tmp_path / "backups")

        # The live cache gains an entry after the backup was taken.
        cache = TranslationCache.load(source)
        cache.put("en", "9", "name", "ソース", "translated")
        cache.save(source)

        with pytest.raises(backup.BackupError, match="does not match the live cache"):
            backup.verify_restore(path, against=source)

    def test_a_missing_backup_is_named(self, tmp_path):
        with pytest.raises(backup.BackupError, match="no backup at"):
            backup.verify_restore(tmp_path / "absent.json")


class TestR2Keys:
    def test_backups_are_namespaced_away_from_served_artifacts(self):
        """They share a bucket with cards.json; the prefix is what keeps them apart."""
        key = backup.r2_key("translation-cache-20260808T093000Z.json")

        assert key == "backups/translation-cache-20260808T093000Z.json"
        assert key.startswith(f"{backup.BACKUP_PREFIX}/")

    def test_names_sort_chronologically(self):
        """`list_r2_backups` sorts by key, which only orders correctly if names do."""
        early = backup.backup_name(datetime(2026, 8, 1, tzinfo=timezone.utc))
        late = backup.backup_name(datetime(2026, 8, 8, tzinfo=timezone.utc))

        assert sorted([late, early]) == [early, late]
