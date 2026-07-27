"""The D1 client — credentials, batched writes, and write-budget accounting.

There is no Python driver for D1, so this speaks its REST API directly:
`POST /accounts/{account}/d1/database/{database}/query`. The alternative was generating
a `.sql` file and shelling out to `wrangler`, which is what v1 did — a 1.7 MB
`migration.sql` of 49,094 statements applied in 500-statement batches.

Two properties decided it (ADR 0004):

1. **Bound parameters, not SQL literals.** v1 escaped every value by hand at each call
   site. Our data carries the official site's raw HTML in `related_cards.raw_html`,
   which is exactly where a quoting bug turns into silent data corruption. Binding
   removes the whole class.
2. **The response carries per-statement `meta`.** `rows_written` comes back for every
   statement, so `seed` reports what it *actually* wrote rather than restating its own
   estimate. A gate that cannot measure itself is ceremony.

Verified against the live API while designing Phase 3: batches return one `meta` per
statement, and **a batch is transactional** — one failing statement rolls back the
whole request and the response carries no `result` array at all. That is why `seed`
groups a card's statements into one batch: the failure boundary is a whole card, so a
card is never half-written and an interrupted run resumes with no reconciliation.

Unlike R2 — which needs boto3, a 27 MB optional extra — this needs no new dependency.
`requests` is already here for the scraper, and the REST API is plain JSON over HTTPS.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import requests

from . import r2
from .paths import REPO_ROOT

WRANGLER_CONFIG = REPO_ROOT / "apps" / "api" / "wrangler.jsonc"

DATABASE_BINDING = "DB"

# What wrangler.jsonc ships with until the database is actually created. Caught
# explicitly so the failure names the command to run, rather than surfacing as a 404
# from the REST API with an opaque id in it.
PLACEHOLDER_DATABASE_ID = "REPLACE_ME"

API_ROOT = "https://api.cloudflare.com/client/v4"
GRAPHQL_URL = f"{API_ROOT}/graphql"

# D1 free tier, per Cloudflare's published limits. Writes are the budget `seed` spends;
# reads are the one the *site* spends, and the schema redesign is what protects those.
DAILY_WRITE_LIMIT = 100_000

# D1 caps bound parameters at 100 per query. The `cards` upsert binds 17 columns, so a
# single statement can carry at most 5 cards — which is why the seeder batches by
# statement count rather than trying to pack rows into one giant INSERT.
MAX_BOUND_PARAMS = 100

# How many statements to put in one HTTP request. Not an API limit — a failure-blast
# radius. A batch is atomic, so this is also the largest amount of work one network
# error can cost us.
DEFAULT_BATCH_STATEMENTS = 80

# (connect, read). Generous on read: a batch of 80 statements against a 2,448-row table
# is fast, but D1 allows a query up to 30 seconds and we would rather wait than retry a
# write we cannot tell succeeded.
REQUEST_TIMEOUT = (15.0, 60.0)


class D1Error(RuntimeError):
    """Raised for a misconfiguration or an API failure, with a message saying how."""


@dataclass(frozen=True)
class D1Config:
    account_id: str
    api_token: str
    database_id: str
    database_name: str

    @property
    def query_url(self) -> str:
        return (
            f"{API_ROOT}/accounts/{self.account_id}"
            f"/d1/database/{self.database_id}/query"
        )


def database_binding(config_path: Path = WRANGLER_CONFIG) -> tuple[str, str]:
    """Read the D1 database name and id from `wrangler.jsonc`.

    Same rule as `r2.bucket_names`: the infra config is the one place a resource is
    named. A second hardcoded copy in Python is the drift ADR 0001 exists to prevent.
    """
    if not config_path.exists():
        raise D1Error(
            f"no wrangler config at {config_path}.\n"
            "It declares the D1 binding and must be committed (v2-plan.md §6)."
        )

    parsed = json.loads(r2._strip_jsonc(config_path.read_text(encoding="utf-8")))
    for entry in parsed.get("d1_databases", []):
        if entry.get("binding") == DATABASE_BINDING:
            name = entry.get("database_name")
            database_id = entry.get("database_id")
            if not name or not database_id:
                raise D1Error(
                    f"{config_path}: the {DATABASE_BINDING} binding is missing "
                    "database_name or database_id."
                )
            if database_id == PLACEHOLDER_DATABASE_ID:
                raise D1Error(
                    f"{config_path} still has the placeholder database_id.\n\n"
                    "Create the database and paste the id it prints:\n"
                    f"    npx wrangler d1 create {name}\n\n"
                    "See docs/infra.md. (Or set D1_DATABASE_ID for a one-off.)"
                )
            return name, database_id

    raise D1Error(
        f"{config_path} has no d1_databases entry for binding {DATABASE_BINDING!r}.\n\n"
        "Create the database and record it there:\n"
        "  npx wrangler d1 create hololive-ocg-wiki\n"
        "See docs/infra.md."
    )


def load_config(config_path: Path = WRANGLER_CONFIG) -> D1Config:
    """Assemble the database identity from wrangler and credentials from the env."""
    name, database_id = database_binding(config_path)

    account_id = r2.normalise_account_id(
        os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        or os.environ.get("R2_ACCOUNT_ID", "").strip()
    )
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()

    missing = []
    if not account_id:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if missing:
        raise D1Error(
            "missing D1 credentials: " + ", ".join(missing) + "\n\n"
            "Add them to pipeline/.env (see pipeline/.env.example). The token needs\n"
            "D1 Edit on this database and Account Analytics Read — see docs/infra.md."
        )

    if not r2.ACCOUNT_ID_PATTERN.match(account_id):
        raise D1Error(
            f"CLOUDFLARE_ACCOUNT_ID does not look like an account ID: {account_id!r}\n\n"
            "Expected 32 hex characters, e.g. 7d0fb552073ff07340658bcefeed8a89."
        )

    return D1Config(
        account_id=account_id,
        api_token=token,
        database_id=os.environ.get("D1_DATABASE_ID", "").strip() or database_id,
        database_name=name,
    )


@dataclass(frozen=True)
class Statement:
    """One parameterised SQL statement.

    `params` is always bound, never interpolated. `sqlite3` and D1 both accept `?`
    placeholders, which is what lets the same statement run against a local SQLite file
    (for `fixtures.sql` and the tests) and against D1 unchanged.
    """

    sql: str
    params: tuple[Any, ...] = ()

    def as_payload(self) -> dict[str, Any]:
        """The REST API's `{sql, params}` shape.

        Params are passed with their **native JSON types**, not stringified. Verified
        against the live API: binding `"42"` makes SQLite store text, so `typeof()`
        reports `text` and an INTEGER column silently holds a string. `hp` and `life`
        are INTEGER columns, so this is the difference between a correct row and one
        that compares wrongly the first time anything sorts on it.
        """
        return {"sql": self.sql, "params": list(self.params)}


@dataclass
class WriteReport:
    """What a run actually did, as reported by D1 rather than as estimated."""

    rows_written: int = 0
    rows_read: int = 0
    statements: int = 0
    batches: int = 0
    duration_ms: float = 0.0
    size_after: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)

    def merge(self, other: "WriteReport") -> None:
        self.rows_written += other.rows_written
        self.rows_read += other.rows_read
        self.statements += other.statements
        self.batches += other.batches
        self.duration_ms += other.duration_ms
        self.size_after = max(self.size_after, other.size_after)
        self.failures.extend(other.failures)


def client(config: D1Config) -> requests.Session:
    """A session carrying the bearer token, reused across every batch."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {config.api_token}",
            "Content-Type": "application/json",
        }
    )
    return session


def _raise_for_payload(payload: dict[str, Any], context: str) -> None:
    errors = payload.get("errors") or []
    detail = "; ".join(
        f"{item.get('code', '?')}: {item.get('message', item)}" for item in errors
    ) or "unknown error"
    raise D1Error(f"{context}: {detail}")


def execute(
    http: requests.Session, config: D1Config, statements: Sequence[Statement]
) -> WriteReport:
    """Run one batch and return what D1 says it did.

    The batch is atomic: if any statement fails, nothing in it is applied and the
    response carries no results. Verified against the live API — an INSERT followed by a
    failing statement left no row behind.
    """
    if not statements:
        return WriteReport()

    response = http.post(
        config.query_url,
        json={"batch": [statement.as_payload() for statement in statements]},
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            raise D1Error(
                f"D1 returned HTTP {response.status_code}: {response.text[:400]}"
            ) from None
        _raise_for_payload(payload, f"D1 returned HTTP {response.status_code}")

    payload = response.json()
    if not payload.get("success"):
        _raise_for_payload(payload, "D1 rejected the batch (nothing was applied)")

    report = WriteReport(statements=len(statements), batches=1)
    for result in payload.get("result", []):
        meta = result.get("meta") or {}
        report.rows_written += meta.get("rows_written", 0) or 0
        report.rows_read += meta.get("rows_read", 0) or 0
        report.duration_ms += meta.get("duration", 0.0) or 0.0
        report.size_after = max(report.size_after, meta.get("size_after", 0) or 0)
    return report


def query(
    http: requests.Session, config: D1Config, sql: str, params: Sequence[Any] = ()
) -> list[dict[str, Any]]:
    """Run one read and return its rows."""
    response = http.post(
        config.query_url,
        json=Statement(sql, tuple(params)).as_payload(),
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        try:
            _raise_for_payload(response.json(), f"D1 returned HTTP {response.status_code}")
        except ValueError:
            raise D1Error(
                f"D1 returned HTTP {response.status_code}: {response.text[:400]}"
            ) from None

    payload = response.json()
    if not payload.get("success"):
        _raise_for_payload(payload, "D1 rejected the query")

    results = payload.get("result") or []
    return results[0].get("results", []) if results else []


def table_exists(http: requests.Session, config: D1Config, name: str) -> bool:
    rows = query(
        http,
        config,
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    )
    return bool(rows)


def writes_used_today(
    config: D1Config, http: requests.Session | None = None
) -> int | None:
    """Rows written to this account's D1 so far today (UTC).

    `seed` refuses if its estimate would not fit in what is left of the daily budget.
    Checking against the flat 100k limit instead would be blind to a seed that already
    ran today — and the failure that guards against is specific: writes start failing
    *mid-run*, leaving the database partially updated.

    Returns None if analytics cannot be read (the token lacks the scope, or the API is
    unreachable). The caller decides what to do with that; `seed` degrades to warning
    rather than blocking, because a missing read permission should not stop a
    legitimate seed.

    Analytics latency was measured at under a few minutes during Phase 3 design, which
    is well inside the resolution this gate needs.
    """
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    graphql = """
    query($account: String!, $day: Date!) {
      viewer {
        accounts(filter: {accountTag: $account}) {
          d1AnalyticsAdaptiveGroups(
            limit: 100
            filter: {date_geq: $day, date_leq: $day}
          ) { sum { rowsWritten } }
        }
      }
    }
    """

    owned = http is None
    http = http or client(config)
    try:
        response = http.post(
            GRAPHQL_URL,
            json={
                "query": graphql,
                "variables": {"account": config.account_id, "day": today},
            },
            timeout=REQUEST_TIMEOUT,
        )
        payload = response.json()
        if payload.get("errors"):
            return None
        accounts = payload["data"]["viewer"]["accounts"]
        if not accounts:
            return None
        groups = accounts[0]["d1AnalyticsAdaptiveGroups"]
        return sum(entry["sum"]["rowsWritten"] for entry in groups)
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None
    finally:
        if owned:
            http.close()


def chunk(
    statements: Sequence[Statement], size: int = DEFAULT_BATCH_STATEMENTS
) -> list[list[Statement]]:
    """Split statements into batches, never splitting a group across two batches.

    Takes an already-grouped sequence and packs whole groups; the seeder passes one
    card's statements as a group so a card's rows land atomically together.
    """
    return [list(statements[i : i + size]) for i in range(0, len(statements), size)]


def pack_groups(
    groups: Sequence[Sequence[Statement]], size: int = DEFAULT_BATCH_STATEMENTS
) -> list[list[Statement]]:
    """Pack per-card statement groups into batches without splitting a group.

    A group is a card's whole write — its `cards` upsert, its junction rows, its FTS
    row. Because a D1 batch is atomic, keeping a group whole is what makes "a card is
    either fully written or not written at all" true.
    """
    batches: list[list[Statement]] = []
    current: list[Statement] = []

    for group in groups:
        if not group:
            continue
        if current and len(current) + len(group) > size:
            batches.append(current)
            current = []
        current.extend(group)

    if current:
        batches.append(current)
    return batches
