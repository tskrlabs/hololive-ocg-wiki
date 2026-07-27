"""Upload images and artifacts to R2 (Phase 2).

`publish` deliberately has **no `--confirm` flag**, unlike `translate` and `seed`. D10
gates steps that are costly or irreversible; this is neither. Image keys are immutable by
construction, the diff makes a re-run a no-op, and ~3,000 uploads is 0.3% of the monthly
Class A allowance. A `--confirm` on a harmless command teaches the habit of typing
`--confirm` without reading, which is precisely what must not happen by the time `seed`
asks for it.

What it has instead are two gates that an agent cannot satisfy by adding a flag (D4: the
CLI may be driven by an agent, so the guard rails must be facts rather than ceremony):

1. **Staleness** — `cards.json` must be newer than the inputs it was built from.
   Publishing a stale artifact is the realistic failure, and `--confirm` would not catch
   it because the person typing it also believes the build is current.
2. **Coverage** — every card's `image_key` must resolve to a local WebP. A missing image
   is a broken tile on the site, and it is free to detect here.

The artifact is also re-validated against the contract before upload, which is where
`CardCollection`'s duplicate-key check fires (F-006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import paths, r2
from .build import load as load_build


@dataclass
class StalenessReport:
    artifact: Path
    newer_inputs: list[Path] = field(default_factory=list)

    @property
    def is_stale(self) -> bool:
        return bool(self.newer_inputs)


def check_staleness(artifact: Path | None = None) -> StalenessReport:
    """Is `cards.json` older than anything it was built from?

    Compares against the scrape output and the translation cache — the two inputs
    `build` reads. mtime rather than content hashing: this is a "did you forget to
    re-run build" check, not a security boundary, and a false positive costs one
    command.
    """
    artifact = artifact or paths.cards_json()
    report = StalenessReport(artifact=artifact)

    if not artifact.exists():
        return report

    built_at = artifact.stat().st_mtime
    for candidate in (paths.i18n_file(), paths.cache_file()):
        if candidate.exists() and candidate.stat().st_mtime > built_at:
            report.newer_inputs.append(candidate)

    return report


@dataclass
class PublishPlan:
    """Everything `publish` intends to do, computed before it does any of it."""

    image_uploads: list[r2.UploadItem] = field(default_factory=list)
    images_unchanged: int = 0
    artifact_uploads: list[r2.UploadItem] = field(default_factory=list)
    artifacts_unchanged: int = 0
    missing_images: list[str] = field(default_factory=list)
    orphan_images: list[str] = field(default_factory=list)

    @property
    def total_uploads(self) -> int:
        return len(self.image_uploads) + len(self.artifact_uploads)

    @property
    def upload_bytes(self) -> int:
        return sum(
            item.path.stat().st_size
            for item in self.image_uploads + self.artifact_uploads
        )


def check_coverage(card_keys: list[str], local: dict[str, Path]) -> tuple[list[str], list[str]]:
    """Cross-check the card set against the WebP tree, both directions.

    Missing images are a hard failure — they render as broken tiles. Orphans are only
    reported: a leftover file from a delisted card wastes a few hundred KB and is not
    worth blocking a publish over.
    """
    missing = r2.iter_missing_images(iter(card_keys), local)
    expected = {f"{key}.webp" for key in card_keys}
    orphans = sorted(key for key in local if key not in expected)
    return missing, orphans


def build_plan(s3, config: r2.R2Config, force: bool = False) -> PublishPlan:
    """Diff local state against both buckets without uploading anything."""
    plan = PublishPlan()

    collection = load_build()
    if collection is None:
        raise r2.R2Error(
            f"no build at {paths.cards_json()} — run `holo-data build` first."
        )

    local = r2.local_images(paths.WEBP_DIR)
    card_keys = [card.image_key for card in collection.cards]
    plan.missing_images, plan.orphan_images = check_coverage(card_keys, local)

    # Only publish images the card set actually references. An orphan is dead weight in
    # the bucket and, unlike a local file, it is not free to leave lying around: it is
    # world-readable at a guessable URL forever.
    publishable = {
        key: path for key, path in local.items() if key in {f"{k}.webp" for k in card_keys}
    }

    remote_images = r2.list_objects(s3, config.images_bucket)
    plan.image_uploads, plan.images_unchanged = r2.diff(publishable, remote_images, force)

    artifacts: dict[str, Path] = {"cards.json": paths.cards_json()}
    info = paths.info_json()
    if info.exists():
        artifacts["info.json"] = info

    # Per-locale dropdown values, read by /api/filter-options straight from R2. Written
    # by `build`, so they are absent on a working directory built before Phase 4 — the
    # endpoint 404s rather than the publish failing, and the next `build` supplies them.
    #
    # `status.json` is deliberately not here: it is uploaded by `seed`, which runs after
    # publish, so a copy pushed from here would always describe the previous run.
    for path in sorted((paths.BUILD_DIR / paths.FILTER_OPTIONS_PREFIX).glob("*.json")):
        artifacts[f"{paths.FILTER_OPTIONS_PREFIX}/{path.name}"] = path

    remote_artifacts = r2.list_objects(s3, config.artifacts_bucket)
    plan.artifact_uploads, plan.artifacts_unchanged = r2.diff(
        artifacts, remote_artifacts, force
    )

    return plan
