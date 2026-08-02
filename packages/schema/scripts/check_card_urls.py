"""Verify the committed `packages/schema/data/card-urls.json`.

This is the sitemap's only knowledge of which cards exist (#33 §5). `nuxt generate` runs
on Cloudflare's builder with no D1 binding and no credentials, and the site never loads
`cards.json` (21 MB — D8 moved querying to D1), so the URL list cannot be queried at build
time. It is emitted by `holo-data build`, committed, and imported statically by
`nuxt.config.ts`.

**The check has two tiers, and the reason is that the source is gitignored.**
`pipeline/build/cards.json` is working state — reproducible only by a full scrape — so a
fresh clone cannot regenerate this file to compare against. Hard-failing there would break
the promise `CONTRIBUTING.md` makes and ADR 0007 paid for: a frontend contributor needs no
Python toolchain and no credentials.

So:

- **Structural, always.** The properties the sitemap actually depends on — one `/` per key,
  URL-safe characters, unique, sorted, non-empty. These hold with no pipeline data, and
  they are what turns "the file parses" into "the file can build 17,241 correct URLs".
- **Byte-exact, when the build is present.** Re-render and compare, which is what catches
  the realistic failure: a new card set built and published without re-committing this.

Two invariants are **deliberately not** asserted, having been measured against the real
2,463-card set and found false — asserting either would fail on good data:

- the stem is not always prefixed by `card_number` (`hBP05/hBP02-085_HR`)
- `card_number` is not always prefixed by the set segment (582 cards; a reprint lives in
  the later set's folder, which is F-006's fix)

    make generate   # rewrite it, when a build is present
    make check      # verify it
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "schema" / "src"))

MANIFEST = REPO_ROOT / "packages" / "schema" / "data" / "card-urls.json"

# `image_key` is the URL's two path segments verbatim (D6), so anything outside this set
# would need percent-encoding — and the Worker matches the stored form exactly. Verified
# across the real set: all 2,463 keys are URL-safe unescaped.
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


def structural_problems(entries: object) -> list[str]:
    """Everything checkable without the pipeline's build output."""
    problems: list[str] = []

    if not isinstance(entries, list):
        return [f"expected a JSON array, got {type(entries).__name__}"]
    if not entries:
        # An empty manifest is the failure this whole file exists to prevent: the build
        # would succeed and emit a sitemap with no cards in it, silently.
        return ["the manifest is empty — the sitemap would list no cards at all"]

    keys: list[str] = []
    for index, entry in enumerate(entries):
        where = f"entry {index}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: expected an object, got {type(entry).__name__}")
            continue

        key = entry.get("image_key")
        number = entry.get("card_number")

        if not isinstance(key, str) or not key:
            problems.append(f"{where}: missing or non-string `image_key`")
        else:
            keys.append(key)
            if not KEY_PATTERN.match(key):
                problems.append(
                    f"{where}: `image_key` {key!r} is not `{{set}}/{{stem}}` in URL-safe "
                    "characters"
                )
        if not isinstance(number, str) or not number:
            problems.append(f"{where}: missing or non-string `card_number`")

        unexpected = sorted(set(entry) - {"image_key", "card_number"})
        if unexpected:
            problems.append(f"{where}: unexpected key(s) {', '.join(unexpected)}")

    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        # A duplicate is two sitemap entries for one URL. The unique index added in
        # commit 6 makes this impossible upstream, so it would mean a hand edit.
        shown = ", ".join(duplicates[:5])
        more = f" (+{len(duplicates) - 5} more)" if len(duplicates) > 5 else ""
        problems.append(f"duplicate `image_key`: {shown}{more}")

    if keys != sorted(keys):
        problems.append("entries are not sorted by `image_key`")

    return problems


def rendered_from_build() -> str | None:
    """The manifest as `holo-data build` would write it, or None if there is no build.

    Imported lazily: on a clone with no Python pipeline data this module is never needed,
    and the import itself pulls pydantic.
    """
    from holo_data import build as build_module
    from holo_data.paths import cards_json

    if not cards_json().exists():
        return None

    collection = build_module.load()
    if collection is None:
        return None
    return json.dumps(build_module.card_urls(collection), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the manifest is missing or stale"
    )
    args = parser.parse_args()

    if not args.check:
        # `make generate`'s path: rewrite from the build, when there is one. Silent
        # success with nothing to do is right for a clone with no pipeline data — the
        # committed file is already correct there, and there is nothing to rewrite it
        # from.
        expected = rendered_from_build()
        if expected is None:
            print("  card-urls.json unchanged — pipeline/build/cards.json is not present")
            return 0
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(expected, encoding="utf-8")
        print(f"  wrote {MANIFEST.relative_to(REPO_ROOT)} — {len(json.loads(expected))} card URLs")
        return 0

    if not MANIFEST.exists():
        print(
            f"✗ {MANIFEST.relative_to(REPO_ROOT)} is missing.\n"
            "  It is committed output — run `holo-data build` and commit the result.",
            file=sys.stderr,
        )
        return 1

    raw = MANIFEST.read_text(encoding="utf-8")
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as error:
        print(f"✗ {MANIFEST.relative_to(REPO_ROOT)} is not valid JSON: {error}", file=sys.stderr)
        return 1

    problems = structural_problems(entries)
    if problems:
        print(f"✗ {MANIFEST.relative_to(REPO_ROOT)} is malformed:", file=sys.stderr)
        for problem in problems[:20]:
            print(f"    {problem}", file=sys.stderr)
        if len(problems) > 20:
            print(f"    (+{len(problems) - 20} more)", file=sys.stderr)
        return 1

    count = len(entries)

    expected = rendered_from_build()
    if expected is None:
        # The common case for anyone who is not the maintainer, and not a failure.
        print(f"✓ card URLs well-formed ({count} cards)")
        print("  staleness unchecked — pipeline/build/cards.json is not present")
        return 0

    if expected != raw:
        print(
            f"✗ {MANIFEST.relative_to(REPO_ROOT)} is stale against "
            "pipeline/build/cards.json.\n"
            "  Run `make generate` and commit the result.",
            file=sys.stderr,
        )
        return 1

    print(f"✓ card URLs current ({count} cards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
