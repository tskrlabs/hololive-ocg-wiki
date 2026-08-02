"""Generate the R2 artifacts for local development, from the committed fixtures.

`fixtures.sql` gives a local D1 with no credentials (D12), but the site also reads three
*R2* artifacts — the per-locale filter options, `info.json` and `status.json` — and
nothing produced those locally. `make dev` therefore served a site whose filter dropdowns
404ed in six of seven locales.

**The output is committed, and this script regenerates it.** That is ADR 0001's rule
applied to fixtures rather than to the contract: generated output lives in git so a
frontend contributor needs no Python toolchain, and `make check` fails if it is stale.
Before Phase 6 this script ran on every `make dev`, which meant `uv sync`, a venv and
pydantic stood between a fresh clone and a working site — D12 asks for zero *Cloudflare
credentials*, but the spirit is zero setup, and 64 KB of committed JSON buys it.

Both are built with the **pipeline's own functions**, never a reimplementation.
`filter_options()` encodes F-015 — 41% of characters are spelled inconsistently across
their own cards — and `build_status()` encodes the artifact's shape, which ADR 0009 D26
has since grown by three counts and three lists. A second copy of either rule is exactly
the drift ADR 0001 exists to prevent, and the status report was one until D26: it was a
dict literal here, and it silently fell behind the seeder that writes the real thing.

The status report still describes a seeder run that never happened — `seed` only ever
writes to production — but it is now *synthesised by the seeder*, against an empty
database, which is what a first seed looks like.

    make generate                        # rewrite fixtures/artifacts/
    make check                           # fails if it is stale

Uploaded to the local R2 by `apps/api/scripts/seed-local-r2.sh`, which needs only
`wrangler`. Not part of the published pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "schema" / "src"))

from holo_data import seed as seed_module  # noqa: E402
from holo_data.build import filter_options  # noqa: E402
from holo_schema import CardCollection, LOCALE_VALUES  # noqa: E402

ARTIFACTS_DIR = REPO_ROOT / "fixtures" / "artifacts"


def render() -> dict[str, str]:
    """Every artifact, keyed by path relative to `fixtures/artifacts/`."""
    raw = json.loads((REPO_ROOT / "fixtures" / "cards.json").read_text("utf-8"))
    collection = CardCollection.model_validate(raw)

    out: dict[str, str] = {}

    for locale in LOCALE_VALUES:
        payload = filter_options(collection, locale)
        out[f"filter-options/{locale}.json"] = (
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )

    # A status report describing the fixture set as though it had just been seeded into an
    # empty database — every card new, which is what a first seed looks like.
    #
    # Built with the seeder's own `diff` and `build_status` rather than a dict literal, for
    # the reason the filter options are: a hand-written copy of the artifact's shape is a
    # second source of truth, and it drifts silently. It already had — this file described
    # a `counts` block that ADR 0009 D26 has since grown three fields, and nothing would
    # have failed to tell us.
    #
    # An empty `stored` is the whole trick: every card is `new`, so `source_added` fills,
    # `source_changed` stays empty, and no baseline is missing.
    rows = [seed_module.to_row(card) for card in collection.cards]
    plan = seed_module.diff(rows, {})
    status = seed_module.build_status(plan, collection, report=None, mode="full")
    # The seeder stamps the wall clock; a fixture must be reproducible or `make check`
    # fails on the second run of any given day.
    status["generated_at"] = raw["generated_at"]
    out["status.json"] = json.dumps(status, ensure_ascii=False, indent=2) + "\n"

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the output is stale")
    args = parser.parse_args()

    artifacts = render()

    if args.check:
        stale = [
            name
            for name, content in artifacts.items()
            if not (ARTIFACTS_DIR / name).exists()
            or (ARTIFACTS_DIR / name).read_text(encoding="utf-8") != content
        ]
        # A file nobody generates any more is staleness too: it would keep being uploaded
        # to the local R2 long after the reason for it went away.
        orphans = [
            str(path.relative_to(ARTIFACTS_DIR))
            for path in sorted(ARTIFACTS_DIR.rglob("*.json"))
            if str(path.relative_to(ARTIFACTS_DIR)) not in artifacts
        ]
        if stale or orphans:
            print("Fixture artifacts are out of date:", file=sys.stderr)
            for name in stale:
                print(f"  fixtures/artifacts/{name}", file=sys.stderr)
            for name in orphans:
                print(f"  fixtures/artifacts/{name} (no longer generated)", file=sys.stderr)
            print("\nRun `make generate` and commit the result.", file=sys.stderr)
            return 1
        print(f"✓ fixture artifacts are current ({len(artifacts)} files)")
        return 0

    for name, content in artifacts.items():
        target = ARTIFACTS_DIR / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"  wrote {len(artifacts)} files to fixtures/artifacts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
