#!/usr/bin/env bash
# Populate the local R2 bucket with the three artifacts the site reads (D12).
#
# `wrangler d1 execute --local` gives us a database from `fixtures.sql`, but nothing
# equivalent existed for R2 — so `make dev` served a site whose filter dropdowns 404ed in
# six of seven locales and whose about dialog had no content. The endpoints were right;
# the local bucket was simply empty.
#
# What goes in:
#   filter-options/{locale}.json   derived from the 34 fixture cards, one per locale
#   info.json                      the real committed editorial copy
#   status.json                    a plausible seeder report over the fixture set
#
# No credentials and no network: everything is computed from files already in the repo.
# Production gets these from `holo-data build` + `publish` + `seed`.
set -euo pipefail

cd "$(dirname "$0")/.."

BUCKET=hololive-ocg-wiki-artifacts
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 ../../fixtures/build_local_artifacts.py "$TMP"

for file in "$TMP"/filter-options/*.json; do
  npx wrangler r2 object put "$BUCKET/filter-options/$(basename "$file")" \
    --local --file="$file" >/dev/null
done
npx wrangler r2 object put "$BUCKET/status.json" --local --file="$TMP/status.json" >/dev/null
npx wrangler r2 object put "$BUCKET/info.json" --local --file=../../content/info.json >/dev/null

echo "✓ local R2 seeded — 7 filter-options, info.json, status.json"
