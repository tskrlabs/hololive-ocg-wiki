"""Driving batches through the Poe API and into the content-addressed cache.

The v2 counterpart to `poe.run_translation`. What changed is the unit of work: that
function sent one card per call per locale, this one sends a batch of distinct strings
sharing a kind.

Everything about cost control is kept. The rate limiter and retry/back-off behaviour are
v1's, unchanged, because they have run against this endpoint for a year. `--confirm` is
still required (D10). `--dry-run` still costs nothing and reports exactly what would be
sent.

**The cache is the unit of progress.** A failed batch is reported and skipped; whatever
succeeded is saved. A re-run sends only what is still stale, so an interrupted or partly
failed run is resumed rather than restarted — which matters when a run is 204 calls and
the last one fails.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .batcher import Batch, BatchResult, build_batches, collect_result, parse_reply
from .cache_v2 import TranslationCacheV2
from .poe import DEFAULT_MODEL, RateLimiter
from .units import Unit

DEFAULT_CONCURRENCY = 4
DEFAULT_MAX_RETRIES = 3
POE_BASE_URL = "https://api.poe.com/v1"


@dataclass
class RunReport:
    """What a run did, for the operator and for the phase record."""

    locale: str
    batches_sent: int = 0
    batches_failed: int = 0
    units_translated: int = 0
    units_failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def lines(self) -> list[str]:
        out = [
            f"{self.locale}: {self.units_translated} units from "
            f"{self.batches_sent} call(s), {self.total_tokens:,} tokens "
            f"({self.prompt_tokens:,} in / {self.completion_tokens:,} out)"
        ]
        if self.batches_failed:
            out.append(f"  ⚠ {self.batches_failed} batch(es) failed entirely")
        if self.units_failed:
            out.append(f"  ⚠ {self.units_failed} unit(s) rejected — left stale, retried next run")
        out.extend(f"    {failure}" for failure in self.failures[:10])
        if len(self.failures) > 10:
            out.append(f"    … and {len(self.failures) - 10} more")
        return out


async def _send(
    client: Any,
    batch: Batch,
    limiter: RateLimiter,
    model: str,
    max_retries: int,
) -> tuple[dict[str, Any] | None, dict[str, int]]:
    """Send one batch, returning the parsed reply and token usage.

    Retries on a malformed reply as well as on an API error: a model that returns prose
    instead of JSON usually returns JSON on the next attempt, and that is cheaper than
    dropping 40 units.
    """
    prompt = batch.prompt()
    usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for attempt in range(max_retries):
        try:
            await limiter.wait_if_needed()
            response = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}]
            )
            if response.usage:
                usage["prompt_tokens"] += response.usage.prompt_tokens or 0
                usage["completion_tokens"] += response.usage.completion_tokens or 0
            return parse_reply(response.choices[0].message.content.strip()), usage
        except Exception as exc:  # noqa: BLE001 — the reply shape is not ours to trust
            print(f"  {batch.kind}/{batch.locale}: attempt {attempt + 1} failed: {exc}")
            if "rate limit" in str(exc).lower() or "429" in str(exc):
                await asyncio.sleep(5)
            if attempt < max_retries - 1:
                await asyncio.sleep((attempt + 1) * 2)

    return None, usage


async def run_locale(
    units: Iterable[Unit],
    cache: TranslationCacheV2,
    table: list[tuple[str, str]],
    restorer: object,
    locale: str,
    model: str = DEFAULT_MODEL,
    concurrency: int = DEFAULT_CONCURRENCY,
    char_budget: int | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> RunReport:
    """Translate every stale unit for one locale.

    Returns:
        A report naming what was translated, what failed, and what it cost.
    """
    import openai

    api_key = os.getenv("POE_API_KEY")
    if not api_key:
        raise ValueError(
            "POE_API_KEY is not set. Get a key from https://poe.com/api_key and put it "
            "in pipeline/.env"
        )

    from .batcher import DEFAULT_CHAR_BUDGET

    stale = cache.stale(locale, units)
    report = RunReport(locale=locale)
    if not stale:
        return report

    batches = build_batches(
        stale, locale, table, char_budget or DEFAULT_CHAR_BUDGET
    )
    client = openai.AsyncOpenAI(api_key=api_key, base_url=POE_BASE_URL)
    limiter = RateLimiter()
    semaphore = asyncio.Semaphore(concurrency)
    done = 0

    async def handle(batch: Batch) -> tuple[Batch, BatchResult | None, dict[str, int]]:
        async with semaphore:
            reply, usage = await _send(
                client, batch, limiter, model, DEFAULT_MAX_RETRIES
            )
            if reply is None:
                return batch, None, usage
            return batch, collect_result(batch, reply, restorer), usage

    for coro in asyncio.as_completed([handle(batch) for batch in batches]):
        batch, result, usage = await coro
        done += 1
        report.prompt_tokens += usage["prompt_tokens"]
        report.completion_tokens += usage["completion_tokens"]

        if result is None:
            report.batches_failed += 1
            report.units_failed += batch.size
            report.failures.append(
                f"{batch.kind}: whole batch of {batch.size} units failed"
            )
        else:
            report.batches_sent += 1
            # Units keyed by content, so a translation lands once for every card that
            # prints the string — the saving this whole rework is built on.
            by_key = {item.unit.key: item.unit for item in batch.items}
            for key, value in result.translations.items():
                cache.put(locale, by_key[key], value)
            report.units_translated += result.ok
            report.units_failed += len(result.failures)
            report.failures.extend(result.failures)

        if on_progress:
            on_progress(done, len(batches), f"{batch.kind}")

    return report
