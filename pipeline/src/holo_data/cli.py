"""`holo-data` — the pipeline CLI.

Replaces v1's numbered scripts and `run-pipeline.sh`. The command order encodes D10's
gated update flow: everything before `publish` is local, free and reversible, and the
steps that cost money or touch production are explicit.

    holo-data scrape              official site -> raw HTML + images   (local, free)
    holo-data transform           re-transform the scrape, no refetch  (local, free)
    holo-data images              PNG -> WebP                          (local, free)
    holo-data translate-units     Poe API, content-addressed           ($$ — never implicit)
    holo-data build               merge + validate -> cards.json       (local, free)
    holo-data verify              diff against v1's data               (local, free)
    holo-data verify-images       coverage; --remote re-checks bytes   (local / ~2.4k reqs)
    holo-data publish             images + artifacts -> R2             (uploads)
    holo-data seed --dry          row counts + D1 write estimate       (reads only)
    holo-data seed --confirm      diff-based upsert into D1            (writes)

    holo-data glossary            proper-noun coverage, per locale     (local, free)
    holo-data corrections         verify hand-written fixes            (local, free)
    holo-data cache-status        migration progress, per locale       (local, free)
    holo-data backup-cache        snapshot the translation cache       (local / R2)
    holo-data normalise-cache     deterministic spelling fixes         (local, free)
    holo-data migrate-images      one-time v1 flat -> set-scoped tree

`translate` requires `--confirm` or refuses, and prints exactly what it would spend
under `--dry-run`. An agent-driven run that misfires must not be able to burn the Poe
budget or corrupt live data.

`publish` deliberately takes no `--confirm` — see its docstring. Uploading is cheap and
idempotent; what it checks instead is that the artifact is current and the image set is
complete, which are the failures that actually happen.

`seed` does take one, because it writes to production and the daily D1 write budget is
finite. Its gates are described on the command itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from holo_schema import SCHEMA_VERSION
from holo_schema.enums import SOURCE_LOCALE

from . import build as build_module
from . import corrections as corrections_module
from . import glossary as glossary_module
from . import images as images_module
from . import migrate_images as migrate_module
from . import paths, r2, transform, verify as verify_module
from . import publish as publish_module
from . import verify_images as verify_images_module
from .scrape import card_list, extract, fetch
from .translate import backup, batcher, mask_table, masking, poe, runner
from .translate import normalise as normalise_module
from .translate import units as units_module
from .translate.cache import TranslationCache
from .translate import cache_v2 as cache_v2_module
from .translate.cache_v2 import TranslationCacheV2

app = typer.Typer(
    help="hololive-ocg-wiki data pipeline.",
    no_args_is_help=True,
    add_completion=False,
)

load_dotenv(paths.PIPELINE_ROOT / ".env")


def _progress(label: str):
    def report(done: int, total: int, *rest) -> None:
        suffix = f" {rest[0]}" if rest else ""
        end = "\n" if done == total else "\r"
        print(f"  {label}: {done}/{total}{suffix}", end=end, flush=True)

    return report


# --- scrape ------------------------------------------------------------------

@app.command()
def scrape(
    skip_ids: bool = typer.Option(
        False, "--skip-ids", help="reuse the existing card id list"
    ),
    skip_images: bool = typer.Option(
        False, "--skip-images", help="fetch card data but do not download images"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="only fetch the first N cards (for testing)"
    ),
) -> None:
    """Scrape the official site: card ids, per-card HTML, and images."""
    paths.ensure_dirs()

    if skip_ids:
        card_ids = card_list.load_card_ids()
        typer.echo(f"→ reusing {len(card_ids)} card ids")
    else:
        typer.echo("→ fetching card id list")
        card_ids = card_list.fetch_card_ids(on_progress=_progress("pages"))
        card_list.save_card_ids(card_ids)
        typer.echo(f"  {len(card_ids)} card ids")

    if not card_ids:
        typer.echo("no card ids — aborting", err=True)
        raise typer.Exit(1)

    if limit:
        card_ids = card_ids[:limit]
        typer.echo(f"→ limited to {len(card_ids)} cards")

    typer.echo("→ fetching card pages")
    raw = fetch.fetch_cards(
        card_ids, download_images=not skip_images, on_progress=_progress("cards")
    )
    fetch.save_raw(raw)

    typer.echo("→ extracting structured data")
    structured = extract.extract_cards(raw, on_progress=_progress("cards"))
    extract.save_structured(structured)

    typer.echo("→ transforming to contract shape")
    cards, unmapped = transform.transform_cards(
        structured, on_progress=_progress("cards")
    )
    transform.save_i18n(cards)

    typer.echo(f"✓ scraped {len(cards)} cards")
    _report_unmapped(unmapped)


def _report_unmapped(report: transform.UnmappedReport) -> None:
    """Print the source values no mapping table covered.

    Printed here because this is the only place they exist. The mapping tables replace
    an unrecognised value with `unknown` and discard what the site printed, so `build`'s
    own error can name the values we accept and never the one that caused it — an
    operator got "Input should be 'debut', 'first', 'second' or 'spot'", a card id, and
    no way to learn what to add to `mappings.py` short of opening the card by hand.

    Not an error: `transform` succeeded, and whether an unmapped value stops anything is
    `build`'s call. This says what happened and what to do about it (issue #19).
    """
    if report.is_empty:
        return

    typer.echo("")
    typer.echo(
        f"⚠ {report.card_count} card(s) carry a value no mapping covers:", err=True
    )
    for field_name, source, card_ids in report.rows():
        ids = ", ".join(card_ids[:5])
        more = f" (+{len(card_ids) - 5} more)" if len(card_ids) > 5 else ""
        typer.echo(f"    {field_name:22s} {source}", err=True)
        typer.echo(f"    {'':22s}   {len(card_ids)} card(s): {ids}{more}", err=True)

    typer.echo("", err=True)
    typer.echo(
        "  Add the missing entries to `mappings.py`. Until then `build` fails on these "
        "cards — which is deliberate; a card the site prints and we cannot classify "
        "should not ship unannounced (issue #19).",
        err=True,
    )


# --- transform ---------------------------------------------------------------

@app.command("transform")
def transform_() -> None:
    """Re-transform the scraped data into contract shape, without re-scraping.

    `scrape` ends by running this, so the only way to repair `cards_i18n.json` used to
    be re-fetching 2,464 pages from a small operator's site — a bad reason to hit
    someone's server when the scrape artifact on disk is already correct.

    That is not hypothetical: when the contract dropped `cost_count`, the transformer
    stopped emitting it but `cards_i18n.json` had been written before the change, so
    `build` failed on 1,991 arts against data that was fine. This command is the repair
    (issue #16).

    Ungated, like `build`: local, free, and reproducible from `cards_structured.json`.
    """
    structured = extract.load_structured()
    if not structured:
        typer.echo(
            f"no scraped data at {paths.structured_file()} — run `holo-data scrape` first",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"→ transforming {len(structured)} entries to contract shape")
    cards, unmapped = transform.transform_cards(
        structured, on_progress=_progress("cards")
    )
    transform.save_i18n(cards)

    size = paths.i18n_file().stat().st_size
    typer.echo(
        f"✓ wrote {paths.i18n_file()} — {len(cards)} entries, {size / 1024 / 1024:.1f} MB"
    )
    _report_unmapped(unmapped)


# --- images ------------------------------------------------------------------

@app.command()
def images(
    quality: int = typer.Option(
        images_module.DEFAULT_QUALITY, "--quality", min=1, max=100
    ),
    force: bool = typer.Option(False, "--force", help="reconvert everything"),
) -> None:
    """Convert downloaded PNGs to WebP (D9 — only WebP is ever uploaded)."""
    typer.echo(f"→ converting PNG → WebP at quality {quality}")
    result = images_module.convert_all(
        quality=quality, force=force, on_progress=_progress("images")
    )

    typer.echo(f"  converted {result.converted}, skipped {result.skipped}")
    if result.failed:
        typer.echo(f"  {len(result.failed)} failed:", err=True)
        for name, error in result.failed[:10]:
            typer.echo(f"    {name}: {error}", err=True)

    png_size = images_module.directory_size(paths.PNG_DIR, "*.png")
    webp_size = images_module.directory_size(paths.WEBP_DIR, "*.webp")
    if png_size:
        typer.echo(
            f"  PNG {png_size / 1024 / 1024:.0f} MB → "
            f"WebP {webp_size / 1024 / 1024:.0f} MB "
            f"({100 - webp_size / png_size * 100:.0f}% smaller)"
        )

    raise typer.Exit(1 if result.failed else 0)


# --- translate ---------------------------------------------------------------

@app.command("translate-units")
def translate_units(
    locale: Optional[str] = typer.Option(
        None, "--locale", help="translate one locale only"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="report what would be sent, spend nothing"
    ),
    confirm: bool = typer.Option(
        False, "--confirm", help="required to actually call the Poe API"
    ),
    include_qa: bool = typer.Option(
        False, "--include-qa", help="also translate Q&A (62% of the corpus)"
    ),
    model: str = typer.Option(poe.DEFAULT_MODEL, "--model"),
) -> None:
    """Translate stale units into the content-addressed cache. Costs money — D10.

    The v2 path: distinct strings batched by kind, names and tags masked out, one
    translation per source string rather than one per card printing it.

    **Q&A is excluded by default.** It is 596 units but 62% of the corpus by character
    count, its existing translations were migrated as `legacy`, and re-doing it is a
    separate decision from re-doing everything else (#23 D6).

    Reads the **scrape** output, not `cards.json`, and this is load-bearing: `build`
    refuses to write a card whose locales are missing, so on a new card set the built
    artifact is the *previous* set — the one place the new strings are guaranteed absent.
    Sourcing units from the build made the v2 path unable to onboard a new set at all
    (found updating 2,463 → 2,559: 132 new units were invisible to it while `build`
    failed on the 19 cards needing exactly those translations). `translate` has always
    read `load_i18n()`; only the units path diverged. Units are collected from
    `translations.ja`, which `build` passes through unchanged — verified over the 2,463
    shared cards at the time of the fix.
    """
    cards = transform.load_i18n()
    if not cards:
        typer.echo("no cards found — run `holo-data scrape` first", err=True)
        raise typer.Exit(1)

    all_units = units_module.collect(cards)
    work = [
        unit
        for unit in all_units.values()
        if include_qa or unit.kind != units_module.QA_KIND
    ]

    names = glossary_module.Glossary.load("names")
    tags = glossary_module.Glossary.load("tags")
    table = mask_table.combined_table(names, tags)
    restorer = mask_table.Restorer(names, tags)

    cache = TranslationCacheV2.load()
    locales = [locale] if locale else poe.target_locales()

    typer.echo(f"→ {len(work)} translatable units, {len(locales)} locale(s)")
    typer.echo(f"  mask table: {len(table)} entries")

    plans = {}
    total_calls = total_units = 0
    for loc in locales:
        stale = cache.stale(loc, work)
        batches = batcher.build_batches(stale, loc, table)
        plans[loc] = (stale, batches)
        total_calls += len(batches)
        total_units += len(stale)
        fresh = len(work) - len(stale)
        typer.echo(
            f"  {loc}: {len(stale)} stale units in {len(batches)} call(s), "
            f"{fresh} already current"
        )

    if total_units == 0:
        typer.echo("✓ everything is up to date")
        return

    typer.echo("")
    typer.echo(f"Would send {total_calls} call(s) covering {total_units} unit(s).")

    if dry_run or not confirm:
        if not confirm:
            typer.echo("This costs money. Re-run with --confirm to proceed.")
        raise typer.Exit(0 if dry_run else 1)

    import asyncio

    reports = []
    for loc in locales:
        stale, batches = plans[loc]
        if not stale:
            continue
        typer.echo(f"→ translating {loc}")
        report = asyncio.run(
            runner.run_locale(
                work, cache, table, restorer, loc,
                model=model, on_progress=_progress(loc),
            )
        )
        # Saved per locale, not at the end: a run is 34 calls and losing all of them to
        # a failure on the last one is the kind of thing that happens once and is never
        # forgiven.
        cache.save()
        reports.append(report)
        for line in report.lines():
            typer.echo(f"  {line}")

    typer.echo("")
    total_tokens = sum(r.total_tokens for r in reports)
    translated = sum(r.units_translated for r in reports)
    typer.echo(f"✓ {translated} units translated, {total_tokens:,} tokens")
    for report in reports:
        status = cache.status(report.locale, work)
        typer.echo(f"  {status.describe()}")


@app.command()
def translate(
    locale: Optional[str] = typer.Option(
        None, "--locale", help="translate one locale only"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="report what would be sent, spend nothing"
    ),
    confirm: bool = typer.Option(
        False, "--confirm", help="required to actually call the Poe API"
    ),
    model: str = typer.Option(poe.DEFAULT_MODEL, "--model"),
) -> None:
    """Translate stale fields via the Poe API. Costs money — gated per D10.

    Only cards with at least one stale field are sent. The whole card goes in the prompt
    for context, but only stale fields are read out of the reply — which is what keeps
    manual corrections from being overwritten.
    """
    cards = transform.load_i18n()
    if not cards:
        typer.echo("no cards found — run `holo-data scrape` first", err=True)
        raise typer.Exit(1)

    cache = TranslationCache.load()
    locales = [locale] if locale else poe.target_locales()

    plans = [poe.plan_translation(cards, cache, loc) for loc in locales]
    total_cards = sum(plan.card_count for plan in plans)
    total_fields = sum(plan.field_count for plan in plans)

    typer.echo(f"→ {len(cards)} cards, {len(locales)} locale(s)")
    for plan in plans:
        fresh = len(cards) - plan.card_count
        typer.echo(
            f"  {plan.locale}: {plan.card_count} cards to send "
            f"({plan.field_count} stale fields), {fresh} already current"
        )

    manual = cache.manual_count()
    if manual:
        typer.echo(f"  {manual} manual correction(s) preserved")

    if total_cards == 0:
        typer.echo("✓ everything is up to date — nothing to translate")
        return

    if dry_run or not confirm:
        typer.echo("")
        typer.echo(f"Would send {total_cards} card requests ({total_fields} fields).")
        if not confirm:
            typer.echo("This costs money. Re-run with --confirm to proceed.")
        raise typer.Exit(0 if dry_run else 1)

    import asyncio

    for plan in plans:
        if plan.card_count == 0:
            continue
        typer.echo(f"→ translating {plan.locale}")
        translated, updated = asyncio.run(
            poe.run_translation(
                cards, cache, plan.locale, plan, model=model,
                on_progress=_progress(plan.locale),
            )
        )
        cache.save()
        typer.echo(f"  {translated} cards, {updated} fields updated")

    typer.echo("✓ translation complete")


# --- build -------------------------------------------------------------------

@app.command()
def build(
    allow_unknown_enums: bool = typer.Option(
        False,
        "--allow-unknown-enums",
        help="build without the cards carrying unrecognised enum values "
        "(publish and seed then refuse the artifact)",
    ),
) -> None:
    """Merge translations and validate against the contract, producing cards.json."""
    cards = transform.load_i18n()
    if not cards:
        typer.echo("no cards found — run `holo-data scrape` first", err=True)
        raise typer.Exit(1)

    cache = TranslationCache.load()
    cache_v2 = TranslationCacheV2.load()
    locales = poe.target_locales()

    typer.echo(f"→ building {len(cards)} entries across {len(locales) + 1} locales")
    if cache_v2.entries:
        typer.echo(
            f"  content-addressed cache: {cache_v2.count()} entries "
            f"({cache_v2.count(source='legacy')} legacy, "
            f"{cache_v2.count(source='manual')} manual); v1 fills any gap"
        )
    collection, notices, report = build_module.build(
        cards, cache, locales,
        allow_unknown_enums=allow_unknown_enums, cache_v2=cache_v2,
    )
    if report.notice_count:
        typer.echo(
            f"  {report.notice_count} rules notice(s) split out — not cards, "
            f"published as an R2 artifact (holo_schema.notice)"
        )

    typer.echo("  translation coverage:")
    for locale, count in report.translation_coverage.items():
        pct = 100 * count / report.total if report.total else 0
        typer.echo(f"    {locale}: {count}/{report.total} ({pct:.0f}%)")

    if report.enum_violations:
        typer.echo("")
        label = "dropped for" if allow_unknown_enums else "unrecognised"
        typer.echo(f"  {label} enum values:", err=not allow_unknown_enums)
        for message, ids in sorted(report.enum_violations.items()):
            typer.echo(f"    {len(ids):5d}  {message}")
            typer.echo(f"           e.g. card {', '.join(ids[:5])}")
        if not allow_unknown_enums:
            typer.echo("", err=True)
            typer.echo(
                "  Add the missing entry to `mappings.py` — `holo-data transform` "
                "names the source value the site printed. `--allow-unknown-enums` "
                "builds without these cards, but `publish` and `seed` then refuse "
                "the artifact.",
                err=True,
            )

    if report.errors:
        typer.echo("")
        typer.echo(f"  {report.failed} card(s) failed validation:", err=True)
        for message, ids in sorted(report.errors.items()):
            typer.echo(f"    {len(ids):5d}  {message}", err=True)
            typer.echo(f"           e.g. card {', '.join(ids[:5])}", err=True)

    if collection is None:
        typer.echo("")
        typer.echo("✗ build failed — nothing written", err=True)
        raise typer.Exit(1)

    size = build_module.save(collection)
    typer.echo("")
    dropped_note = f", {len(collection.dropped)} dropped" if collection.dropped else ""
    typer.echo(
        f"✓ wrote {paths.cards_json()} — {report.valid} cards{dropped_note}, "
        f"{size / 1024 / 1024:.1f} MB"
    )

    # Said after the ✓ on purpose: the build succeeded, and the operator needs to know
    # the artifact is not shippable before they reach for `publish` and read a refusal
    # they have no context for.
    if collection.dropped:
        typer.echo("")
        typer.echo(
            f"⚠ {len(collection.dropped)} card(s) are missing from this artifact. "
            "`publish` and `seed` will refuse it — add the mapping and rebuild.",
            err=True,
        )

    notices_size = build_module.save_notices(notices)
    typer.echo(
        f"✓ wrote {paths.notices_json()} — {len(notices.notices)} notice(s), "
        f"{notices_size / 1024:.1f} KB"
    )

    # The dropdown values for /api/filter-options. Built here, beside the data they
    # summarise, so they can never describe a different cards.json than the one shipped.
    options = build_module.save_filter_options(collection, ["ja", *locales])
    typer.echo(
        f"✓ wrote {len(options)} filter-options files — "
        f"{sum(options.values()) / 1024:.0f} KB total"
    )

    # The sitemap's URL list (#33 §5). Written here for the same reason as the filter
    # options — beside the data it describes — but into `packages/schema/`, because it is
    # **committed**: the site's build has no D1 and no credentials, so this is the only
    # way `nuxt generate` can know which cards exist.
    urls_size = build_module.save_card_urls(collection)
    typer.echo(
        f"✓ wrote {paths.card_urls_json()} — {report.valid} card URLs, "
        f"{urls_size / 1024:.0f} KB"
    )
    typer.echo("  commit it — `make check` fails if it is stale")


# --- verify ------------------------------------------------------------------

@app.command()
def verify(
    baseline: Path = typer.Option(
        Path("/Users/chingli/lichingchester/projects/hololive-ocg-wiki/data/cards.json"),
        "--baseline",
        help="v1's cards.json to compare against",
    ),
) -> None:
    """Diff the current build against v1's published data.

    Expected differences (snake_case keys, stripped `_source_hash`, `image_key` instead
    of `image_path`) are normalised away, so what it reports is unexpected drift only.
    """
    collection = build_module.load()
    if collection is None:
        typer.echo("no build found — run `holo-data build` first", err=True)
        raise typer.Exit(1)

    if not baseline.exists():
        typer.echo(f"baseline not found: {baseline}", err=True)
        typer.echo("Pass --baseline, or skip verification.", err=True)
        raise typer.Exit(1)

    typer.echo(f"→ comparing against {baseline}")
    built = collection.model_dump(mode="json", exclude_none=True)
    report = verify_module.compare(baseline, built)

    typer.echo(f"  baseline {report.baseline_count} cards, build {report.build_count}")
    if report.missing_ids:
        typer.echo(
            f"  ✗ {len(report.missing_ids)} card(s) in baseline but not in build: "
            f"{', '.join(report.missing_ids[:10])}",
            err=True,
        )
    if report.extra_ids:
        typer.echo(f"  + {len(report.extra_ids)} new card(s) since the baseline")

    if report.field_diffs:
        typer.echo("  base field differences:")
        for key, ids in sorted(report.field_diffs.items(), key=lambda kv: -len(kv[1])):
            typer.echo(f"    {len(ids):5d}  {key}   e.g. card {', '.join(ids[:3])}")

    if report.locale_diffs:
        typer.echo("  translation differences:")
        for locale, counts in sorted(report.locale_diffs.items()):
            summary = ", ".join(f"{key}={n}" for key, n in counts.most_common(5))
            typer.echo(f"    {locale}: {summary}")

    if report.is_clean:
        typer.echo("✓ build reproduces the baseline data")
    else:
        typer.echo("")
        typer.echo("Differences above are not automatically failures — review them.")


# --- publish -----------------------------------------------------------------

@app.command()
def publish(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="report what would upload, change nothing"
    ),
    force: bool = typer.Option(
        False, "--force", help="re-upload everything, ignoring the diff"
    ),
    images_only: bool = typer.Option(False, "--images-only"),
    artifacts_only: bool = typer.Option(False, "--artifacts-only"),
) -> None:
    """Upload images and artifacts to R2.

    No `--confirm`: image keys are immutable, the diff makes a re-run a no-op, and
    ~3,000 uploads is 0.3% of the monthly allowance. The guards that matter are a
    staleness check on `cards.json` and a coverage check on the images — both facts an
    agent cannot wave away with a flag (D10).
    """
    try:
        config = r2.load_config()
    except r2.R2Error as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1)

    staleness = publish_module.check_staleness()
    if staleness.is_stale:
        typer.echo("✗ build/cards.json is older than its inputs:", err=True)
        for path in staleness.newer_inputs:
            typer.echo(f"    {path}", err=True)
        typer.echo("", err=True)
        typer.echo("Run `holo-data build` first.", err=True)
        raise typer.Exit(1)

    typer.echo(f"→ {config.images_bucket} + {config.artifacts_bucket}")

    try:
        s3 = r2.client(config)
        typer.echo("→ listing what is already published")
        plan = publish_module.build_plan(s3, config, force=force)
    except r2.R2Error as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1)

    # Coverage: a card with no image renders as a broken tile. Hard failure.
    if plan.missing_images:
        typer.echo("", err=True)
        typer.echo(
            f"✗ {len(plan.missing_images)} card(s) have no local WebP:", err=True
        )
        for key in plan.missing_images[:10]:
            typer.echo(f"    {key}", err=True)
        if len(plan.missing_images) > 10:
            typer.echo(f"    … and {len(plan.missing_images) - 10} more", err=True)
        typer.echo("", err=True)
        typer.echo("Run `holo-data images` (or `migrate-images`) first.", err=True)
        raise typer.Exit(1)

    if plan.orphan_images:
        typer.echo(
            f"  {len(plan.orphan_images)} local WebP(s) match no card — not uploaded"
        )

    typer.echo(
        f"  images:    {len(plan.image_uploads):5d} to upload, "
        f"{plan.images_unchanged} unchanged"
    )
    typer.echo(
        f"  artifacts: {len(plan.artifact_uploads):5d} to upload, "
        f"{plan.artifacts_unchanged} unchanged"
    )

    if plan.total_uploads == 0:
        typer.echo("✓ everything is already published — nothing to do")
        return

    typer.echo(f"  {plan.upload_bytes / 1024 / 1024:.1f} MB total")

    if dry_run:
        typer.echo("")
        by_reason: dict[str, int] = {}
        for item in plan.image_uploads + plan.artifact_uploads:
            by_reason[item.reason] = by_reason.get(item.reason, 0) + 1
        typer.echo("Would upload: " + ", ".join(f"{n} {r}" for r, n in sorted(by_reason.items())))
        for item in (plan.image_uploads + plan.artifact_uploads)[:15]:
            typer.echo(f"    {item.reason:8s} {item.key}")
        if plan.total_uploads > 15:
            typer.echo(f"    … and {plan.total_uploads - 15} more")
        return

    failures: list[tuple[str, str]] = []

    if not artifacts_only and plan.image_uploads:
        typer.echo("→ uploading images")
        report = _progress("images")
        for index, item in enumerate(plan.image_uploads):
            try:
                r2.upload(s3, config.images_bucket, item, r2.IMAGE_CACHE_CONTROL)
            except Exception as exc:  # noqa: BLE001
                failures.append((item.key, str(exc)))
            report(index + 1, len(plan.image_uploads), item.key)

    if not images_only and plan.artifact_uploads:
        typer.echo("→ uploading artifacts")
        for item in plan.artifact_uploads:
            try:
                r2.upload(s3, config.artifacts_bucket, item, r2.ARTIFACT_CACHE_CONTROL)
                typer.echo(f"  {item.key}")
            except Exception as exc:  # noqa: BLE001
                failures.append((item.key, str(exc)))

    if failures:
        typer.echo("")
        typer.echo(f"✗ {len(failures)} upload(s) failed:", err=True)
        for key, error in failures[:10]:
            typer.echo(f"    {key}: {error}", err=True)
        raise typer.Exit(1)

    typer.echo("")
    typer.echo(f"✓ published {plan.total_uploads} object(s)")


# --- verify-images -----------------------------------------------------------

@app.command("verify-images")
def verify_images(
    remote: bool = typer.Option(
        False,
        "--remote",
        help="re-fetch every source image and compare bytes (~2,450 requests)",
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="check only the first N"),
) -> None:
    """Check the image set: coverage always, provenance with `--remote`.

    Coverage is a set difference and free. `--remote` re-downloads every card's
    `source_image_url` and compares bytes — that is what catches an image being the
    *wrong card's art*, which is how F-006 went unnoticed for a year. Expensive by
    nature, so it never runs implicitly.
    """
    try:
        coverage = verify_images_module.check_coverage()
    except FileNotFoundError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"→ {coverage.total_cards} cards")
    typer.echo(
        f"  missing PNG:  {len(coverage.missing_png)}\n"
        f"  missing WebP: {len(coverage.missing_webp)}\n"
        f"  orphan WebP:  {len(coverage.orphan_webp)}"
    )

    for label, keys in (
        ("missing PNG", coverage.missing_png),
        ("missing WebP", coverage.missing_webp),
    ):
        if keys:
            typer.echo(f"  {label}:", err=True)
            for key in keys[:10]:
                typer.echo(f"    {key}", err=True)
            if len(keys) > 10:
                typer.echo(f"    … and {len(keys) - 10} more", err=True)

    if not remote:
        if coverage.is_clean:
            typer.echo("✓ every card has both a PNG and a WebP")
            typer.echo("  (pass --remote to also verify the bytes against the source)")
        raise typer.Exit(0 if coverage.is_clean else 1)

    typer.echo("")
    typer.echo("→ re-fetching source images to compare bytes (this is the slow one)")
    provenance = verify_images_module.check_provenance(
        limit=limit, on_progress=_progress("checked")
    )

    typer.echo(f"  {provenance.matched}/{provenance.checked} match their source")

    if provenance.mismatched:
        typer.echo("")
        typer.echo(f"  ✗ {len(provenance.mismatched)} differ from source:", err=True)
        for key, problem in sorted(provenance.mismatched.items())[:20]:
            typer.echo(f"    {key}: {problem}", err=True)

    if provenance.errors:
        typer.echo(f"  {len(provenance.errors)} could not be fetched:", err=True)
        for key, error in sorted(provenance.errors.items())[:10]:
            typer.echo(f"    {key}: {error}", err=True)

    if provenance.is_clean and coverage.is_clean:
        typer.echo("")
        typer.echo("✓ every local image matches the bytes the official site serves")
        return
    raise typer.Exit(1)


# --- migrate-images ----------------------------------------------------------

@app.command("migrate-images")
def migrate_images(
    source: Path = typer.Option(
        migrate_module.V1_IMAGE_DIR, "--source", help="v1's flat image directory"
    ),
    mapping: Path = typer.Option(
        migrate_module.V1_MAPPING, "--mapping", help="v1 artifact carrying imageUrl"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="report the plan only"),
) -> None:
    """One-time: copy v1's flat images into the set-scoped tree.

    Copies rather than re-scrapes — ~2,450 local file copies instead of ~2,450 requests
    to a small operator's site. Files whose name is claimed by two different cards
    (F-006) are re-fetched instead of copied, because which print the flat file holds is
    not recoverable.
    """
    if not mapping.exists():
        typer.echo(f"✗ mapping not found: {mapping}", err=True)
        raise typer.Exit(1)

    typer.echo(f"→ reading image keys from {mapping.name}")
    key_map = migrate_module.load_key_map(mapping)
    typer.echo(f"  {len(key_map)} image keys")

    plan = migrate_module.plan(source, key_map)

    typer.echo(f"→ from {source}")
    typer.echo(f"  copy:   {len(plan.copies)}")
    typer.echo(f"  fetch:  {len(plan.fetches)}")
    if plan.contested:
        typer.echo(
            f"  {len(plan.contested)} filename(s) claimed by two cards — "
            f"re-fetching both prints (F-006):"
        )
        for filename, keys in sorted(plan.contested.items()):
            typer.echo(f"    {filename} → {', '.join(keys)}")
    if plan.orphan_files:
        typer.echo(f"  {len(plan.orphan_files)} file(s) on disk match no card")
        for name in plan.orphan_files[:5]:
            typer.echo(f"    {name}")
        if len(plan.orphan_files) > 5:
            typer.echo(f"    … and {len(plan.orphan_files) - 5} more")
    if plan.unresolved:
        typer.echo(f"  ✗ {len(plan.unresolved)} key(s) have no source at all", err=True)

    if dry_run:
        typer.echo("")
        typer.echo(f"Would place {plan.total} image(s). Nothing written.")
        return

    typer.echo("")
    typer.echo("→ migrating")
    copied, fetched, failures = migrate_module.apply(
        plan, on_progress=_progress("images")
    )

    typer.echo(f"  copied {copied}, fetched {fetched}")
    if failures:
        typer.echo(f"  ✗ {len(failures)} failed:", err=True)
        for key, error in failures[:10]:
            typer.echo(f"    {key}: {error}", err=True)
        raise typer.Exit(1)

    typer.echo("")
    typer.echo("✓ images are in the set-scoped tree")
    typer.echo("  next: `holo-data images` to convert, then `verify-images --remote`")


# --- seed --------------------------------------------------------------------


@app.command()
def seed(
    dry: bool = typer.Option(
        False, "--dry", help="report row counts and the D1 write estimate, write nothing"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="required to write to D1"),
    full: bool = typer.Option(
        False, "--full", help="rewrite every card, ignoring the diff"
    ),
    prune: bool = typer.Option(
        False, "--prune", help="delete cards that are in D1 but not in the build"
    ),
) -> None:
    """Seed D1 from the built card set, writing only what changed.

    The diff baseline is D1 itself — every row carries a content hash, so an
    interrupted run resumes correctly and a second run writes nothing.

    Gates (D10). Three of them are facts rather than ceremony, and no flag gets past
    them: a stale `cards.json`, a card set that collapsed since the last seed, and a
    write estimate that would not fit in today's remaining D1 budget. Deleting is
    separately gated behind `--prune` because it is the one irreversible thing here.
    """
    from . import d1, seed as seed_module

    try:
        config = d1.load_config()
    except d1.D1Error as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1)

    # Same staleness check `publish` uses: seeding a stale artifact is the realistic
    # failure, and it is one --confirm would not catch because the person typing it
    # also believes the build is current.
    staleness = publish_module.check_staleness()
    if staleness.is_stale:
        typer.echo("✗ build/cards.json is older than its inputs:", err=True)
        for path in staleness.newer_inputs:
            typer.echo(f"    {path}", err=True)
        typer.echo("", err=True)
        typer.echo("Run `holo-data build` first.", err=True)
        raise typer.Exit(1)

    collection = build_module.load()
    if collection is None:
        typer.echo("no build found — run `holo-data build` first", err=True)
        raise typer.Exit(1)

    typer.echo(f"→ {config.database_name} ({len(collection.cards)} cards in the build)")

    http = d1.client(config)
    try:
        if not d1.table_exists(http, config, "cards"):
            typer.echo("✗ the `cards` table does not exist in this database.", err=True)
            typer.echo("", err=True)
            typer.echo("Apply the schema first:", err=True)
            typer.echo(
                f"    npx wrangler d1 execute {config.database_name} --remote "
                "--file=packages/schema/sql/schema.sql",
                err=True,
            )
            raise typer.Exit(1)

        try:
            seed_module.assert_fts_has_qa_column(http, config)
        except seed_module.MissingQaColumn:
            typer.echo("", err=True)
            typer.echo("✗ D1's `cards_fts` is missing the `qa` column", err=True)
            typer.echo(
                "  Migration 0004 has not been applied. Apply it from apps/api/ with:\n"
                "    npx wrangler d1 execute hololive-ocg-wiki-db --remote \\\n"
                "        --file=../../packages/schema/sql/migrations/0004-fts-qa-column.sql\n"
                "  ⚠️ That migration leaves the index EMPTY — FTS5 rejects ALTER, so it "
                "drops and recreates the table. Search is dead until this seed runs, so "
                "run it straight after, with --full.",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo("→ reading the diff baseline from D1")
        try:
            stored = seed_module.read_stored_hashes(http, config)
        except seed_module.MissingSourceHashColumn:
            # Printed in a refusal's shape, but raised before a plan exists — the column
            # this needs is the one the baseline query selects (ADR 0009 D26).
            typer.echo("", err=True)
            typer.echo("✗ D1 is missing the `source_hash` column", err=True)
            typer.echo(
                "  Migration 0003 has not been applied. Apply it from apps/api/ with:\n"
                "    npx wrangler d1 execute hololive-ocg-wiki-db --remote \\\n"
                "        --file=../../packages/schema/sql/migrations/0003-source-hash.sql\n"
                "  Refusing here rather than partway through: a D1 batch is atomic but a "
                "run is not, so seeding would commit some batches before failing.",
                err=True,
            )
            raise typer.Exit(1)
        rows = [seed_module.to_row(card) for card in collection.cards]
        plan = seed_module.diff(rows, stored)

        if full:
            # --full is its own path, not a bigger diff: it rebuilds the FTS index with
            # one `rebuild` statement instead of 2,448 delete/insert pairs.
            #
            # The report-only sets are *not* overwritten: --full changes what we write,
            # not what the official site did, and reporting 2,463 source changes because
            # the operator passed a flag is the falsehood D26 exists to remove. The
            # backfill list is cleared because every row is about to be rewritten anyway.
            plan.new, plan.changed, plan.qa_updated = rows, [], []
            plan.unchanged = 0
            plan.backfill = []

        typer.echo(f"  stored {plan.stored_count}, incoming {plan.incoming_count}")
        typer.echo(f"  new            {len(plan.new):5d}")
        typer.echo(f"  changed        {len(plan.changed):5d}")
        typer.echo(f"  qa only        {len(plan.qa_updated):5d}")
        typer.echo(f"  unchanged      {plan.unchanged:5d}")
        if plan.backfill:
            typer.echo(
                f"  source_hash backfill: {len(plan.backfill)} "
                "(one UPDATE each — rows already current, but written before 0003)"
            )
        if plan.missing_ids:
            typer.echo(
                f"  in D1, not in the build: {len(plan.missing_ids)}"
                + ("  → will be deleted (--prune)" if prune else "  → left alone")
            )

        # What the *source* did, which is what /status reports (D26). Kept apart from the
        # four lines above on purpose: those describe our database, these describe the
        # official card list, and conflating them is the bug this whole decision fixes.
        typer.echo("")
        typer.echo("  the official card list, since the last seed:")
        typer.echo(f"    added        {len(plan.source_added):5d}")
        typer.echo(f"    edited       {len(plan.source_changed):5d}")
        typer.echo(f"    FAQ changed  {len(plan.faq_changed):5d}")
        if plan.backfill and not plan.source_changed:
            typer.echo(
                "    (no baseline yet for some rows — this run records one, "
                "so the next is comparable)"
            )

        writes_used = d1.writes_used_today(config, http)
        estimated = plan.estimated_writes
        if prune:
            estimated += len(plan.missing_ids) * (2 + len(seed_module.JUNCTIONS))

        typer.echo("")
        if writes_used is None:
            typer.echo(
                f"  estimated writes {estimated:,} "
                f"({100 * estimated / d1.DAILY_WRITE_LIMIT:.1f}% of the daily limit)"
            )
            typer.echo(
                "  could not read today's usage — the token may lack Account "
                "Analytics Read (docs/infra.md)"
            )
        else:
            remaining = d1.DAILY_WRITE_LIMIT - writes_used
            typer.echo(
                f"  estimated writes {estimated:,} of {remaining:,} remaining today "
                f"({writes_used:,} already used)"
            )

        refusals = seed_module.check_gates(
            plan, collection, SCHEMA_VERSION, writes_used, prune
        )
        if refusals:
            typer.echo("")
            for refusal in refusals:
                typer.echo(f"✗ {refusal.reason}", err=True)
                typer.echo(f"  {refusal.detail}", err=True)
            raise typer.Exit(1)

        if plan.is_empty and not full:
            typer.echo("")
            typer.echo("✓ D1 is already up to date — nothing to write")
            return

        if dry or not confirm:
            typer.echo("")
            typer.echo(
                f"Would write {len(plan.to_write)} card(s), ~{estimated:,} rows."
            )
            if plan.backfill:
                typer.echo(
                    f"Would backfill source_hash on {len(plan.backfill)} "
                    "already-current card(s)."
                )
            if prune and plan.missing_ids:
                typer.echo(f"Would DELETE {len(plan.missing_ids)} card(s).")
            if not confirm:
                typer.echo("This writes to production D1. Re-run with --confirm.")
            raise typer.Exit(0 if dry else 1)

        seeded_at = (
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        )
        groups = [seed_module.statements_for(row, seeded_at) for row in plan.to_write]
        # One statement per group: a backfill touches a single row and depends on nothing,
        # so there is no atomicity to preserve and `pack_groups` is free to fill batches.
        groups.extend([seed_module.backfill_statement(row)] for row in plan.backfill)
        if prune and plan.missing_ids:
            groups.extend(seed_module.prune_statements(plan.missing_ids))

        batches = d1.pack_groups(groups)
        typer.echo("")
        typer.echo(f"→ writing {len(batches)} batch(es)")

        report = d1.WriteReport()
        progress = _progress("batches")
        for index, batch in enumerate(batches):
            try:
                report.merge(d1.execute(http, config, batch))
            except d1.D1Error as exc:
                typer.echo("", err=True)
                typer.echo(f"✗ batch {index + 1} failed: {exc}", err=True)
                typer.echo(
                    "  A D1 batch is atomic, so that batch wrote nothing. Cards in "
                    "earlier batches are committed; re-run to continue from there.",
                    err=True,
                )
                raise typer.Exit(1)
            progress(index + 1, len(batches))

        if full:
            typer.echo("→ rebuilding the FTS index")
            report.merge(
                d1.execute(
                    http, config, [d1.Statement("INSERT INTO cards_fts(cards_fts) VALUES('rebuild')")]
                )
            )

        typer.echo("")
        typer.echo(
            f"  wrote {report.rows_written:,} rows "
            f"(estimated {estimated:,}), read {report.rows_read:,}"
        )
        if report.size_after:
            typer.echo(f"  database is now {report.size_after / 1024 / 1024:.1f} MB")

        status = seed_module.build_status(
            plan,
            collection,
            report,
            mode="full" if full else "diff",
            pruned=plan.missing_ids if prune else (),
        )
        _upload_status(status)

        typer.echo("")
        typer.echo(f"✓ seeded {len(plan.to_write)} card(s)")
    finally:
        http.close()


def _upload_status(status: dict) -> None:
    """Write `status.json` locally and push it to R2.

    `seed` uploads it rather than leaving it for the next `publish`, because publish
    runs *before* seed — a status file written here and uploaded there would always
    describe the previous run (D11, ADR 0004).

    A failed upload is a warning, not an error: the seeding itself succeeded, and
    status.json is a status page, not data.
    """
    paths.ensure_dirs()
    local = paths.BUILD_DIR / "status.json"
    local.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    typer.echo(f"  wrote {local}")

    try:
        config = r2.load_config()
        s3 = r2.client(config)
        r2.upload(
            s3,
            config.artifacts_bucket,
            r2.UploadItem("status.json", local, "new"),
            r2.ARTIFACT_CACHE_CONTROL,
        )
        typer.echo("  uploaded status.json to R2")
    except Exception as exc:  # noqa: BLE001 — a status page must not fail a good seed
        typer.echo(f"  status.json not uploaded: {exc}")
        typer.echo("  (the seed itself succeeded; re-upload with `holo-data publish`)")


# --- status ------------------------------------------------------------------

@app.command("glossary")
def glossary_(
    locale: Optional[str] = typer.Option(None, "--locale", help="report one locale only"),
    missing: bool = typer.Option(
        False, "--missing", help="list the keys with no decision yet"
    ),
    review: bool = typer.Option(
        False, "--review", help="list machine-written entries nobody has checked"
    ),
) -> None:
    """Report what the proper-noun glossary covers.

    `pipeline/glossary/` is the committed source of truth for names, sets and tags —
    what `translate` masks with, what `build` labels dropdowns with, and what the site's
    i18n maps are generated from. This shows where it still has gaps.
    """
    glossaries = glossary_module.load_all()
    if not any(g.entries for g in glossaries.values()):
        typer.echo(
            "glossary is empty — seed it with\n"
            "  uv run python pipeline/scripts/seed_glossary.py",
            err=True,
        )
        raise typer.Exit(1)

    locales = [locale] if locale else list(poe.target_locales())
    for line in glossary_module.coverage_report(glossaries, locales):
        typer.echo(line)

    # Two distinct names displaying identically is almost always a copy-paste slip, and
    # it is invisible in review. The seeded glossary carried one, inherited from the
    # hand-written i18n and live on the site: Shiranui Flare shown as Shirakami Fubuki.
    found_collisions = False
    for kind, glossary in glossaries.items():
        for loc in locales:
            for display, keys in sorted(glossary.collisions(loc).items()):
                if not found_collisions:
                    typer.echo("")
                    typer.echo("⚠ distinct entries sharing one display name:")
                    found_collisions = True
                typer.echo(f"  {kind}/{loc}: {display!r} <- {keys}")

    pending = {
        kind: glossary.needs_review() for kind, glossary in glossaries.items()
    }
    if any(pending.values()):
        total = sum(len(keys) for keys in pending.values())
        typer.echo("")
        typer.echo(f"{total} entry(ies) are machine-written and unreviewed:")
        for kind, keys in pending.items():
            if keys:
                typer.echo(f"  {kind}: {len(keys)}")

    if review:
        for kind, keys in pending.items():
            if not keys:
                continue
            typer.echo(f"\n{kind} — needs review:")
            for key in keys:
                entry = glossaries[kind].entries[key]
                shown = ", ".join(
                    f"{loc}={entry.translations[loc]!r}"
                    for loc in sorted(entry.translations)
                )
                typer.echo(f"  {key}\n      {shown}")

    if not missing:
        return

    for kind, entries in glossaries.items():
        for loc in locales:
            gaps = entries.missing(loc)
            if gaps:
                typer.echo(f"\n{kind}/{loc} — {len(gaps)} undecided:")
                for key in gaps:
                    typer.echo(f"  {key}")


@app.command("corrections")
def corrections_(
    locale: Optional[str] = typer.Option(
        None, "--locale", help="report one locale only"
    ),
    extract: bool = typer.Option(
        False,
        "--extract",
        help="move `manual` cache entries that predate this mechanism into the "
        "committed files, so they become reviewable",
    ),
) -> None:
    """Verify the committed translation corrections. Spends nothing.

    `pipeline/corrections/{locale}.json` is where a hand-written translation lives — the
    reviewable surface #18 asked for, and the one thing a contributor can send as a PR
    against card text. `translate` never overwrites what it holds.

    A correction names its `kind` and the Japanese `source`; the cache key is derived, so
    nobody has to compute a hash. **This is the check that replaces a stored key**: every
    `(kind, source)` is looked up in the current build, and one that no card prints is
    reported here rather than sitting inert as an entry matching nothing. That happens for
    a typo in the Japanese, and it happens when the official site rewords a card — the
    same key-moved-underneath-us shape as #78.

    Needs no Poe key. Folding a file into a dict is verifiable offline, which was the
    third of the three worries that kept this open.
    """
    all_corrections = corrections_module.load_all()
    if locale:
        all_corrections = {
            loc: c for loc, c in all_corrections.items() if loc == locale
        }

    total = sum(len(c) for c in all_corrections.values())
    if not total:
        # Deliberately not an early return: with no corrections files at all, *every*
        # `manual` cache entry is an orphan — which is the state this command exists to
        # get a repo out of, and returning here would make it silent.
        typer.echo("no corrections recorded")
        typer.echo(f"  they would live in {paths.CORRECTIONS_DIR}")

    collection = build_module.load()
    units = None
    if collection is None:
        typer.echo(
            "⚠ no build found — cannot check corrections against the cards they "
            "translate. Run `holo-data build` first.",
            err=True,
        )
    else:
        cards = collection.model_dump(mode="json", exclude_none=True)["cards"]
        units = units_module.collect(cards).values()

    failed = False
    for loc, corrections in sorted(all_corrections.items()):
        typer.echo(f"{loc}: {len(corrections)} correction(s)")
        for item in sorted(corrections.items, key=lambda c: (c.kind, c.key)):
            typer.echo(f"  {item.kind:15s} {item.key.split(':')[1][:12]}… {item.value!r}")

        if units is None:
            continue
        # An unmatched correction is silent by construction — it fills a slot the build
        # never asks for. Naming it is the whole reason this command exists.
        for orphan in corrections.unknown(units):
            failed = True
            typer.echo(
                f"  ✗ no card prints this {orphan.kind}: {orphan.source!r}",
                err=True,
            )

    # Entries written before corrections/ existed: durable, but invisible to review.
    cache = TranslationCacheV2.load()
    stranded = {
        loc: keys
        for loc in (
            [locale] if locale else sorted(cache.entries)
        )
        if (keys := cache.orphan_manual(loc))
    }

    if stranded and not extract:
        count = sum(len(keys) for keys in stranded.values())
        typer.echo("")
        typer.echo(
            f"⚠ {count} `manual` cache entry(ies) have no committed correction — "
            "they are durable but unreviewable.",
            err=True,
        )
        for loc, keys in stranded.items():
            typer.echo(f"    {loc}: {len(keys)}", err=True)
        typer.echo("  re-run with --extract to move them into corrections/", err=True)

    if extract:
        if not stranded:
            typer.echo("")
            typer.echo("✓ nothing to extract — every `manual` entry is committed")
        else:
            typer.echo("")
            # The source string is not stored in the cache — only its hash — so the
            # build is what supplies it. Without a build there is nothing to extract
            # *from*, which is why this refuses rather than writing hashes.
            if units is None:
                typer.echo(
                    "✗ --extract needs a build: the cache stores a hash, and the "
                    "source string it addresses comes from the cards.",
                    err=True,
                )
                raise typer.Exit(1)

            by_key = {unit.key: unit for unit in units}
            for loc, keys in stranded.items():
                corrections = all_corrections.get(
                    loc, corrections_module.Corrections(locale=loc)
                )
                moved = 0
                for key in keys:
                    unit = by_key.get(key)
                    if unit is None:
                        typer.echo(
                            f"  ⚠ {loc}: {key} matches no card in the build — left in "
                            "the cache, nothing to key a correction on",
                            err=True,
                        )
                        continue
                    corrections.items.append(
                        corrections_module.Correction(
                            kind=unit.kind,
                            source=unit.value,
                            value=cache.entries[loc][key].value,
                            note="extracted from the cache",
                        )
                    )
                    moved += 1
                if moved:
                    written = corrections.save()
                    typer.echo(f"  ✓ {loc}: {moved} moved to {written}")

    if failed:
        raise typer.Exit(1)

    if units is not None and total:
        typer.echo("")
        typer.echo(f"✓ {total} correction(s) all match a string in the build")


@app.command("normalise-cache")
def normalise_cache(
    locale: Optional[str] = typer.Option(
        None, "--locale", help="normalise one locale only"
    ),
    write: bool = typer.Option(
        False, "--write", help="required to modify the cache; otherwise reports only"
    ),
) -> None:
    """Apply deterministic fixes to cached translations. Spends nothing.

    Three kinds of defect, none of them a translation *judgement*:

    **One word spelled several ways** — #28's `エール`, which came back from the Thai run
    as four different strings, one of them (`เอール`) Thai `เอ` followed by katakana
    `ール`, not a word in any language.

    **A card reference in ASCII brackets** — #27. The source writes `〈…〉` 6,804 times and
    ASCII `<>` zero times, so `<Hakui Koyori>` is always model output. This one is not
    cosmetic: `ability_text` renders through `v-html`, so a browser reads that as an
    unknown tag and **drops the name**. 54 names were invisible on 24 live card pages.

    **A quoted name left in Japanese** — #27, where the canonical translation is already
    one entry away in the same cache and nothing was looking it up. Needs a build, since
    that is where the source-string-to-unit map comes from; skipped without one.

    A re-translation would cost money and would not fix any of them: the model produced
    the inconsistency, and nothing about a second run makes it pick one answer. This is
    deterministic, free, and re-runnable.

    Reports by default and needs `--write` to touch the cache, matching `translate`'s
    posture — the cache is expensive to rebuild and this rewrites it in place.

    Entries it changes keep their `source_hash`, because the *source* has not moved —
    only our rendering of it. A `manual` entry is left alone entirely: a human decided
    that string, and a blanket rule does not get to overrule them.
    """
    cache = TranslationCacheV2.load()
    locales = [locale] if locale else sorted(cache.entries)
    total = 0
    dirty = False

    # The quoted-name map, per locale: source string -> this locale's translation, for
    # every unit the build contains. Without a build there is no way to know which
    # quoted strings are names, so that rule is skipped rather than guessed at.
    quotes_by_locale: dict[str, dict[str, str]] = {}
    collection = build_module.load()
    if collection is None:
        typer.echo(
            "no build found — the quoted-name rule needs one and will be skipped "
            "(`holo-data build` to enable it)",
            err=True,
        )
    else:
        cards = collection.model_dump(mode="json", exclude_none=True)["cards"]
        all_units = units_module.collect(cards)
        for loc in locales:
            quotes_by_locale[loc] = {
                unit.value: entry.value
                for key, unit in all_units.items()
                if isinstance(unit.value, str)
                and (entry := cache.get(loc, key)) is not None
                and isinstance(entry.value, str)
            }

    for loc in locales:
        entries = cache.entries.get(loc)
        if not entries:
            typer.echo(f"{loc}: no entries", err=True)
            continue

        # `manual` is excluded rather than filtered afterwards: ADR 0002's durability
        # guarantee is that a human decision stands until the source moves, and a
        # spelling rule is exactly the kind of blanket change it protects against.
        editable = {
            key: entry.value
            for key, entry in entries.items()
            if entry.source != "manual"
        }

        changed, report = normalise_module.normalise_locale(
            editable, loc, quotes=quotes_by_locale.get(loc)
        )
        for line in report.lines():
            typer.echo(line)

        left = normalise_module.remaining({**editable, **changed}, loc)
        if left:
            # An ordered rewrite that leaves variants behind has produced a *new*
            # spelling rather than removing the old ones — the specific way this goes
            # wrong, so it is checked rather than assumed.
            typer.echo(f"  ⚠ variants still present after the pass: {left}", err=True)
            raise typer.Exit(1)

        # `manual` entries are not rewritten, which used to mean they were not *checked*
        # either — a bad variant inside a committed correction was invisible to both the
        # pass and its guard, and the command still printed ✓. Reported, never rewritten:
        # the fix belongs in `pipeline/corrections/`, where a human can review the diff.
        protected_left = normalise_module.remaining(
            {k: e.value for k, e in entries.items() if e.source == "manual"}, loc
        )
        if protected_left:
            typer.echo(
                f"  ⚠ {loc}: a `manual` entry contains {protected_left} — not rewritten "
                "(fix it in pipeline/corrections/)",
                err=True,
            )

        total += report.total_replacements
        if changed and write:
            for key, value in changed.items():
                entries[key].value = value
            dirty = True

    if not total:
        typer.echo("✓ nothing to normalise")
        return

    if not write:
        typer.echo(f"\n{total} replacement(s) available — re-run with --write to apply")
        return

    if dirty:
        cache.save()
        typer.echo(f"\n✓ {total} replacement(s) written to the cache")
        typer.echo("  next: `holo-data build`, then publish and seed")


@app.command("cache-status")
def cache_status() -> None:
    """How far each locale has moved to the content-addressed cache. Spends nothing.

    Answers "is this locale consistent yet?" — which without this is a question you
    answer by reading the diff of a 24 MB gitignored file.

    A locale is complete when every unit in the build has a v2 entry. Until then the
    build falls back to the per-card cache for the rest, so output stays complete while
    the migration is half-done.
    """
    collection = build_module.load()
    if collection is None:
        typer.echo("no build found — run `holo-data build` first", err=True)
        raise typer.Exit(1)

    cards = collection.model_dump(mode="json", exclude_none=True)["cards"]
    units = units_module.collect(cards)
    stats = units_module.stats(units)
    cache = TranslationCacheV2.load()

    typer.echo(
        f"{stats.distinct} distinct units from {stats.occurrences} field occurrences "
        f"({stats.chars:,} source chars)"
    )
    for line in stats.lines():
        typer.echo(line)

    typer.echo("")
    if not cache.entries:
        typer.echo("no v2 cache yet — run pipeline/scripts/migrate_cache.py")
        return

    for locale in poe.target_locales():
        typer.echo(f"  {cache.status(locale, units.values()).describe()}")


@app.command("report-masks")
def report_masks(
    show: int = typer.Option(25, "--show", help="how many names to list"),
    failures_only: bool = typer.Option(
        False, "--failures-only", help="print nothing unless a string fails to restore"
    ),
) -> None:
    """Show what masking would do to every translatable string. Spends nothing.

    Masking rewrites text on its way to the model and puts names back afterwards, so a
    bug here corrupts translations rather than failing them. This is the offline
    rehearsal: every string in the build is masked and restored, and any that does not
    come back byte-identical is reported.

    Run it after editing `pipeline/glossary/` and before `translate`.
    """
    collection = build_module.load()
    if collection is None:
        typer.echo("no build found — run `holo-data build` first", err=True)
        raise typer.Exit(1)

    names = glossary_module.Glossary.load("names")
    tags = glossary_module.Glossary.load("tags")
    table = mask_table.combined_table(names, tags)
    report = masking.MaskReport()

    for card in collection.cards:
        source = card.translations[SOURCE_LOCALE]
        for text in _translatable_strings(source):
            report.record(text, table)

    if failures_only:
        if not report.failures:
            typer.echo(f"✓ {report.total} strings round-trip")
            return
    else:
        typer.echo(
            f"mask table: {len(table)} entries "
            f"({len(names.entries)} names + {len(tags.entries)} tags)"
        )
        for line in report.lines(top=show):
            typer.echo(line)

    if report.failures:
        raise typer.Exit(1)


def _translatable_strings(translation) -> list[str]:
    """Every short label and prose string on one locale's translation."""
    out: list[str] = []
    for value in (translation.name, translation.ability_text, translation.extra):
        if value:
            out.append(value)
    out.extend(translation.tags or [])
    for art in translation.arts or []:
        out.extend(v for v in (art.name, art.effect) if v)
    if translation.keyword:
        out.extend(v for v in (translation.keyword.name, translation.keyword.effect) if v)
    for skill in (translation.oshi_skill, translation.sp_oshi_skill):
        if skill:
            out.extend(v for v in (skill.name, skill.effect, skill.timing) if v)
    for qa in translation.qa_items or []:
        out.extend(v for v in (qa.title, qa.question, qa.answer) if v)
    return out


@app.command("backup-cache")
def backup_cache(
    remote: bool = typer.Option(
        False, "--remote", help="also upload a copy to R2 (needs credentials + boto3)"
    ),
    keep: int = typer.Option(10, "--keep", help="how many local snapshots to retain"),
    backup_dir: Optional[Path] = typer.Option(
        None, "--dir", help=f"where to write (default: {backup.DEFAULT_BACKUP_DIR})"
    ),
) -> None:
    """Back up the translation cache — the one file the pipeline cannot rebuild.

    Everything else under `pipeline/` is reproducible by re-running. The cache is a
    year of paid API calls, it is gitignored, and `publish` does not upload it — so
    until this command existed it lived in exactly one place, on one laptop.

    Writes a dated snapshot outside the repo (so `git clean` cannot take it) and
    verifies the copy by loading it back and comparing entry counts. `--remote` adds
    a copy in the artifacts bucket, which is what survives losing the machine.
    """
    target_dir = backup_dir or backup.DEFAULT_BACKUP_DIR

    # Both caches, because both hold work that exists nowhere else. v1 is a year of paid
    # calls; v2 holds the `manual` entries — which are hand-written, gitignored, and
    # therefore exactly as unbacked as v1 was before this command existed.
    sources = [(paths.cache_file(), False)]
    if cache_v2_module.cache_v2_file().exists():
        sources.append((cache_v2_module.cache_v2_file(), True))

    written: list[Path] = []
    for source, is_v2 in sources:
        if not source.exists():
            continue
        try:
            path, stats = backup.write_local(source=source, backup_dir=target_dir)
        except backup.BackupError as exc:
            typer.echo(f"✗ {exc}", err=True)
            raise typer.Exit(1)

        typer.echo(f"→ {source.name}: {stats.describe()}")
        typer.echo(f"✓ verified: {path}")
        written.append(path)

        removed = backup.prune_local(target_dir, keep=keep, v2=is_v2)
        if removed:
            typer.echo(f"  pruned {len(removed)} older snapshot(s), keeping {keep}")

    if not written:
        typer.echo("no cache found to back up", err=True)
        raise typer.Exit(1)

    if not remote:
        typer.echo("")
        typer.echo(
            "These copies are on the same disk as the originals. Re-run with --remote "
            "to put one in R2."
        )
        return

    try:
        config = r2.load_config()
        s3 = r2.client(config)
    except r2.R2Error as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1)

    for path in written:
        key = backup.upload_to_r2(s3, config.artifacts_bucket, path)
        typer.echo(f"✓ uploaded to r2://{config.artifacts_bucket}/{key}")

    existing = backup.list_r2_backups(s3, config.artifacts_bucket)
    total = sum(size for _, size in existing)
    typer.echo(
        f"  {len(existing)} backup(s) in the bucket, {total / 1_048_576:.1f} MB total"
    )


@app.command()
def status() -> None:
    """Show what the pipeline currently has on disk."""
    paths.ensure_dirs()

    def describe(path: Path, label: str) -> None:
        if path.exists():
            size = path.stat().st_size
            typer.echo(f"  {label:22s} {size / 1024 / 1024:8.1f} MB  {path}")
        else:
            typer.echo(f"  {label:22s} {'—':>8s}      (not built)")

    typer.echo("pipeline state:")
    describe(paths.card_ids_file(), "card ids")
    describe(paths.raw_html_file(), "raw html")
    describe(paths.structured_file(), "structured")
    describe(paths.i18n_file(), "contract shape")
    describe(paths.cache_file(), "translation cache")
    describe(paths.cards_json(), "cards.json")

    # rglob — the trees are nested by set (`{set}/{stem}.png`).
    png = len(list(paths.PNG_DIR.rglob("*.png")))
    webp = len(list(paths.WEBP_DIR.rglob("*.webp")))
    sets = len([d for d in paths.WEBP_DIR.iterdir() if d.is_dir()]) if paths.WEBP_DIR.exists() else 0
    typer.echo(f"  {'images':22s} {png} PNG, {webp} WebP across {sets} set(s)")

    cache = TranslationCache.load()
    if cache.entries:
        typer.echo("  translations cached:")
        for locale, cards in sorted(cache.entries.items()):
            fields = sum(len(entry) for entry in cards.values())
            manual = cache.manual_count(locale)
            note = f", {manual} manual" if manual else ""
            typer.echo(f"    {locale}: {len(cards)} cards, {fields} fields{note}")


if __name__ == "__main__":
    app()
