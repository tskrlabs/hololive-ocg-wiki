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
# Both stores are wiped, not just D1. The artifact checks below assert that a
# never-published bucket 404s, and local R2 persists across runs — so without this the
# first run would pass and every later one would find last run's objects still there.
rm -rf .wrangler/state/v3/d1 .wrangler/state/v3/r2
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

# check_html <name> <expected-status> <path> [grep -E pattern the body must match]
#
# The card page returns HTML, not JSON, so `check` above cannot read it. This is what the
# metadata injection needs: what a crawler sees is the *served bytes*, before any
# JavaScript runs, which is exactly what curl gets and a browser test would not.
check_html() {
  local name="$1" expect="$2" path="$3" pattern="${4:-}"
  local body status
  body="$(mktemp)"
  status="$(curl -sS -o "$body" -w '%{http_code}' "${BASE}${path}")"

  if [[ "$status" != "$expect" ]]; then
    printf '  ✗ %-52s expected HTTP %s, got %s\n' "$name" "$expect" "$status"
    FAILURES=$((FAILURES + 1))
    rm -f "$body"
    return
  fi

  if [[ -n "$pattern" ]] && ! grep -qE "$pattern" "$body"; then
    printf '  ✗ %-52s body did not match: %s\n' "$name" "$pattern"
    FAILURES=$((FAILURES + 1))
    rm -f "$body"
    return
  fi

  printf '  ✓ %-52s HTTP %s\n' "$name" "$status"
  rm -f "$body"
}

# check_redirect <name> <expected-status> <path> <expected Location suffix>
check_redirect() {
  local name="$1" expect="$2" path="$3" suffix="$4"
  local status location
  status="$(curl -sS -o /dev/null -w '%{http_code}' "${BASE}${path}")"
  location="$(curl -sS -o /dev/null -w '%{redirect_url}' "${BASE}${path}")"

  if [[ "$status" != "$expect" || "$location" != *"$suffix" ]]; then
    printf '  ✗ %-52s HTTP %s -> %s\n' "$name" "$status" "$location"
    FAILURES=$((FAILURES + 1))
    return
  fi

  printf '  ✓ %-52s HTTP %s\n' "$name" "$status"
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
echo "cards by image key (ADR 0009 D6 — a card's URL)"
# `{set}/{stem}` is `image_key` verbatim, so this is how a card page resolves.
check "by key"                     200 "/api/cards/by-key/hSD01/hSD01-001_OSR?locale=tc" \
  "d['card']['image_key'] == 'hSD01/hSD01-001_OSR'"
check "by key carries Q&A"         200 "/api/cards/by-key/hSD01/hSD01-001_OSR" \
  "'qa_items' in d['card']"
check "by key honours locale"      200 "/api/cards/by-key/hSD01/hSD01-001_OSR?locale=en" \
  "d['card']['locale'] == 'en'"
# A wrong-case key reports the canonical form so the caller can 301 rather than 404.
# Safe because lowercasing all 2,463 real keys still yields 2,463 distinct values.
check "wrong case names the canonical" 404 "/api/cards/by-key/HSD01/hsd01-001_osr" \
  "d['canonical'] == 'hSD01/hSD01-001_OSR'"
check "unknown key"                404 "/api/cards/by-key/hSD01/NOPE" "'canonical' not in d"
check "malformed key segment"      400 "/api/cards/by-key/hSD01/bad%20key"

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
# One ja key returns every card for the character (F-015).
#
# This used to assert *two different* `en` spellings — the F-015 defect pinned as a
# fixture property, back when the filter had to key on ja precisely because the same
# character was spelled inconsistently. #23 made one source string resolve to one
# translation, so the spellings now agree and the count is 1. The filter still keys on
# ja, which is what this checks; the reason it must has simply stopped being visible.
check "name filter keys on ja"     200 "/api/cards/filter?name=%E3%81%A8%E3%81%8D%E3%81%AE%E3%81%9D%E3%82%89&locale=en" \
  "d['total'] == 2 and len({c['name'] for c in d['cards']}) == 1"

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
echo "artifacts"
# Checked before publishing, so the missing-artifact branch is exercised rather than
# assumed. A fresh bucket is the realistic state: `publish` and `seed` are maintainer
# steps that a contributor's clone has never run.
check "info before publish"        404 "/api/info"
check "status before publish"      404 "/api/status"
# Notices are the exception to the 404-when-absent rule, deliberately: "no notices
# published" and "no notices exist" are the same answer to a caller, and a site
# rendering a notices section should not have to treat a 404 as success.
check "notices before publish"     200 "/api/notices" "d['notices'] == []"

# `content/info.json` is the real committed artifact, not a stand-in — the same bytes
# `holo-data publish` uploads. `status.json` has no committed copy (it is written by
# `seed` against a live database), so it is faked here, shaped exactly as `build_status`
# emits it.
npx wrangler r2 object put "hololive-ocg-wiki-artifacts/info.json" \
  --local --file=../../content/info.json >/dev/null
STATUS_FILE="$(mktemp -t holo-status).json"
printf '{"generated_at":"2026-07-27T06:17:56Z","built_at":"2026-07-26T23:33:21Z","mode":"diff","counts":{"total":34,"new":0,"changed":34,"qa_updated":0,"unchanged":0,"removed":0,"missing_from_build":0},"new":[],"changed":[{"id":"1","card_number":"hSD01-001","image_key":"hSD01/hSD01-001_OSR","name":"ときのそら"}],"qa_updated":[],"removed":[]}' >"$STATUS_FILE"
npx wrangler r2 object put "hololive-ocg-wiki-artifacts/status.json" \
  --local --file="$STATUS_FILE" >/dev/null
rm -f "$STATUS_FILE"

check "info served from R2"        200 "/api/info" "'disclaimer' in d and 'contents' in d"
# The one fact the info dialog needs and info.json deliberately does not carry: v1 hard-
# coded "2448 cards (June 19, 2026)" into its prose, so it was permanently out of date.
check "info carries no card count" 200 "/api/info" \
  "not any('cards' in str(c) and any(ch.isdigit() for ch in str(c)) for c in d['contents'])"
check "status served from R2"      200 "/api/status" \
  "d['counts']['total'] == 34 and 'generated_at' in d"
check "status carries the diff"    200 "/api/status" \
  "d['changed'][0]['image_key'] == 'hSD01/hSD01-001_OSR'"

# A rules notice — the non-card entries the official site publishes into its card list
# (F-020). Shaped exactly as `NoticeCollection` emits it. The assertions pin the two
# properties that make it not-a-card: no card_number, and a body that carries the rule.
NOTICES_FILE="$(mktemp -t holo-notices).json"
printf '{"generated_at":"2026-07-28T00:00:00Z","schema_version":1,"notices":[{"id":"2459","image_key":"sele08/sele08_teaching","source_image_url":"https://example.invalid/sele08_teaching.png","card_sets":["【使用可能カード】セレクションカップ"],"translations":{"ja":{"name":"デッキ構築ルール","body":"※本説明用カードはデッキ登録できません。"}}}]}' >"$NOTICES_FILE"
npx wrangler r2 object put "hololive-ocg-wiki-artifacts/notices.json" \
  --local --file="$NOTICES_FILE" >/dev/null
rm -f "$NOTICES_FILE"

check "notices served from R2"     200 "/api/notices" \
  "len(d['notices']) == 1 and d['notices'][0]['id'] == '2459'"
check "a notice has no card_number" 200 "/api/notices" \
  "'card_number' not in d['notices'][0] and 'rarity_code' not in d['notices'][0]"
check "a notice carries its rule"  200 "/api/notices" \
  "'デッキ登録できません' in d['notices'][0]['translations']['ja']['body']"

echo ""
echo "caching"
# These headers are the only thing standing between the site and its two metered
# resources — D1 reads breached the free tier once already (F-014) and Workers requests
# stop serving at 100k/day. v1's `checkRateLimit()` unconditionally returned true.
#
# Each path is paired with its expected max-age rather than sharing one constant: the
# artifacts deliberately differ from card data. `info.json` is one hour because its whole
# purpose is editing without a redeploy, and `filter-options` is a day because a reseed
# is the only thing that changes it.
while read -r path expected; do
  header="$(curl -sSD- -o /dev/null "${BASE}${path}" | tr -d '\r' | awk 'tolower($1) == "cache-control:" {print $2, $3}')"
  if [[ "$header" == "public, max-age=${expected}" ]]; then
    printf '  ✓ %-52s %s\n' "$path" "$header"
  else
    printf '  ✗ %-52s expected max-age=%s, got %s\n' "$path" "$expected" "${header:-none}"
    FAILURES=$((FAILURES + 1))
  fi
done <<'PATHS'
/api/cards/1 3600
/api/cards/filter?limit=1 3600
/api/cards/search?q=IRyS 3600
/api/status 3600
/api/info 3600
/api/filter-options?locale=en 86400
/api/notices 86400
PATHS

echo ""
echo ""
echo "card pages (ADR 0009 D7, D8 — the Worker's own HTML)"
# These read the *served bytes*, before any JavaScript runs — which is precisely what a
# crawler sees and what the generated shell alone does not contain. The shell carries no
# description, no canonical, no og:*, and a bare <html> with no lang.
check_html "card page renders"          200 "/tc/card/hSD01/hSD01-001_OSR" \
  '<html[^>]*lang="zh-TW"'
check_html "title names the card"       200 "/tc/card/hSD01/hSD01-001_OSR" \
  '<title>[^<]+ · hSD01-001 \| Hololive OCG Wiki</title>'
check_html "canonical is the card URL"  200 "/tc/card/hSD01/hSD01-001_OSR" \
  'rel="canonical" href="[^"]*/tc/card/hSD01/hSD01-001_OSR"'
check_html "og:image is the card art"   200 "/tc/card/hSD01/hSD01-001_OSR" \
  'property="og:image" content="[^"]*/hSD01/hSD01-001_OSR.webp"'
check_html "hreflang covers x-default"  200 "/tc/card/hSD01/hSD01-001_OSR" \
  'hreflang="x-default"'
check_html "carries JSON-LD"            200 "/tc/card/hSD01/hSD01-001_OSR" \
  'application/ld\+json'
# The soft-404 fix. Before this, an unmatched path served index.html with HTTP 200 —
# verified against production — so every mistyped card URL looked like a real page.
check_html "unknown card is a real 404" 404 "/tc/card/hSD01/NOPE"
# ...but the body is still the app, so the client renders a proper in-app screen. Status
# and body are independent; the status is the half a crawler reads.
check_html "404 still serves the app"   404 "/tc/card/hSD01/NOPE" 'id="__nuxt"'
check_html "an unknown locale is a 404" 404 "/xx/card/hSD01/hSD01-001_OSR"
# A wrong-case URL is a redirect, not a 404: the stored casing is canonical, and no two
# real keys differ only by case (verified over all 2,463).
check_redirect "wrong case 301s to the canonical form" 301 \
  "/tc/card/HSD01/hsd01-001_osr" "/tc/card/hSD01/hSD01-001_OSR"

if [[ "$FAILURES" -gt 0 ]]; then
  echo "✗ $FAILURES check(s) failed"
  exit 1
fi
echo "✓ all endpoint checks passed"
