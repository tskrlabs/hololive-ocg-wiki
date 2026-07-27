"""Read v1's `cards.json` into v2 `Card` models.

This is a **migration aid, not part of the contract**. It exists so Phase 0 can prove
the models describe reality (by validating all 2,448 live cards) and so Phase 1 has a
reference for what the repackaged pipeline must reproduce.

Delete this once `holo-data build` emits v2 shapes natively.

What it does, per the Phase 0 decisions:

- camelCase -> snake_case (decision: one convention everywhere)
- strips `_source_hash` from translations (it is translator cache bookkeeping and has
  no place in a published artifact; the pipeline keeps it in its own internal state)
- `imagePath` -> `image_key`: drops the `card_images/` prefix and the `.png` extension,
  since D9 stores the key and composes the URL
- `imageUrl` -> `source_image_url`
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")

# Keys that are already snake_case in v1 and must not be re-split.
_PASSTHROUGH = {"qa_items", "related_cards", "raw_html", "card_number", "_source_hash"}


def _snake(key: str) -> str:
    if key in _PASSTHROUGH:
        return key
    return _CAMEL_BOUNDARY.sub("_", key).lower()


def _convert(value: Any) -> Any:
    if isinstance(value, dict):
        return {_snake(k): _convert(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert(v) for v in value]
    return value


def image_key_from_path(image_path: str, source_url: str | None = None) -> str:
    """`card_images/default/hBP01-028_C_02.png` -> `default/hBP01-028_C_02`.

    Reprints collide. v1's `image_path` is derived from the image filename alone, and
    the official site reuses filenames across sets: hBP03-044_SR.png exists under both
    `/cardlist/hBP03/` and `/cardlist/hCO01/`, as two genuinely different cards (ids
    726 and 2138). v1 stored the same path for both, so one silently overwrote the
    other on disk — and under D9 they would collide as R2 objects too.

    When `source_url` is given, the set folder from the official URL replaces the
    generic `default/` bucket, so the two become `hBP03/hBP03-044_SR` and
    `hCO01/hBP03-044_SR`. The set folder is the disambiguator the site itself uses.

    Phase 2 should adopt this key scheme when uploading to R2; `CardCollection`'s
    uniqueness validator enforces that no two cards ever share a key.
    """
    path = Path(image_path)
    stem = path.with_suffix("").as_posix()
    prefix = "card_images/"
    if stem.startswith(prefix):
        stem = stem[len(prefix) :]

    if source_url:
        parts = source_url.split("/cardlist/")
        if len(parts) == 2:
            set_folder = parts[1].split("/")[0]
            if set_folder:
                filename = stem.rsplit("/", 1)[-1]
                return f"{set_folder}/{filename}"

    return stem


# v1 published these cards as `unknown` because its pipeline had no mapping for
# `サポート・スタッフ`. The type is real; the mapping entry was simply missing. Correcting
# it here keeps the fixtures — which are selected from v1's data — consistent with what
# the pipeline now produces. See docs/findings.md F-001.
_CARD_TYPE_CORRECTIONS: dict[str, str] = {
    "1877": "supportStaff",  # hBP07-091 ライブスタッフ
    "2003": "supportStaff",  # hBP07-091 ライブスタッフ, different rarity
}


def adapt_card(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert one v1 card dict into v2 `Card` keyword arguments."""
    out: dict[str, Any] = {}
    source_url = raw.get("imageUrl")

    for key, value in raw.items():
        if key == "translations":
            continue
        if key == "imagePath":
            out["image_key"] = image_key_from_path(value, source_url)
            continue
        if key == "imageUrl":
            out["source_image_url"] = value
            continue
        out[_snake(key)] = _convert(value)

    translations: dict[str, Any] = {}
    for locale, payload in raw.get("translations", {}).items():
        converted = {
            _snake(k): _convert(v)
            for k, v in payload.items()
            if k != "_source_hash"  # translator bookkeeping, not contract data
        }
        translations[locale] = converted
    out["translations"] = translations

    corrected = _CARD_TYPE_CORRECTIONS.get(out.get("id", ""))
    if corrected:
        out["card_type_code"] = corrected

    return out


def load_v1_cards(path: Path) -> list[dict[str, Any]]:
    """Load and adapt every card in a v1 `cards.json`."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [adapt_card(card) for card in raw]
