"""Backing up the translation cache.

**The cache is the only irreplaceable thing the pipeline holds.** Everything else under
`PIPELINE_ROOT` is reproducible by re-running: the scrape can be re-fetched, images
re-converted, `cards.json` rebuilt. The cache cannot — it is the accumulated output of a
year of paid API calls, and re-creating it means paying for it again.

Yet it is the *least* protected file in the repo. `pipeline/locales/` is gitignored (D1:
generated data lives in R2, not git), and `publish` uploads `cards.json`, `info.json`,
`notices.json` and the filter options — but not this. So at the time this module was
written the cache existed in exactly one place: one directory on one laptop. 82,098
entries across 6 locales, 24 MB, no second copy anywhere.

That was survivable while the cache was only ever appended to. It stops being survivable
the moment a migration rewrites it, which is what the translation rework does — so this
module exists before that rework touches anything.

Two copies, deliberately different in kind:

- **A local dated snapshot**, outside the repo tree so a `git clean` cannot take it and a
  botched migration cannot overwrite it. Cheap, instant, and the one you actually restore
  from.
- **An R2 copy**, in the artifacts bucket under `backups/`. Survives the laptop. Costs a
  Class A operation and some storage against a 10 GB free tier.

Both are verified after writing: a backup that was never read back is a hope, not a
backup. `verify_backup` re-loads the copy through `TranslationCache.load` and compares
entry counts per locale, so a truncated write or a half-flushed buffer fails here rather
than during the restore nobody rehearsed.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..paths import cache_file
from .cache import TranslationCache

# Outside the repo, on purpose. `~/.holo-data/` rather than a directory under
# `pipeline/`: everything in the repo tree is subject to `git clean -fdx`, and a backup
# that a routine cleanup deletes is not a backup. It is also outside the working
# directory an agent operates in, which bounds the blast radius of a bad command.
DEFAULT_BACKUP_DIR = Path.home() / ".holo-data" / "cache-backups"

# R2 key prefix in the artifacts bucket.
BACKUP_PREFIX = "backups"


@dataclass
class CacheStats:
    """What a cache file contains, for comparing a copy against its original."""

    locales: dict[str, int]
    entry_count: int
    card_count: int
    manual_count: int
    byte_size: int

    def matches(self, other: "CacheStats") -> bool:
        """Same content, ignoring byte size.

        Byte size is excluded because `save()` re-serialises rather than copying bytes —
        a round-tripped cache is semantically identical but need not be byte-identical.
        The counts are what a restore depends on.
        """
        return (
            self.locales == other.locales
            and self.entry_count == other.entry_count
            and self.card_count == other.card_count
            and self.manual_count == other.manual_count
        )

    def describe(self) -> str:
        parts = ", ".join(f"{loc} {n:,}" for loc, n in sorted(self.locales.items()))
        return (
            f"{self.entry_count:,} entries across {len(self.locales)} locales "
            f"({parts}), {self.card_count:,} cards, {self.manual_count} manual, "
            f"{self.byte_size / 1_048_576:.1f} MB"
        )


def stats_for(path: Path) -> CacheStats:
    """Load a cache file and describe it.

    Loading rather than stat-ing is the point: this parses the JSON and walks every
    entry, so a file that is present but corrupt fails here.
    """
    cache = TranslationCache.load(path)
    locales = {
        locale: sum(len(fields) for fields in cards.values())
        for locale, cards in cache.entries.items()
    }
    return CacheStats(
        locales=locales,
        entry_count=sum(locales.values()),
        card_count=sum(len(cards) for cards in cache.entries.values()),
        manual_count=cache.manual_count(),
        byte_size=path.stat().st_size,
    )


def backup_name(when: datetime | None = None) -> str:
    """The filename for a snapshot taken now.

    UTC and sortable, so `ls` orders them chronologically and two backups on the same
    day do not collide.
    """
    moment = when or datetime.now(timezone.utc)
    return f"translation-cache-{moment.strftime('%Y%m%dT%H%M%SZ')}.json"


class BackupError(RuntimeError):
    """Raised when a backup could not be made or could not be verified."""


def write_local(
    source: Path | None = None,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    when: datetime | None = None,
) -> tuple[Path, CacheStats]:
    """Copy the cache to a dated file outside the repo, and verify the copy.

    Returns the backup path and the *verified* stats of the copy.

    Raises:
        BackupError: if the source is missing, or the copy does not match the original.
    """
    origin = source or cache_file()
    if not origin.exists():
        raise BackupError(
            f"no translation cache at {origin} — nothing to back up.\n"
            "If this is a fresh clone, that is expected: the cache is gitignored and "
            "is restored from a backup or rebuilt by `holo-data translate`."
        )

    before = stats_for(origin)

    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / backup_name(when)

    # copy2 preserves mtime, so a backup directory listing shows when the cache was last
    # *written*, not when it was copied — which is the more useful fact when choosing
    # which snapshot to restore.
    shutil.copy2(origin, target)

    after = stats_for(target)
    if not before.matches(after):
        target.unlink(missing_ok=True)
        raise BackupError(
            f"backup verification failed — the copy does not match the original.\n"
            f"  original: {before.describe()}\n"
            f"  copy:     {after.describe()}\n"
            "The incomplete copy has been removed."
        )

    return target, after


def prune_local(
    backup_dir: Path = DEFAULT_BACKUP_DIR, keep: int = 10
) -> list[Path]:
    """Delete all but the newest `keep` snapshots. Returns what was removed.

    At 24 MB a copy, an unbounded backup directory is a slow disk leak. Ten is enough to
    cover "the migration went wrong three runs ago" while capping the cost at ~250 MB.

    Never prunes to zero, and never touches files that do not match the backup naming
    pattern — a directory the user has put something else in is left alone.
    """
    if keep < 1:
        raise ValueError("keep must be at least 1 — pruning to zero is never intended")

    if not backup_dir.exists():
        return []

    snapshots = sorted(
        (p for p in backup_dir.glob("translation-cache-*.json") if p.is_file()),
        reverse=True,
    )

    removed = []
    for path in snapshots[keep:]:
        path.unlink()
        removed.append(path)
    return removed


def r2_key(name: str) -> str:
    """The artifacts-bucket key for a backup file."""
    return f"{BACKUP_PREFIX}/{name}"


def upload_to_r2(s3: Any, bucket: str, path: Path) -> str:
    """PUT one backup into the artifacts bucket. Returns the key written.

    Uploaded with `no-store` rather than the artifacts default of `no-cache`: a backup is
    never served to a browser, and there is no reason for any cache anywhere to hold a
    copy of it.
    """
    key = r2_key(path.name)
    with open(path, "rb") as handle:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=handle,
            ContentType="application/json; charset=utf-8",
            CacheControl="no-store",
        )
    return key


def list_r2_backups(s3: Any, bucket: str) -> list[tuple[str, int]]:
    """Every backup in the bucket as (key, size), newest first.

    Sorted by key, which sorts by timestamp because `backup_name` is ISO-ordered.
    """
    found: list[tuple[str, int]] = []
    token: str | None = None

    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": f"{BACKUP_PREFIX}/"}
        if token:
            kwargs["ContinuationToken"] = token
        response = s3.list_objects_v2(**kwargs)

        for item in response.get("Contents", []):
            found.append((item["Key"], item["Size"]))

        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")

    return sorted(found, reverse=True)


def verify_restore(backup_path: Path, against: Path | None = None) -> CacheStats:
    """Prove a backup is restorable by loading it and comparing to the live cache.

    This is the rehearsal. A backup nobody has read back is a file, not a restore point,
    and the failure mode of skipping it is discovering the problem at exactly the moment
    the original is gone.

    Raises:
        BackupError: if the backup cannot be loaded, or disagrees with the live cache.
    """
    if not backup_path.exists():
        raise BackupError(f"no backup at {backup_path}")

    restored = stats_for(backup_path)

    live_path = against or cache_file()
    if live_path.exists():
        live = stats_for(live_path)
        if not restored.matches(live):
            raise BackupError(
                "the backup does not match the live cache.\n"
                f"  live:   {live.describe()}\n"
                f"  backup: {restored.describe()}\n"
                "This is expected if the cache has changed since the backup was taken; "
                "it is a problem if the backup was just written."
            )

    return restored
