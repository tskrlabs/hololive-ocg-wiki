"""Generate `fixtures/fixtures.sql` — the committed local-development dataset.

D12's requirement is that **a fresh clone runs with zero Cloudflare credentials**. That
single property is what separates "public repo" from "contributor-ready repo", and it is
why this file exists as a committed artifact rather than as something `seed` produces:

    npx wrangler d1 execute hololive-ocg-wiki --local \\
        --file=packages/schema/sql/schema.sql
    npx wrangler d1 execute hololive-ocg-wiki --local --file=fixtures/fixtures.sql

No token, no network, no Python. `holo-data seed` is not involved at all — it is a
production tool whose entire design is about gating writes to a live database, and a
`--local` flag on it would be an invitation to reach for the wrong one (ADR 0004).

The 34 fixture cards cover every card type, every rarity, all 9 colours including both
fused dual-colour codes, all 7 locales, and 546 Q&A items — enough to exercise every
filter and the search path.

Values are emitted as SQL literals here rather than bound parameters, because the output
is a file rather than an API call. Escaping goes through `quote()` below, and the round
trip is verified by the test suite loading this file into SQLite and comparing against
the source JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from holo_schema import CardCollection

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pipeline" / "src"))

from holo_data import seed as seed_module  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "fixtures"

BANNER = """-- DO NOT EDIT — generated from fixtures/cards.json by
-- packages/schema/scripts/generate_fixtures_sql.py.
-- Regenerate with `make generate`; `make check` fails if this file is stale.
--
-- The local development dataset (D12). A fresh clone must run with zero Cloudflare
-- credentials, so this is committed rather than fetched:
--
--   npx wrangler d1 execute hololive-ocg-wiki --local \\
--       --file=packages/schema/sql/schema.sql
--   npx wrangler d1 execute hololive-ocg-wiki --local --file=fixtures/fixtures.sql
--
-- 34 cards covering every card type, every rarity, all 9 colours (including the two
-- fused dual-colour codes), all 7 locales, and every structural edge case the contract
-- models. `holo-data seed` is not involved — it only ever writes to production.
"""

# A fixed timestamp: the file is committed and diffed, so a real clock would make every
# regeneration show 34 changed rows regardless of whether the data moved.
SEEDED_AT = "1970-01-01T00:00:00Z"


def quote(value: Any) -> str:
    """One value as a SQL literal.

    SQLite escapes a single quote by doubling it, and that is the only escape needed
    inside a string literal — backslashes are not special. The fixture text carries the
    official site's raw HTML and seven languages of card text, so this is exercised
    hard; the test suite round-trips the generated file to prove it.

    Carriage returns are written as an escape rather than literally. Some card text
    carries CRLF from the official site, and a literal `\\r` inside a committed .sql
    file is both invisible in review and mangled by any tool that normalises line
    endings — including Python's own text-mode write, which silently turned this file
    into one that reported itself stale immediately after being generated.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)

    text = str(value).replace("'", "''")
    if "\r" not in text:
        return f"'{text}'"

    # char(13) concatenated between the parts, so the stored bytes round-trip exactly.
    return " || char(13) || ".join(f"'{part}'" for part in text.split("\r"))


def statements(collection: CardCollection) -> list[str]:
    lines: list[str] = []

    for card in collection.cards:
        row = seed_module.to_row(card)
        columns = ", ".join(
            [*seed_module.CARD_COLUMNS, "payload", "qa_payload", "content_hash", "qa_hash", "seeded_at"]
        )
        values = ", ".join(
            quote(value)
            for value in (
                *row.columns,
                row.payload,
                row.qa_payload,
                row.content_hash,
                row.qa_hash,
                SEEDED_AT,
            )
        )
        lines.append(f"INSERT INTO cards ({columns}) VALUES ({values});")

        for _field, table, value_column in seed_module.JUNCTIONS:
            for entry in row.junction_values.get(table, []):
                lines.append(
                    f"INSERT INTO {table} ({value_column}, card_id) "
                    f"VALUES ({quote(entry)}, {quote(row.id)});"
                )

        lines.append(
            "INSERT INTO cards_fts (card_id, card_number, text) VALUES "
            f"({quote(row.id)}, {quote(row.columns[1])}, {quote(row.search_text)});"
        )

    return lines


def render() -> str:
    source = FIXTURES_DIR / "cards.json"
    if not source.exists():
        raise SystemExit(f"no fixture set at {source} — run `make fixtures` first.")

    collection = CardCollection.model_validate_json(
        source.read_text(encoding="utf-8")
    )

    body = "\n".join(
        [
            BANNER,
            "-- Idempotent: clears the tables before loading, so re-running is safe.",
            "DELETE FROM cards_fts;",
            *(f"DELETE FROM {table};" for _f, table, _v in seed_module.JUNCTIONS),
            "DELETE FROM cards;",
            "",
            *statements(collection),
            "",
        ]
    )
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the output is stale")
    args = parser.parse_args()

    target = FIXTURES_DIR / "fixtures.sql"
    content = render()

    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            print("Generated SQL is out of date:", file=sys.stderr)
            print(f"  {target.relative_to(REPO_ROOT)}", file=sys.stderr)
            print("\nRun `make generate` and commit the result.", file=sys.stderr)
            return 1
        print("✓ fixtures.sql is current")
        return 0

    # newline="" disables Python's line-ending translation. Belt and braces alongside
    # `quote()` escaping CR: nothing in this file should depend on how the platform
    # feels about newlines.
    target.write_text(content, encoding="utf-8", newline="")
    print(f"  wrote {target.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
