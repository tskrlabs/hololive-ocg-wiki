"""`holo-data` — the pipeline CLI.

Replaces v1's numbered scripts and `run-pipeline.sh`. The command order encodes D10's
gated update flow: everything before `publish` is local, free and reversible, and the
steps that cost money or touch production are explicit.

    holo-data scrape              official site -> raw HTML + images   (local, free)
    holo-data images              PNG -> WebP                          (local, free)
    holo-data translate           Poe API                              ($$ — never implicit)
    holo-data build               merge + validate -> cards.json       (local, free)
    holo-data verify              diff against v1's data               (local, free)
    holo-data publish             images + artifacts -> R2             (Phase 2)
    holo-data seed --dry          row counts + D1 write estimate       (Phase 3)
    holo-data seed --confirm      diff-based upsert into D1            (Phase 3)

`translate` requires `--confirm` or refuses, and prints exactly what it would spend
under `--dry-run`. An agent-driven run that misfires must not be able to burn the Poe
budget or corrupt live data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from . import build as build_module
from . import images as images_module
from . import paths, transform, verify as verify_module
from .scrape import card_list, extract, fetch
from .translate import poe
from .translate.cache import TranslationCache

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
    cards = transform.transform_cards(structured, on_progress=_progress("cards"))
    transform.save_i18n(cards)

    typer.echo(f"✓ scraped {len(cards)} cards")


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
        help="publish despite unrecognised enum values (prints what it let through)",
    ),
) -> None:
    """Merge translations and validate against the contract, producing cards.json."""
    cards = transform.load_i18n()
    if not cards:
        typer.echo("no cards found — run `holo-data scrape` first", err=True)
        raise typer.Exit(1)

    cache = TranslationCache.load()
    locales = poe.target_locales()

    typer.echo(f"→ building {len(cards)} cards across {len(locales) + 1} locales")
    collection, report = build_module.build(
        cards, cache, locales, allow_unknown_enums=allow_unknown_enums
    )

    typer.echo("  translation coverage:")
    for locale, count in report.translation_coverage.items():
        pct = 100 * count / report.total if report.total else 0
        typer.echo(f"    {locale}: {count}/{report.total} ({pct:.0f}%)")

    if report.enum_violations:
        typer.echo("")
        label = "allowed" if allow_unknown_enums else "unrecognised"
        typer.echo(f"  {label} enum values:", err=not allow_unknown_enums)
        for message, ids in sorted(report.enum_violations.items()):
            typer.echo(f"    {len(ids):5d}  {message}")
            typer.echo(f"           e.g. card {', '.join(ids[:5])}")

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
    typer.echo(
        f"✓ wrote {paths.cards_json()} — {report.valid} cards, {size / 1024 / 1024:.1f} MB"
    )


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


# --- Phase 2 / 3 placeholders ------------------------------------------------

@app.command()
def publish() -> None:
    """Upload images and artifacts to R2. (Phase 2)"""
    typer.echo("`publish` arrives in Phase 2, with the Cloudflare resources.", err=True)
    typer.echo("It will upload images/webp/ and build/cards.json to R2.", err=True)
    raise typer.Exit(1)


@app.command()
def seed(
    dry: bool = typer.Option(False, "--dry", help="report row counts and write estimate"),
    confirm: bool = typer.Option(False, "--confirm", help="perform the upsert"),
) -> None:
    """Seed D1 from the published artifact. (Phase 3)"""
    typer.echo("`seed` arrives in Phase 3, with the D1 schema.", err=True)
    typer.echo(
        "It will require a --dry run first and gate --full separately (D10).", err=True
    )
    raise typer.Exit(1)


# --- status ------------------------------------------------------------------

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

    png = len(list(paths.PNG_DIR.glob("*.png")))
    webp = len(list(paths.WEBP_DIR.glob("*.webp")))
    typer.echo(f"  {'images':22s} {png} PNG, {webp} WebP")

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
