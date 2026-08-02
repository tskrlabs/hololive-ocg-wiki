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
#
# Both are laid out as `{set}/{stem}.{ext}`, mirroring `Card.image_key` exactly. That
# equivalence is the point: `publish` can walk the WebP tree and use each relative path
# (minus extension) as the R2 object key, with no lookup against cards.json. It also
# keeps the two hCO01 reprints apart on disk — see F-006, where a flat tree silently
# dropped one card's artwork for a year.
IMAGES_DIR = _env_path("HOLO_IMAGES_DIR", PIPELINE_ROOT / "images")
PNG_DIR = IMAGES_DIR / "png"
WEBP_DIR = IMAGES_DIR / "webp"

# Manual translation corrections. Committed — this is source, not working state.
CORRECTIONS_DIR = _env_path("HOLO_CORRECTIONS_DIR", PIPELINE_ROOT / "corrections")

# Build output: the canonical cards.json that Phase 2 publishes and Phase 3 seeds.
BUILD_DIR = _env_path("HOLO_BUILD_DIR", PIPELINE_ROOT / "build")

# Editorial site copy, committed at the repo root. `info.json` lives here rather than in
# the pipeline because it is not generated — it is prose the maintainer writes, which
# `publish` merely uploads (D11). It carries no facts about the data: the card count and
# date the v1 file embedded in its prose come from `cards.json`'s own `generated_at`,
# so nothing here can go stale.
CONTENT_DIR = _env_path("HOLO_CONTENT_DIR", REPO_ROOT / "content")

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


def notices_json() -> Path:
    """Non-card entries from the official card list — format-legality notices.

    An R2 artifact rather than a D1 table, for the same reason as `filter-options`: a
    handful of records, the same answer for every user until the next pipeline run, and
    nothing that needs an index. It also means adding one requires no migration against
    the populated production database. See `holo_schema.notice`.
    """
    return BUILD_DIR / "notices.json"


FILTER_OPTIONS_PREFIX = "filter-options"
"""R2 key prefix for the per-locale filter dropdown data. The Worker reads
`filter-options/{locale}.json` from the artifacts bucket."""


def filter_options_json(locale: str) -> Path:
    """One locale's dropdown values — names, tags and sets.

    Served by `/api/filter-options` straight from R2 rather than computed in D1. The
    answer is identical for every user until the next reseed, and v1 recomputed it with
    four `SELECT DISTINCT` full scans per call on the endpoint family whose read count
    breached the free tier (findings F-014). ~9-13 KB per locale, 70 KB for all seven.
    """
    return BUILD_DIR / FILTER_OPTIONS_PREFIX / f"{locale}.json"


def info_json() -> Path:
    """Editorial site copy. Source, not build output — committed and reviewed."""
    return CONTENT_DIR / "info.json"


def card_urls_json() -> Path:
    """Every card's URL, for the sitemap — **committed**, unlike the rest of the build.

    The sitemap needs one entry per card per locale, and nothing at build time can produce
    that list: `nuxt generate` runs on Cloudflare's builder with no D1 binding and no
    credentials, and the site never loads `cards.json` (21 MB — D8 moved querying to D1).
    So the list is emitted here, committed, and read by `nuxt.config.ts` as a static
    import. No D1 access, no credentials, no network during the build (#33 §5).

    That makes this the one build output that lives in git rather than in `BUILD_DIR`,
    which is ADR 0001's rule — generated output is committed so a frontend contributor
    needs no Python toolchain — applied to the sitemap for the same reason ADR 0007
    applied it to the fixtures. `make check` fails if it is stale.

    It sits beside the generated contract rather than in `fixtures/artifacts/` (which #33
    §5 suggested): that directory is the 34-card local-R2 mirror, and this describes all
    2,463 real cards. ~190 KB.
    """
    return REPO_ROOT / "packages" / "schema" / "data" / "card-urls.json"


# --- Image paths, keyed the same way the CDN is ---
#
# An image key is `{set}/{stem}` (no extension) — the same string `Card.image_key` holds
# and the same path R2 serves. These two helpers are the only places that turn a key into
# a local path, so the "local tree mirrors the bucket" property has one enforcement point.

def png_path_for_key(image_key: str) -> Path:
    return PNG_DIR / f"{image_key}.png"


def webp_path_for_key(image_key: str) -> Path:
    return WEBP_DIR / f"{image_key}.webp"


def key_for_webp_path(path: Path) -> str:
    """Inverse of `webp_path_for_key` — the R2 object key for a file in the WebP tree.

    Returns POSIX-separated text regardless of platform, because object keys are not
    filesystem paths and must not pick up a backslash on Windows.
    """
    return path.relative_to(WEBP_DIR).with_suffix("").as_posix()
