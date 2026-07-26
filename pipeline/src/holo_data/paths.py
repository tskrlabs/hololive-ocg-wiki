"""Where the pipeline keeps its working files.

v1's scripts hardcoded `./data/...` relative to the current directory, so they only ran
correctly from the pipeline folder. Paths are resolved from the package location here
instead, so `holo-data` works from anywhere.

Everything under `PIPELINE_ROOT` except `corrections/` is working state: gitignored,
reproducible by re-running, and never published. Per D1 the published artifacts live in
R2, not git.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PIPELINE_ROOT = PACKAGE_ROOT.parent.parent
REPO_ROOT = PIPELINE_ROOT.parent


def _env_path(name: str, default: Path) -> Path:
    """Allow any location to be overridden, mainly so tests can use a tmpdir."""
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


# Raw scrape output — card id list, per-card HTML, structured extraction.
DATA_DIR = _env_path("HOLO_DATA_DIR", PIPELINE_ROOT / "data")

# Per-locale translations, keyed by card id. Also the translation cache's home.
LOCALES_DIR = _env_path("HOLO_LOCALES_DIR", PIPELINE_ROOT / "locales")

# Downloaded PNGs (intermediate) and converted WebP (what Phase 2 uploads).
IMAGES_DIR = _env_path("HOLO_IMAGES_DIR", PIPELINE_ROOT / "images")
PNG_DIR = IMAGES_DIR / "png"
WEBP_DIR = IMAGES_DIR / "webp"

# Manual translation corrections. Committed — this is source, not working state.
CORRECTIONS_DIR = _env_path("HOLO_CORRECTIONS_DIR", PIPELINE_ROOT / "corrections")

# Build output: the canonical cards.json that Phase 2 publishes and Phase 3 seeds.
BUILD_DIR = _env_path("HOLO_BUILD_DIR", PIPELINE_ROOT / "build")

SOURCE_SUBDIR = "default"
"""v1 named the JP scrape directory `default`. Kept so an existing working directory
can be copied across without renaming."""


def ensure_dirs() -> None:
    """Create every working directory. Safe to call repeatedly."""
    for path in (
        DATA_DIR / SOURCE_SUBDIR,
        LOCALES_DIR,
        PNG_DIR,
        WEBP_DIR,
        CORRECTIONS_DIR,
        BUILD_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


# --- Individual files ---

def card_ids_file() -> Path:
    return DATA_DIR / SOURCE_SUBDIR / "card_ids.json"


def raw_html_file() -> Path:
    return DATA_DIR / SOURCE_SUBDIR / "cards_raw_html.json"


def structured_file() -> Path:
    return DATA_DIR / SOURCE_SUBDIR / "cards_structured.json"


def i18n_file() -> Path:
    return DATA_DIR / SOURCE_SUBDIR / "cards_i18n.json"


def locale_file(locale: str) -> Path:
    return LOCALES_DIR / f"{locale}.json"


def cache_file() -> Path:
    """The field-level translation cache."""
    return LOCALES_DIR / "translation-cache.json"


def corrections_file(locale: str) -> Path:
    return CORRECTIONS_DIR / f"{locale}.json"


def cards_json() -> Path:
    return BUILD_DIR / "cards.json"
