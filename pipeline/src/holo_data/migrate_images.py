"""Move v1's flat image directory into the set-scoped tree.

**Run this once, before the first `holo-data publish`.** v1 wrote every card image into
one directory keyed by filename; v2 uses `images/png/{set}/{stem}.png` so the local tree
mirrors `Card.image_key` and therefore the R2 bucket (Phase 2).

Re-scraping would produce the same result, correctly, but it costs ~2,450 requests
against a small operator's site for files that are already on disk. A year of runs has
kept to a deliberate 0.1–0.3 s delay; re-pulling a gigabyte to rename directories is not
a good way to spend that goodwill. So this copies what exists and fetches only what it
cannot place.

**The one thing it cannot copy.** When two sets ship different artwork under the same
filename — F-006's `hBP03-044_SR.png` and `hBP03-055_SR.png`, each present in both hBP03
and hCO01 — v1 only ever stored *one* file, because `download_image()` skipped any name
already on disk. Which of the two prints won is not recoverable from the filename, the
bytes, or the mtime. Guessing would silently assign one card's artwork to the other,
which is exactly the bug being fixed. Both members of such a pair are therefore
re-downloaded from source and neither is copied.

Migration aid, not part of the pipeline. Delete it once the tree is established.
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests

from .paths import PNG_DIR, ensure_dirs, png_path_for_key
from .transform import image_key_from_url

V1_IMAGE_DIR = Path(
    "/Users/chingli/lichingchester/tool/python-scripts/hololive-ocg-data-v2/card_images/default"
)
"""Where the maintainer's working images live. A default, not an assumption — override
with `--source`."""

V1_MAPPING = Path(
    "/Users/chingli/lichingchester/tool/python-scripts/hololive-ocg-data-v2/data/cards_i18n_combined.json"
)
"""Any v1 artifact carrying `imageUrl` per card. The set folder is only recoverable from
the original URL, so a file listing alone is not enough to migrate."""


@dataclass
class MigrationPlan:
    """What the migration would do, computed before anything is written."""

    # image_key -> source file to copy from
    copies: dict[str, Path] = field(default_factory=dict)
    # image_key -> source URL, for keys no local file can safely supply
    fetches: dict[str, str] = field(default_factory=dict)
    # filenames on disk that no card refers to
    orphan_files: list[str] = field(default_factory=list)
    # image_keys whose card exists but which have no source at all
    unresolved: list[str] = field(default_factory=list)
    # filename -> the keys that share it (F-006 shape)
    contested: dict[str, list[str]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.copies) + len(self.fetches)


def load_key_map(mapping_file: Path) -> dict[str, str]:
    """Read a v1 artifact into `image_key -> source URL`.

    Accepts either a bare list of cards (v1's `cards.json`) or the `{cards: [...]}`
    wrapper the v2 contract uses, and tolerates both camelCase and snake_case keys —
    the file may be v1's or ours depending on when this is run.
    """
    payload = json.loads(mapping_file.read_text(encoding="utf-8"))
    cards = payload if isinstance(payload, list) else payload.get("cards", [])

    key_map: dict[str, str] = {}
    for card in cards:
        url = card.get("imageUrl") or card.get("source_image_url")
        if not url:
            continue
        key = card.get("image_key") or image_key_from_url(url, url.split("/")[-1])
        if key:
            key_map[key] = url
    return key_map


def plan(source_dir: Path, key_map: dict[str, str]) -> MigrationPlan:
    """Decide, per key, whether a local file can supply it or it must be fetched.

    A local file is only trusted when its filename maps to exactly one key. The moment
    two keys share a filename, the file on disk is one of them and there is no way to
    tell which, so both go to `fetches`.
    """
    result = MigrationPlan()

    by_filename: dict[str, list[str]] = defaultdict(list)
    for key in key_map:
        by_filename[f"{key.split('/')[-1]}.png"].append(key)

    for filename, keys in by_filename.items():
        source = source_dir / filename

        if len(keys) > 1:
            result.contested[filename] = sorted(keys)
            for key in keys:
                result.fetches[key] = key_map[key]
            continue

        key = keys[0]
        if source.exists():
            result.copies[key] = source
        elif key_map[key]:
            result.fetches[key] = key_map[key]
        else:
            result.unresolved.append(key)

    if source_dir.exists():
        known = set(by_filename)
        result.orphan_files = sorted(
            path.name for path in source_dir.glob("*.png") if path.name not in known
        )

    return result


def fetch_one(url: str, destination: Path) -> None:
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as handle:
        for chunk in response.iter_content(8192):
            handle.write(chunk)


def apply(
    migration: MigrationPlan,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> tuple[int, int, list[tuple[str, str]]]:
    """Execute the plan. Returns (copied, fetched, failures).

    Copies rather than moves: the source directory is the only complete set of these
    images, and a migration that turns out to be wrong should be re-runnable. Disk is
    cheaper than a re-scrape.
    """
    ensure_dirs()
    copied = fetched = 0
    failures: list[tuple[str, str]] = []
    done = 0

    for key, source in sorted(migration.copies.items()):
        destination = png_path_for_key(key)
        try:
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            copied += 1
        except Exception as exc:  # noqa: BLE001 — one bad file must not stop the run
            failures.append((key, str(exc)))
        done += 1
        if on_progress:
            on_progress(done, migration.total, key)

    for key, url in sorted(migration.fetches.items()):
        try:
            fetch_one(url, png_path_for_key(key))
            fetched += 1
        except Exception as exc:  # noqa: BLE001
            failures.append((key, str(exc)))
        done += 1
        if on_progress:
            on_progress(done, migration.total, key)

    return copied, fetched, failures


def existing_keys() -> set[str]:
    """Every image key already present in the PNG tree."""
    if not PNG_DIR.exists():
        return set()
    return {
        path.relative_to(PNG_DIR).with_suffix("").as_posix()
        for path in PNG_DIR.rglob("*.png")
    }
