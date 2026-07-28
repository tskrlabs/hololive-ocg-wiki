"""Check the local image set against the cards that reference it.

Two levels, deliberately separated by cost.

**Coverage** is free — a set difference between the card set's `image_key`s and the WebP
tree. It runs on every `publish` as a hard gate, because a card with no image is a broken
tile and there is no reason to ever ship one.

**Provenance** costs ~2,450 HTTP requests: it re-fetches every `source_image_url` and
compares the bytes to what is on disk. That is as expensive as a re-scrape, so it is
opt-in (`--remote`) and never implicit.

Provenance exists because of F-006. v1's flat image directory meant a card whose filename
already existed was never downloaded, so two cards shared one file and one of them showed
the wrong artwork — for a year, undetected, because nothing ever compared a local file
against the URL it claimed to come from. Coverage would not have caught it: both cards
*had* an image. Only the bytes tell you it is the wrong one.

Run it once after `migrate-images` to prove the migrated set is right, and after that
only when something looks wrong.
"""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import requests

from . import paths
from .build import load as load_build, load_notices


@dataclass
class CoverageReport:
    total_cards: int = 0
    missing_png: list[str] = field(default_factory=list)
    missing_webp: list[str] = field(default_factory=list)
    orphan_webp: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (self.missing_png or self.missing_webp)


@dataclass
class ProvenanceReport:
    checked: int = 0
    matched: int = 0
    # image_key -> what went wrong
    mismatched: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def is_clean(self) -> bool:
        return not (self.mismatched or self.errors)


def check_coverage() -> CoverageReport:
    """Does every card have both a PNG and a WebP, and is anything unreferenced?"""
    collection = load_build()
    if collection is None:
        raise FileNotFoundError(
            f"no build at {paths.cards_json()} — run `holo-data build` first."
        )

    report = CoverageReport(total_cards=len(collection.cards))
    expected: set[str] = set()

    # Notices carry images too, referenced by `notices.json` rather than by any card.
    # They are checked alongside cards so a missing notice image is caught, and — just
    # as importantly — so a *present* one is not reported as an orphan on every run.
    entries = [*collection.cards, *load_notices()]

    for entry in entries:
        expected.add(entry.image_key)
        if not paths.png_path_for_key(entry.image_key).exists():
            report.missing_png.append(entry.image_key)
        if not paths.webp_path_for_key(entry.image_key).exists():
            report.missing_webp.append(entry.image_key)

    if paths.WEBP_DIR.exists():
        for path in paths.WEBP_DIR.rglob("*.webp"):
            key = paths.key_for_webp_path(path)
            if key not in expected:
                report.orphan_webp.append(key)

    report.missing_png.sort()
    report.missing_webp.sort()
    report.orphan_webp.sort()
    return report


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_one(image_key: str, source_url: str, timeout: int = 30) -> tuple[str, str | None]:
    """Compare one local PNG against the bytes the official site serves.

    Returns (image_key, problem) where problem is None when they match.
    """
    local_path = paths.png_path_for_key(image_key)
    if not local_path.exists():
        return image_key, "no local PNG"

    response = requests.get(source_url, timeout=timeout)
    response.raise_for_status()

    remote = _digest(response.content)
    local = _digest(local_path.read_bytes())

    if remote != local:
        return image_key, (
            f"bytes differ (local {local[:12]}…, source {remote[:12]}…, "
            f"{local_path.stat().st_size} vs {len(response.content)} bytes)"
        )
    return image_key, None


def check_provenance(
    limit: int | None = None,
    workers: int = 4,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> ProvenanceReport:
    """Re-fetch every card's source image and compare it to the local file.

    Modestly parallel (4 workers) and no more: this hits a small operator's site, and the
    scraper's whole posture — a deliberate 0.1–0.3 s delay between page fetches — is to
    stay a good citizen. Four concurrent image GETs is well within what any CDN-backed
    site absorbs without noticing, and the run is a one-off.
    """
    collection = load_build()
    if collection is None:
        raise FileNotFoundError(
            f"no build at {paths.cards_json()} — run `holo-data build` first."
        )

    # Notices are checked too: their images come from the same site by the same route,
    # so they are subject to the same F-012 staleness (the site silently re-uploading a
    # file) that makes this check worth its ~2,450 requests.
    targets = [
        (entry.image_key, entry.source_image_url)
        for entry in (*collection.cards, *load_notices())
        if entry.source_image_url
    ]
    if limit:
        targets = targets[:limit]

    report = ProvenanceReport()
    total = len(targets)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(check_one, key, url): key for key, url in targets
        }
        for index, future in enumerate(as_completed(futures)):
            key = futures[future]
            try:
                _, problem = future.result()
                if problem:
                    report.mismatched[key] = problem
                else:
                    report.matched += 1
            except Exception as exc:  # noqa: BLE001 — one bad fetch must not stop the run
                report.errors[key] = str(exc)
            report.checked += 1
            if on_progress:
                on_progress(index + 1, total, key)

    return report
