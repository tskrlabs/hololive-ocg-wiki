"""The R2 client — bucket configuration, credentials, and diffing.

R2 speaks S3, so this is `boto3` against a Cloudflare endpoint. `boto3` is an **optional
dependency** (`uv sync --extra publish`): it is 27 MB against a 53 MB environment, and
per D14 an outside contributor can never run `publish` anyway — it needs the maintainer's
Cloudflare credentials. Someone who only scrapes and builds should not pay for it.

Bucket names come from `apps/api/wrangler.jsonc`, not from a constant here. The infra
config is the one place a bucket is named; a second hardcoded list in Python is exactly
the drift ADR 0001 exists to prevent.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .paths import REPO_ROOT

WRANGLER_CONFIG = REPO_ROOT / "apps" / "api" / "wrangler.jsonc"

IMAGES_BINDING = "IMAGES"
ARTIFACTS_BINDING = "ARTIFACTS"

# Images are addressed by a key that encodes set and print, so a key's bytes never
# legitimately change (F-006 proved even a same-numbered reprint gets its own key).
# That makes a year-long immutable cache safe, and it is what keeps R2 Class B reads
# near zero: the CDN answers repeat views without touching the bucket.
IMAGE_CACHE_CONTROL = "public, max-age=31536000, immutable"

# Artifacts are replaced on every build, so they must never be served stale.
ARTIFACT_CACHE_CONTROL = "no-cache"

CONTENT_TYPES = {
    ".webp": "image/webp",
    ".json": "application/json; charset=utf-8",
}

# boto3 switches to multipart above this, and a multipart ETag is a composite hash
# rather than the object's MD5 — which would break the ETag comparison in `diff()`.
# cards.json is ~22 MB, so the threshold is raised past anything we upload.
MULTIPART_THRESHOLD = 512 * 1024 * 1024


class R2Error(RuntimeError):
    """Raised for a misconfiguration the user can fix, with a message saying how."""


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    images_bucket: str
    artifacts_bucket: str

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"


def _strip_jsonc(text: str) -> str:
    """Remove comments from JSONC so `json` can parse it.

    Wrangler's format is JSON with `//` and `/* */` comments. String literals are
    preserved — a URL like `https://…` must not lose everything after the `//`.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    index = 0

    while index < len(text):
        char = text[index]

        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            out.append(char)
            index += 1
        elif text.startswith("//", index):
            index = text.find("\n", index)
            if index == -1:
                break
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = len(text) if end == -1 else end + 2
        else:
            out.append(char)
            index += 1

    # Trailing commas are legal in JSONC and not in JSON.
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def bucket_names(config_path: Path = WRANGLER_CONFIG) -> tuple[str, str]:
    """Read the images and artifacts bucket names from `wrangler.jsonc`."""
    if not config_path.exists():
        raise R2Error(
            f"no wrangler config at {config_path}.\n"
            "It declares the bucket names and must be committed (v2-plan.md §6)."
        )

    payload = json.loads(_strip_jsonc(config_path.read_text(encoding="utf-8")))
    by_binding = {
        entry.get("binding"): entry.get("bucket_name")
        for entry in payload.get("r2_buckets", [])
    }

    missing = [b for b in (IMAGES_BINDING, ARTIFACTS_BINDING) if not by_binding.get(b)]
    if missing:
        raise R2Error(
            f"{config_path} has no r2_buckets entry for: {', '.join(missing)}"
        )

    return by_binding[IMAGES_BINDING], by_binding[ARTIFACTS_BINDING]


def load_config(config_path: Path = WRANGLER_CONFIG) -> R2Config:
    """Assemble bucket names from wrangler and credentials from the environment.

    Fails with instructions rather than letting boto3 raise `NoCredentialsError` from
    somewhere inside the request signer — the same treatment `translate` gives a missing
    `POE_API_KEY`.
    """
    images, artifacts = bucket_names(config_path)

    required = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    values = {name: os.environ.get(name, "").strip() for name in required}
    missing = [name for name, value in values.items() if not value]

    if missing:
        raise R2Error(
            "missing R2 credentials: " + ", ".join(missing) + "\n\n"
            "Add them to pipeline/.env (see pipeline/.env.example). The token needs\n"
            "Object Read & Write on both buckets — see docs/infra.md."
        )

    # Buckets can be overridden for a one-off, but the committed config is the default.
    return R2Config(
        account_id=values["R2_ACCOUNT_ID"],
        access_key_id=values["R2_ACCESS_KEY_ID"],
        secret_access_key=values["R2_SECRET_ACCESS_KEY"],
        images_bucket=os.environ.get("R2_IMAGES_BUCKET", "").strip() or images,
        artifacts_bucket=os.environ.get("R2_ARTIFACTS_BUCKET", "").strip() or artifacts,
    )


def client(config: R2Config) -> Any:
    """An S3 client pointed at R2."""
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise R2Error(
            "publish needs boto3, which is an optional dependency.\n\n"
            "  uv sync --extra publish\n\n"
            "It is optional because it is 27 MB and only the maintainer can publish."
        ) from exc

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name="auto",
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 5}),
    )


def content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def md5_of(path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 — matching S3's ETag, not hashing a secret
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class RemoteObject:
    key: str
    size: int
    etag: str


def list_objects(s3: Any, bucket: str) -> dict[str, RemoteObject]:
    """Every object in the bucket, keyed by object key.

    One paginated LIST (1,000 keys per page, so ~3 Class A operations for the full card
    set) against a 1M/month allowance. Asking the bucket is what makes `publish`
    idempotent in a way a local manifest cannot be: R2 is authoritative about R2, and a
    manifest silently lies the moment anything else writes to the bucket.
    """
    remote: dict[str, RemoteObject] = {}
    token: str | None = None

    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket}
        if token:
            kwargs["ContinuationToken"] = token
        response = s3.list_objects_v2(**kwargs)

        for item in response.get("Contents", []):
            remote[item["Key"]] = RemoteObject(
                key=item["Key"],
                size=item["Size"],
                etag=item["ETag"].strip('"'),
            )

        if not response.get("IsTruncated"):
            return remote
        token = response.get("NextContinuationToken")


@dataclass
class UploadItem:
    key: str
    path: Path
    reason: str  # "new" | "changed" | "forced"


def diff(
    local: dict[str, Path],
    remote: dict[str, RemoteObject],
    force: bool = False,
) -> tuple[list[UploadItem], int]:
    """Which local files need uploading. Returns (uploads, unchanged count).

    Size first because it is free and settles almost every case; MD5 only for the
    survivors, since hashing 425 MB to confirm nothing changed would defeat the point.
    """
    uploads: list[UploadItem] = []
    unchanged = 0

    for key, path in sorted(local.items()):
        existing = remote.get(key)

        if force:
            uploads.append(UploadItem(key, path, "forced"))
        elif existing is None:
            uploads.append(UploadItem(key, path, "new"))
        elif existing.size != path.stat().st_size:
            uploads.append(UploadItem(key, path, "changed"))
        elif existing.etag != md5_of(path):
            uploads.append(UploadItem(key, path, "changed"))
        else:
            unchanged += 1

    return uploads, unchanged


def upload(s3: Any, bucket: str, item: UploadItem, cache_control: str) -> None:
    """PUT one object with explicit content type and cache headers.

    Both headers are set deliberately rather than left to R2's inference or
    Cloudflare's default cached-extension list: cache behaviour that lives in a
    provider default is invisible in review and can change without us noticing.
    """
    with open(item.path, "rb") as handle:
        s3.put_object(
            Bucket=bucket,
            Key=item.key,
            Body=handle,
            ContentType=content_type_for(item.path),
            CacheControl=cache_control,
        )


def local_images(webp_dir: Path) -> dict[str, Path]:
    """Every WebP in the tree, keyed by its R2 object key.

    The key is the path relative to the WebP root with the extension dropped — the tree
    is laid out to make this true, so there is no lookup against cards.json here.
    """
    if not webp_dir.exists():
        return {}
    return {
        f"{path.relative_to(webp_dir).with_suffix('').as_posix()}.webp": path
        for path in webp_dir.rglob("*.webp")
    }


def iter_missing_images(
    image_keys: Iterator[str], local: dict[str, Path]
) -> list[str]:
    """Card image keys with no local WebP — the coverage gate's finding."""
    return sorted(key for key in image_keys if f"{key}.webp" not in local)
