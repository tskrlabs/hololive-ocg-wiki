#!/usr/bin/env bash
# What `nuxt generate` actually emitted (ADR 0009 D24).
#
# `make check-web` covers the pure modules and a few mounted components. This covers what
# they structurally cannot: the **build output**. Every check here reads a file that
# `nuxt generate` wrote, because the failure mode this exists for is a build that succeeds
# and ships the wrong thing — and that has happened here more than once:
#
#   - the prototype route would have deployed, because `nuxt generate` emits an HTML file
#     per route and `wrangler deploy` uploads the directory verbatim (#48)
#   - fonts were configured and never downloaded, because the module resolves only the
#     first family in a stack (#47)
#   - the sitemap listed 2 URLs per locale while 17,241 card pages existed (#33)
#
# None of those is visible to a unit test, and all three are one `grep` away from being
# caught here.
#
# It is a **separate target** from `make check` on purpose: `nuxt generate` alone is ~11s
# against `make check`'s ~46s total, and the pre-commit hook should stay fast (D24).
#
# No credentials and no network beyond the font CSS the build itself fetches.
set -euo pipefail

cd "$(dirname "$0")/.."

OUT=".output/public"
FAILURES=0

# check <name> <file> <grep -E pattern>
check() {
  local name="$1" file="$2" pattern="$3"
  if [[ ! -f "$OUT/$file" ]]; then
    printf '  ✗ %-54s %s is missing\n' "$name" "$file"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if ! grep -qE "$pattern" "$OUT/$file"; then
    printf '  ✗ %-54s %s does not match: %s\n' "$name" "$file" "$pattern"
    FAILURES=$((FAILURES + 1))
    return
  fi
  printf '  ✓ %-54s\n' "$name"
}

# check_absent <name> <file> <grep -E pattern that must NOT appear>
check_absent() {
  local name="$1" file="$2" pattern="$3"
  if [[ -f "$OUT/$file" ]] && grep -qE "$pattern" "$OUT/$file"; then
    printf '  ✗ %-54s %s still contains: %s\n' "$name" "$file" "$pattern"
    FAILURES=$((FAILURES + 1))
    return
  fi
  printf '  ✓ %-54s\n' "$name"
}

# check_missing <name> <path> — a file or directory that must not have been emitted
check_missing() {
  local name="$1" path="$2"
  if [[ -e "$OUT/$path" ]]; then
    printf '  ✗ %-54s %s was emitted and must not be\n' "$name" "$path"
    FAILURES=$((FAILURES + 1))
    return
  fi
  printf '  ✓ %-54s\n' "$name"
}

# check_count <name> <file> <grep -E pattern> <expected count>
check_count() {
  local name="$1" file="$2" pattern="$3" expect="$4"
  local actual
  if [[ ! -f "$OUT/$file" ]]; then
    printf '  ✗ %-54s %s is missing\n' "$name" "$file"
    FAILURES=$((FAILURES + 1))
    return
  fi
  actual="$(grep -cE "$pattern" "$OUT/$file" || true)"
  if [[ "$actual" != "$expect" ]]; then
    printf '  ✗ %-54s expected %s, got %s\n' "$name" "$expect" "$actual"
    FAILURES=$((FAILURES + 1))
    return
  fi
  printf '  ✓ %-54s %s\n' "$name" "$actual"
}

LOCALES=(tc ja en id ko th es)

# --------------------------------------------------------------------------------------
# 1. The pre-launch build — what ships today, and what must not.
# --------------------------------------------------------------------------------------
echo "→ generating the site (indexing off — the pre-launch build)"
npm run generate --silent >/dev/null 2>&1

echo ""
echo "the pre-launch build stays invisible (Phase 5, F-017)"
# Two switches flip at Phase 7 and the site is deliberately unindexable until they do.
# If either regressed, the new site would compete with v1 on the same 2,448 cards.
check "robots.txt disallows everything" "robots.txt" '^Disallow: /$'
check_missing "no sitemap index" "sitemap_index.xml"
check_missing "no per-locale sitemaps" "__sitemap__"
check "the shell carries noindex" "200.html" 'name="robots" content="noindex, nofollow"'

echo ""
echo "the prototype does not ship (#48, D24)"
# `nuxt generate` writes one HTML file per route and `wrangler deploy` uploads the
# directory verbatim, so a route left in the repo ships regardless of any runtime guard
# inside the component. A `.output` gitignore does not help — the deploy reads the built
# directory, not git.
#
# ⚠️ The path is **unprefixed**. `pages:extend` strips these from the route table before
# i18n expands it, so a shipped prototype appears at `/prototype-identity`, not at
# `/{locale}/prototype-identity`. Checking the prefixed paths passes whether or not the
# guard works — verified by disabling it: seven prefixed checks stayed green while the
# route sat in the build root.
check_missing "no prototype route in the build" "prototype-identity"
for locale in "${LOCALES[@]}"; do
  check_missing "  nor under /${locale}" "${locale}/prototype-identity"
done

echo ""
echo "every locale is routable"
for locale in "${LOCALES[@]}"; do
  check "/${locale} renders" "${locale}/index.html" 'id="__nuxt"'
done
# Unprefixed, unlike every other route. `nuxt generate` prerenders the *route table*,
# and `/status` is reached by a plain `NuxtLink to="/status"` from the overflow menu
# rather than through `localePath()` — so one file is emitted, not seven. It works
# because the SPA fallback serves it and the locale comes from the cookie; worth pinning,
# because the day it becomes `/{locale}/status` this line is what notices.
check "the status page renders" "status/index.html" 'id="__nuxt"'

echo ""
echo "the shell the Worker rewrites (ADR 0009 D7, D8)"
# The Worker injects title/description/canonical/og/hreflang/JSON-LD into this shell for
# card pages (asserted over served bytes by `apps/api/tests/smoke.sh`). What matters here
# is that the shell is the *unrewritten* one: if the build ever emitted its own card
# metadata, the two would fight and the result would be cloaking.
check "the SPA fallback exists" "200.html" '<div id="__nuxt">'
check "so does the 404 shell" "404.html" '<div id="__nuxt">'
check_absent "the shell claims no card canonical" "200.html" 'rel="canonical"[^>]*/card/'

echo ""
echo "fonts are actually downloaded (#47, D22)"
# `@nuxt/fonts` was in `modules` with no configuration and no `font-family` anywhere, so
# it had nothing to resolve and seven locales rendered in whatever the OS picked. The
# module also resolves only the *first* family in a stack, which is why the CJK faces
# need `global: true` — verified then in the browser, pinned here.
if [[ -d "$OUT/_fonts" ]]; then
  woff_count="$(find "$OUT/_fonts" -name '*.woff2' | wc -l | tr -d ' ')"
  # Inter alone is ~48 faces. The CJK families are sliced into ~105 `unicode-range`
  # pieces each, so a build that resolved only the first family in the stack — #47's
  # actual bug, verified in Chromium as `document.fonts` holding 48 Inter faces and
  # **zero** Noto — lands far below this.
  if [[ "$woff_count" -ge 200 ]]; then
    printf '  ✓ %-54s %s faces\n' "the CJK faces were downloaded too" "$woff_count"
  else
    printf '  ✗ %-54s only %s — the stack resolved to Inter alone?\n' \
      "the CJK faces were downloaded too" "$woff_count"
    FAILURES=$((FAILURES + 1))
  fi

  # ⚠️ `@nuxt/fonts` is pinned ≥0.14 for correctness: 0.11 fetched the Google CSS API
  # once per format, and the legacy ttf/woff pass returns each weight **unsliced**, as one
  # file with no `unicode-range`. Those faces are emitted last, so they win the cascade
  # and the browser downloads the whole font — measured at 4,340 KB in 3 files, one a
  # 4 MB Noto blob, against 638 KB sliced.
  legacy="$(find "$OUT/_fonts" \( -name '*.ttf' -o -name '*.woff' \) | wc -l | tr -d ' ')"
  if [[ "$legacy" == "0" ]]; then
    printf '  ✓ %-54s\n' "no unsliced legacy font formats"
  else
    printf '  ✗ %-54s %s legacy file(s) — they win the cascade\n' \
      "no unsliced legacy font formats" "$legacy"
    FAILURES=$((FAILURES + 1))
  fi
else
  printf '  ✗ %-54s _fonts/ is missing\n' "fonts were downloaded"
  FAILURES=$((FAILURES + 1))
fi

# --------------------------------------------------------------------------------------
# 2. The launched build — what Phase 7 will ship. Built second so the working tree is
#    left holding the pre-launch output, which is what `make preview` and `make check-api`
#    expect to find.
# --------------------------------------------------------------------------------------
echo ""
echo "→ regenerating with NUXT_PUBLIC_LAUNCHED=true (the Phase 7 build)"
NUXT_PUBLIC_LAUNCHED=true npm run generate --silent >/dev/null 2>&1

echo ""
echo "launched, the site is indexable and the cards are listed (#33 §5)"
check "robots.txt allows crawling" "robots.txt" '^Allow: /$|^Disallow:\s*$'
check_absent "the noindex tag is gone" "200.html" 'content="noindex'
check "the sitemap index exists" "sitemap_index.xml" '<sitemapindex'
check_count "it lists one sitemap per locale" "sitemap_index.xml" '<sitemap>' 7

# The number this whole phase exists for. 2,463 cards + `/` + `/status` per locale; the
# manifest is committed, so this is checkable without D1 or credentials.
CARD_URLS="$(python3 -c 'import json;print(len(json.load(open("../../packages/schema/data/card-urls.json"))))')"
EXPECTED=$((CARD_URLS + 2))
for locale in zh-TW ja-JP en-US id-ID ko-KR th-TH es-ES; do
  actual="$(grep -cE '<loc>' "$OUT/__sitemap__/${locale}.xml" 2>/dev/null || echo 0)"
  # zh-TW carries one extra: an unprefixed `/status` the module emits for the default
  # locale. Pre-existing, and not something this phase introduced.
  if [[ "$actual" == "$EXPECTED" || ( "$locale" == "zh-TW" && "$actual" == "$((EXPECTED + 1))" ) ]]; then
    printf '  ✓ %-54s %s URLs\n' "${locale}.xml lists every card" "$actual"
  else
    printf '  ✗ %-54s expected %s, got %s\n' "${locale}.xml lists every card" "$EXPECTED" "$actual"
    FAILURES=$((FAILURES + 1))
  fi
done

# ⚠️ The regression that would 6× the sitemap. `@nuxtjs/sitemap` inlines seven
# `xhtml:link` alternates per URL for any entry it recognises as i18n, which #33 §5
# measured at ~12.3 MB against ~1.9 MB. Absolute `loc` values opt out (see
# `apps/web/lib/cardUrls.ts`), and a future contributor "fixing" them to relative paths
# would look tidier and change nothing visible. This is what would catch it.
alt_count="$(grep -cE 'xhtml:link' "$OUT/__sitemap__/en-US.xml" || true)"
if [[ "$alt_count" -le 16 ]]; then
  printf '  ✓ %-54s %s (the two non-card pages)\n' "hreflang is not inlined per card" "$alt_count"
else
  printf '  ✗ %-54s %s — card URLs gained alternates\n' "hreflang is not inlined per card" "$alt_count"
  FAILURES=$((FAILURES + 1))
fi

# Casing is load-bearing: the Worker matches `image_key` exactly and 301s anything else,
# so a lowercased sitemap would point every card URL at a redirect (#33 §4).
check "card URLs keep their stored casing" "__sitemap__/en-US.xml" \
  '<loc>[^<]*/en/card/hSD01/hSD01-001_OSR</loc>'

echo ""
echo "→ restoring the pre-launch build"
npm run generate --silent >/dev/null 2>&1

echo ""
if [[ "$FAILURES" -gt 0 ]]; then
  echo "✗ $FAILURES site check(s) failed"
  exit 1
fi
echo "✓ all site checks passed"
