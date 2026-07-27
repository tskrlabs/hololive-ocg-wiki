#!/usr/bin/env bash
# End-to-end check: boot the Worker against local D1 + the committed fixtures, then
# exercise every endpoint over real HTTP.
#
# The unit tests cover query shapes and input parsing with no database. This covers what
# they cannot: routing, bindings, and the D1 round trip. Phase 3's lesson was that the
# expensive bug only appeared against a real database, and `wrangler dev --local` runs
# the same workerd and the same SQLite the deployed Worker does.
#
# No credentials, no network: D12 requires a fresh clone to run with zero Cloudflare
# credentials, and this is part of what proves that stays true.
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-8899}"
BASE="http://127.0.0.1:${PORT}"
DB=hololive-ocg-wiki-db
LOG="$(mktemp -t holo-smoke)"
FAILURES=0

cleanup() {
  [[ -n "${WRANGLER_PID:-}" ]] && kill "$WRANGLER_PID" 2>/dev/null || true
  wait "${WRANGLER_PID:-}" 2>/dev/null || true
  rm -f "$LOG"
}
trap cleanup EXIT

echo "→ applying schema and fixtures to the local D1"
rm -rf .wrangler/state/v3/d1
npx wrangler d1 execute "$DB" --local --file=../../packages/schema/sql/schema.sql >/dev/null
npx wrangler d1 execute "$DB" --local --file=../../fixtures/fixtures.sql >/dev/null

echo "→ publishing a filter-options artifact to the local R2"
FILTER_OPTIONS="$(mktemp -t holo-filters).json"
printf '{"locale":"en","names":[],"tags":[],"sets":[]}' >"$FILTER_OPTIONS"
npx wrangler r2 object put "hololive-ocg-wiki-artifacts/filter-options/en.json" \
  --local --file="$FILTER_OPTIONS" >/dev/null
rm -f "$FILTER_OPTIONS"

echo "→ starting wrangler dev on :${PORT}"
npx wrangler dev --local --port "$PORT" >"$LOG" 2>&1 &
WRANGLER_PID=$!

for _ in $(seq 1 60); do
  if curl -fsS -m 2 "$BASE/api/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -fsS -m 2 "$BASE/api/health" >/dev/null 2>&1; then
  echo "✗ the Worker did not come up"
  cat "$LOG"
  exit 1
fi

# check <name> <expected-status> <path> [jq-ish python expression over the parsed body]
check() {
  local name="$1" expect="$2" path="$3" predicate="${4:-}"
  local body status
  body="$(mktemp)"
  status="$(curl -sS -o "$body" -w '%{http_code}' "${BASE}${path}")"

  if [[ "$status" != "$expect" ]]; then
    printf '  ✗ %-52s expected HTTP %s, got %s\n' "$name" "$expect" "$status"
    FAILURES=$((FAILURES + 1))
    rm -f "$body"
    return
  fi

  if [[ -n "$predicate" ]]; then
    # The body path and the predicate go in as argv, never interpolated into the source:
    # the predicates contain quotes, and splicing them produced a SyntaxError that looked
    # exactly like a failing assertion.
    if ! PREDICATE="$predicate" python3 -c '
import json, os, sys
d = json.load(open(sys.argv[1]))
predicate = os.environ["PREDICATE"]
if not eval(predicate, {"__builtins__": __builtins__}, {"d": d}):
    raise AssertionError(f"{predicate} -> {json.dumps(d, ensure_ascii=False)[:180]}")
' "$body" 2>/tmp/holo-smoke-err; then
      printf '  ✗ %-52s %s\n' "$name" "$(cat /tmp/holo-smoke-err | tail -1)"
      FAILURES=$((FAILURES + 1))
      rm -f "$body"
      return
    fi
  fi

  printf '  ✓ %-52s HTTP %s\n' "$name" "$status"
  rm -f "$body"
}

echo ""
echo "routing"
# The v1 hazard: `/api/cards/search` must not be swallowed by the `:id` route. Here that
# is structural — `:id` is constrained to digits — rather than a matter of file order.
check "search is not captured by the :id route" 200 "/api/cards/search?q=IRyS" \
  "len(d['cards']) == 1"
check "a non-numeric id is not a card"          404 "/api/cards/notanid"
check "unknown path"                            404 "/api/nope"

echo ""
echo "cards"
check "detail"                     200 "/api/cards/1?locale=tc" "d['card']['id'] == '1'"
check "detail carries colours"     200 "/api/cards/1" "d['card']['color_codes'] == ['white']"
check "detail carries sets"        200 "/api/cards/1" "len(d['card']['card_sets']) > 0"
check "detail carries Q&A"         200 "/api/cards/1" "'qa_items' in d['card']"
check "missing card"               404 "/api/cards/999999"

echo ""
echo "search"
check "empty query"                200 "/api/cards/search?q=" "d['cards'] == []"
# Each of these is an FTS5 syntax error when passed to MATCH raw. None may 500.
check "operator input: a AND"      200 "/api/cards/search?q=a%20AND" "'cards' in d"
check "operator input: -x"         200 "/api/cards/search?q=-x" "'cards' in d"
check "operator input: bare quote" 200 "/api/cards/search?q=%22" "'cards' in d"
check "operator input: fub*"       200 "/api/cards/search?q=fub*" "'cards' in d"
check "short query uses LIKE"      200 "/api/cards/search?q=%E3%81%9D%E3%82%89" "'cards' in d"

echo ""
echo "filter"
check "unfiltered page"            200 "/api/cards/filter?limit=3" \
  "len(d['cards']) == 3 and d['total'] == 34"
check "skip_count omits total"     200 "/api/cards/filter?limit=3&page=2&skip_count=true" \
  "'total' not in d"
# blue matches 4 cards outright; the 2 blue_red cards must come with it.
check "fused colours expand"       200 "/api/cards/filter?colors=blue&limit=1" "d['total'] == 6"
check "colour groups OR"           200 "/api/cards/filter?colors=blue,purple&limit=1" \
  "d['total'] == 9"
check "groups AND"                 200 "/api/cards/filter?cardTypes=oshiCharacter&rarity=OSR&limit=1" \
  "d['total'] == 2"
check "invalid colour"             400 "/api/cards/filter?colors=chartreuse"
# One ja key returns every spelling of the character (F-015).
check "name filter keys on ja"     200 "/api/cards/filter?name=%E3%81%A8%E3%81%8D%E3%81%AE%E3%81%9D%E3%82%89&locale=en" \
  "d['total'] == 2 and len({c['name'] for c in d['cards']}) == 2"

echo ""
echo "batch"
check "cards-list"                 200 "/api/cards-list/1,2" "len(d['cards']) == 2"
check "cards-list keeps order"     200 "/api/cards-list/13,1,6" \
  "[c['id'] for c in d['cards']] == ['13','1','6']"
check "cards-list over the cap"    400 "/api/cards-list/$(seq -s, 1 51)"
check "cards-list rejects junk"    400 "/api/cards-list/1%3BDROP"
check "by-card-numbers"            200 "/api/cards/by-card-numbers/hSD01-001" "len(d['cards']) == 1"
check "filter-by-card-number"      200 "/api/cards/filter-by-card-number/hSD01-001" \
  "len(d['cards']) >= 1"

echo ""
echo "filter-options"
check "served from R2"             200 "/api/filter-options?locale=en" "'names' in d"
check "unpublished locale"         404 "/api/filter-options?locale=th"
check "unknown locale falls back"  404 "/api/filter-options?locale=zz"

echo ""
echo "caching"
for path in /api/cards/1 "/api/cards/filter?limit=1" "/api/cards/search?q=IRyS"; do
  header="$(curl -sSD- -o /dev/null "${BASE}${path}" | tr -d '\r' | awk 'tolower($1) == "cache-control:" {print $2, $3}')"
  if [[ "$header" == "public, max-age=3600" ]]; then
    printf '  ✓ %-52s %s\n' "$path" "$header"
  else
    printf '  ✗ %-52s got %s\n' "$path" "${header:-none}"
    FAILURES=$((FAILURES + 1))
  fi
done

echo ""
if [[ "$FAILURES" -gt 0 ]]; then
  echo "✗ $FAILURES check(s) failed"
  exit 1
fi
echo "✓ all endpoint checks passed"
