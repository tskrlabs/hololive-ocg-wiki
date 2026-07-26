"""PNG → WebP conversion.

New in Phase 1. Nothing in v1 produced WebP: the pipeline downloaded PNGs and the
WebP files in the v1 repo were made by some step outside it. D9 requires WebP-only
uploads, so this is the missing piece.

Kept separate from both `scrape` and `publish` because all three are independently
re-runnable: adding 30 cards should not re-download 2,400 images, a failed upload should
not re-convert them, and `publish` reading only `images/webp/` makes "PNG stays a local
intermediate" structural rather than a rule someone has to remember.

Sizing, measured over 25 real cards (full set ≈ 2,500):

| format | avg/card | full set | R2 free tier (10 GB) |
|--------|---------:|---------:|---------------------:|
| PNG    |   318 KB |   776 MB | — |
| q80    |   114 KB |   278 MB | 2.8% |
| q90    |   174 KB |   425 MB | 4.3%  ← chosen |
| q100   |   303 KB |   739 MB | 7.4% |
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from .paths import PNG_DIR, WEBP_DIR, ensure_dirs

DEFAULT_QUALITY = 90
"""Card art carries fine text; q80 softens it. q90 costs ~150 MB more across the full
set and stays well inside the free tier."""


@dataclass
class ConversionResult:
    converted: int = 0
    skipped: int = 0
    failed: list[tuple[str, str]] = None  # (filename, error)

    def __post_init__(self) -> None:
        if self.failed is None:
            self.failed = []

    @property
    def total(self) -> int:
        return self.converted + self.skipped + len(self.failed)


def convert_one(png_path: Path, webp_path: Path, quality: int = DEFAULT_QUALITY) -> None:
    """Convert a single PNG to WebP, preserving transparency.

    Some card PNGs are palette-mode with transparency. Converting those straight to RGB
    flattens the alpha channel and puts black behind transparent regions, so the
    conversion goes via RGBA and only drops to RGB when there is no alpha to keep.
    """
    with Image.open(png_path) as image:
        if image.mode in ("P", "LA", "RGBA"):
            image = image.convert("RGBA")
        elif image.mode != "RGB":
            image = image.convert("RGB")

        webp_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(webp_path, "WEBP", quality=quality, method=6)


def convert_all(
    quality: int = DEFAULT_QUALITY,
    force: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> ConversionResult:
    """Convert every PNG that has no up-to-date WebP.

    Idempotent: a WebP newer than its PNG is left alone, so re-running after a scrape
    that added a handful of cards only converts those.

    Args:
        quality: WebP quality, 1–100.
        force: reconvert everything, ignoring timestamps. Needed after a quality change.
    """
    ensure_dirs()
    result = ConversionResult()

    pngs = sorted(PNG_DIR.glob("*.png"))
    total = len(pngs)

    for index, png_path in enumerate(pngs):
        webp_path = WEBP_DIR / f"{png_path.stem}.webp"

        if (
            not force
            and webp_path.exists()
            and webp_path.stat().st_mtime >= png_path.stat().st_mtime
        ):
            result.skipped += 1
        else:
            try:
                convert_one(png_path, webp_path, quality=quality)
                result.converted += 1
            except Exception as exc:  # noqa: BLE001 — one bad image must not stop the run
                result.failed.append((png_path.name, str(exc)))

        if on_progress:
            on_progress(index + 1, total, png_path.name)

    return result


def directory_size(path: Path, pattern: str = "*") -> int:
    return sum(item.stat().st_size for item in path.glob(pattern) if item.is_file())
