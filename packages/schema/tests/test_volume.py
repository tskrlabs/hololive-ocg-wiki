"""The bulk local corpus, and the properties that make it safe to load (#59).

`fixtures/volume.sql` exists so local development can reach page 4. `pageSize` is 200 and
the coverage corpus is 34 cards, so without it `hasMore` is false on every local run and
infinite scroll, the append path and the scroll restore are all unreachable — which is why
#59 was found in production three times rather than locally once.

**These assert invariants rather than bytes**, for the same reason `TestFixtures` does: the
generator's input is `holo-data build` output, which is gitignored working state, so
`make check` cannot re-run the generator and byte-compare from a fresh clone. What it *can*
do is load the committed SQL into SQLite and check the things that would actually break.

The two corpora are kept separate on purpose. Coverage is `fixtures.sql`'s job — every
enum, every structural edge case, the golden-file source, and the ~100 assertions in
`smoke.sh` written against its exact totals. This one is volume, and nothing else.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SQL = REPO_ROOT / "packages" / "schema" / "sql" / "schema.sql"
FIXTURES_SQL = REPO_ROOT / "fixtures" / "fixtures.sql"
VOLUME_SQL = REPO_ROOT / "fixtures" / "volume.sql"

# `CardListViewAPI.vue`. Restated rather than imported — it lives in a Vue SFC, and the
# point of pinning it here is that the two must not drift apart silently.
PAGE_SIZE = 200


@pytest.fixture()
def db() -> sqlite3.Connection:
    """A local D1 as `make dev` builds it: schema, then coverage, then volume."""
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    connection.executescript(FIXTURES_SQL.read_text(encoding="utf-8"))
    connection.executescript(VOLUME_SQL.read_text(encoding="utf-8"))
    return connection


def test_volume_loads_on_top_of_the_coverage_fixtures(db: sqlite3.Connection):
    """The two files must compose, which is the whole delivery mechanism.

    `volume.sql` has no `DELETE` preamble — it adds to what `fixtures.sql` loaded. If it
    ever selected a card that corpus already contains, the primary key would abort the
    script partway through and leave a half-seeded database.
    """
    total = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    distinct = db.execute("SELECT COUNT(DISTINCT id) FROM cards").fetchone()[0]
    assert total == distinct, "a card id is in both corpora — the PK would abort the load"


def test_the_local_database_reaches_a_fourth_page(db: sqlite3.Connection):
    """The one property this corpus exists for.

    Three pages is the shallowest depth at which the #59 truncation is visible: page 1 is
    what a remount refetches, so a two-page list hides the bug behind its own first page.
    """
    total = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    assert total > PAGE_SIZE * 3, (
        f"{total} cards is {total / PAGE_SIZE:.1f} pages at pageSize {PAGE_SIZE} — "
        "infinite scroll and the scroll restore need a fourth page to be reachable"
    )


def test_the_coverage_corpus_is_still_intact(db: sqlite3.Connection):
    """Volume must not disturb coverage.

    `smoke.sh` asserts exact totals against the 34 coverage cards, and it loads
    `fixtures.sql` *alone* for that reason. This checks the other direction: that loading
    volume on top does not somehow remove or rewrite any of them.
    """
    fixture_ids = {
        line.split()[0]
        for line in (REPO_ROOT / "fixtures" / "card-ids.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    }
    present = {
        row[0]
        for row in db.execute(
            f"SELECT id FROM cards WHERE id IN ({','.join('?' * len(fixture_ids))})",
            tuple(fixture_ids),
        )
    }
    assert present == fixture_ids


def test_every_volume_card_is_searchable(db: sqlite3.Connection):
    """FTS rows are inserted for the bulk cards too.

    Search is how a filtered result set gets large enough to page through, so a volume
    card missing from `cards_fts` would silently shrink exactly the result sets this
    corpus exists to make big.
    """
    cards = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    fts = db.execute("SELECT COUNT(*) FROM cards_fts").fetchone()[0]
    assert fts == cards


def test_an_unfiltered_page_two_is_full(db: sqlite3.Connection):
    """The append path's actual query, at the offset that used to be unreachable.

    `hasMore` is `cards.length < total`, so a short page 2 would end infinite scroll
    early and the restore would never be exercised past the first boundary.
    """
    rows = db.execute(
        "SELECT id FROM cards ORDER BY id LIMIT ? OFFSET ?", (PAGE_SIZE, PAGE_SIZE)
    ).fetchall()
    assert len(rows) == PAGE_SIZE
