/**
 * Search input handling.
 *
 * These are the two failure modes the trigram index has, both verified against a real
 * D1 before being fixed here: a query under 3 characters silently matches nothing, and
 * raw user input is FTS5 *syntax* rather than text.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  escapeFtsPhrase,
  escapeLikePattern,
  searchSql,
  searchStrategy,
  TRIGRAM_MIN_LENGTH,
} from "../src/db/fts.ts";

test("every FTS5 metacharacter is neutralised into a phrase", () => {
  // Each of these throws `fts5: syntax error` when passed to MATCH unquoted. Confirmed
  // against a local D1 before this function existed.
  assert.equal(escapeFtsPhrase("a AND"), '"a AND"');
  assert.equal(escapeFtsPhrase("-x"), '"-x"');
  assert.equal(escapeFtsPhrase("fub*"), '"fub*"');
  assert.equal(escapeFtsPhrase("a OR b"), '"a OR b"');
  assert.equal(escapeFtsPhrase("NEAR(a b)"), '"NEAR(a b)"');
});

test("a double quote is doubled, not dropped", () => {
  // The dangerous one: a bare quote would otherwise close the phrase and let the rest
  // of the input be parsed as syntax.
  assert.equal(escapeFtsPhrase('"'), '""""');
  assert.equal(escapeFtsPhrase('say "hi"'), '"say ""hi"""');
});

test("LIKE wildcards in user input are escaped", () => {
  // Someone searching for "100%" means the literal text, not "anything after 100".
  assert.equal(escapeLikePattern("100%"), "100\\%");
  assert.equal(escapeLikePattern("a_b"), "a\\_b");
  // The escape character itself has to be escaped first, or `\%` would become `\\%`.
  assert.equal(escapeLikePattern("a\\b"), "a\\\\b");
});

test("queries shorter than a trigram take the LIKE path", () => {
  assert.equal(TRIGRAM_MIN_LENGTH, 3);
  // `そら` is the motivating case: 2 characters, 27 real matches, and trigram returns
  // zero rows rather than an error.
  assert.equal(searchStrategy("そら"), "like");
  assert.equal(searchStrategy("a"), "like");
  assert.equal(searchStrategy("フブキ"), "match");
  assert.equal(searchStrategy("IRyS"), "match");
});

test("the MATCH branch always binds a quoted phrase", () => {
  const built = searchSql("a AND", 50);
  assert.match(built.sql, /cards_fts MATCH \?/);
  assert.equal(built.params[0], '"a AND"');
  assert.equal(built.params[1], 50);
});

test("the LIKE branch declares its ESCAPE clause", () => {
  const built = searchSql("そら", 50);
  // Without ESCAPE the backslashes added by escapeLikePattern would be literal text.
  // Every occurrence needs its own clause, including the one in the ORDER BY.
  assert.ok(built.sql.includes("LIKE ?1 ESCAPE '\\'"), built.sql);
  assert.equal(built.params[0], "%そら%");
});

test("a short query searches Q&A too, with card matches first", () => {
  // Under 3 characters trigram cannot match, so this branch is the *only* thing a 1–2
  // character query has — `そら` is 2 characters and matches 27 cards. Q&A was part of
  // `text` until issue #67, so searching only `text` here would quietly shrink what a
  // short query can find while the MATCH branch still searched everything.
  const built = searchSql("そら");
  assert.match(built.sql, /text LIKE \?1 ESCAPE '\\' OR qa LIKE \?1 ESCAPE '\\'/);
  // Card text still wins: the ORDER BY sorts rows whose `text` matched to the front.
  assert.match(built.sql, /ORDER BY text LIKE \?1 ESCAPE '\\' DESC/);
  // One pattern, bound once — `?1` is reused rather than repeated. Verified against
  // D1's binding layer, which is stricter than node:sqlite about the mix.
  assert.equal(built.params.length, 1);
});

test("the MATCH branch ranks card text above rulings", () => {
  // `ORDER BY rank` weights every column 1.0, and Q&A is 88% of the indexed volume — so
  // a card merely *cited* in a ruling outranked the card itself (issue #67). The weights
  // mirror the models' `FullText`: a name is 3.0, a Q&A field 0.5.
  const built = searchSql("白上フブキ");
  assert.match(built.sql, /ORDER BY bm25\(cards_fts, 2\.0, 1\.0, 0\.1\)/);
  assert.doesNotMatch(built.sql, /ORDER BY rank/);
});

test("an omitted limit binds no LIMIT at all, on either branch", () => {
  // The filter path asks for every match, because its `total` is the count shown under
  // the search box — a capped id set makes that number report the cap rather than the
  // answer (issue #66). A limit that is merely large would still be a lie at 2,463
  // cards, so the parameter is absent rather than big.
  for (const query of ["フブキ", "そら"]) {
    const built = searchSql(query);
    assert.doesNotMatch(built.sql, /LIMIT/);
    assert.equal(built.params.length, 1);
  }
});

test("both branches select the rowid as the card id", () => {
  // An FTS5 column cannot be indexed for lookup, so the card id lives in the rowid
  // (ADR 0004). Both paths must agree on that or one of them returns unusable ids.
  for (const query of ["フブキ", "そら"]) {
    assert.match(searchSql(query, 10).sql, /SELECT rowid AS id FROM cards_fts/);
  }
});
