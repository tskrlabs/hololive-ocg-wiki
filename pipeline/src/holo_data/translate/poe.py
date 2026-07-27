"""Translate cards via the Poe API, driven by the field-level cache.

Ported from v1's `5-poe-translate-i18n.py`. **The prompts are verbatim** — they live in
`prompts.json` and encode a year of tuning about what must *not* be translated (proper
nouns, anything in 〈〉, rarity/set/cardType/illustrator/tags). Changing them changes
translation quality, so they are data, not code.

What changed is *when* a card is sent and *what is kept from the reply*:

- v1 hashed the whole card, so any change re-translated everything. Here the cache
  hashes each field, so a card is only sent when at least one field is stale — and on
  measured data that is ~39 cards per update instead of ~2,100.
- The whole card still goes in the prompt and the whole card still comes back. Only
  **stale** fields are read out of the response; everything else is discarded. That is
  what makes a manual correction durable: even when a card is re-sent because its Q&A
  changed, the corrected `name` in the cache is what wins, because the model's `name` is
  thrown away.

Cost is gated per D10 — `translate` is never implicit, and `--dry-run` reports what
would be sent without spending anything.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .cache import TranslationCache, field_keys

PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.json"
POE_BASE_URL = "https://api.poe.com/v1"
DEFAULT_MODEL = "GPT-5-Chat"
DEFAULT_MAX_RETRIES = 3
DEFAULT_CONCURRENCY = 5
DEFAULT_RATE_LIMIT = 8.0  # requests per second


def load_prompts() -> dict[str, dict[str, str]]:
    return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))


def target_locales() -> list[str]:
    """Locales we translate into — every locale except the JP source."""
    return list(load_prompts())


class RateLimiter:
    """Sliding-window limiter. Ported from v1's AsyncRateLimiter."""

    def __init__(self, max_per_second: float = DEFAULT_RATE_LIMIT) -> None:
        self.max_per_second = max_per_second
        self.window = 1.0
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def wait_if_needed(self) -> None:
        async with self._lock:
            now = time.time()
            while self.requests and self.requests[0] <= now - self.window:
                self.requests.popleft()

            if len(self.requests) >= self.max_per_second:
                sleep_for = self.window - (now - self.requests[0])
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)

            self.requests.append(time.time())


@dataclass
class TranslationPlan:
    """What `translate` would do, per locale — the basis of `--dry-run`."""

    locale: str
    stale_by_card: dict[str, list[str]] = field(default_factory=dict)

    @property
    def card_count(self) -> int:
        return len(self.stale_by_card)

    @property
    def field_count(self) -> int:
        return sum(len(fields) for fields in self.stale_by_card.values())


def plan_translation(
    cards: list[dict[str, Any]], cache: TranslationCache, locale: str
) -> TranslationPlan:
    """Work out which cards have at least one stale field.

    This is the whole saving: cards whose fields are all fresh are never sent.
    """
    plan = TranslationPlan(locale=locale)
    for card in cards:
        card_id = card["id"]
        jp = card.get("translations", {}).get("ja", {})
        stale = cache.stale_fields(locale, card_id, jp)
        if stale:
            plan.stale_by_card[card_id] = stale
    return plan


def extract_json(response: str) -> dict[str, Any]:
    """Pull the JSON object out of a model reply.

    Models sometimes wrap the JSON in prose or a fenced block despite being told not to,
    so this takes everything between the first `{` and the last `}` — v1's approach.
    """
    start = response.find("{")
    end = response.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("no JSON object found in response")
    return json.loads(response[start:end])


def read_field(translated: dict[str, Any], field_key: str) -> Any:
    """Read one field out of a translated card by its cache key.

    Keys look like `name`, `arts[0].effect`, `qa_items[2]`. Returns None when the model
    omitted it, which the caller treats as "leave the cache alone".
    """
    node: Any = translated
    for part in field_key.split("."):
        if node is None:
            return None
        name, _, index = part.partition("[")
        if name:
            if not isinstance(node, dict):
                return None
            node = node.get(name)
        if index:
            position = int(index.rstrip("]"))
            if not isinstance(node, list) or position >= len(node):
                return None
            node = node[position]
    return node


async def translate_card(
    client: Any,
    card_json: dict[str, Any],
    prompt_template: str,
    card_id: str,
    limiter: RateLimiter,
    model: str = DEFAULT_MODEL,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any] | None:
    """Send one card and return the parsed reply, or None after exhausting retries.

    v1's retry and back-off behaviour, kept: exponential back-off between attempts and a
    longer pause when the error looks like a rate limit.
    """
    prompt = prompt_template.replace(
        "{card_data}", json.dumps(card_json, ensure_ascii=False, indent=2)
    )

    for attempt in range(max_retries):
        try:
            await limiter.wait_if_needed()
            chat = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return extract_json(chat.choices[0].message.content.strip())
        except json.JSONDecodeError as exc:
            print(f"  card {card_id}: bad JSON (attempt {attempt + 1}): {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"  card {card_id}: API error (attempt {attempt + 1}): {exc}")
            if "rate limit" in str(exc).lower() or "429" in str(exc):
                await asyncio.sleep(5)

        if attempt < max_retries - 1:
            await asyncio.sleep((attempt + 1) * 2)

    return None


async def run_translation(
    cards: list[dict[str, Any]],
    cache: TranslationCache,
    locale: str,
    plan: TranslationPlan,
    model: str = DEFAULT_MODEL,
    concurrency: int = DEFAULT_CONCURRENCY,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> tuple[int, int]:
    """Translate every card in the plan, writing only stale fields into the cache.

    Returns:
        (cards_translated, fields_updated)
    """
    import openai  # imported here so `holo-data --help` works without the dependency

    api_key = os.getenv("POE_API_KEY")
    if not api_key:
        raise ValueError(
            "POE_API_KEY is not set. Get a key from https://poe.com/api_key and put it "
            "in pipeline/.env"
        )

    client = openai.AsyncOpenAI(api_key=api_key, base_url=POE_BASE_URL)
    prompts = load_prompts()
    prompt_template = prompts[locale]["prompt"]
    limiter = RateLimiter()
    semaphore = asyncio.Semaphore(concurrency)

    by_id = {card["id"]: card for card in cards}
    done = 0
    cards_translated = 0
    fields_updated = 0
    total = plan.card_count

    async def handle(card_id: str, stale: list[str]) -> tuple[str, dict | None, list[str]]:
        async with semaphore:
            card = by_id[card_id]
            jp = card.get("translations", {}).get("ja", {})
            # Whole card in — the prompt is unchanged from v1, and context matters for
            # pronouns and terminology.
            result = await translate_card(
                client, jp, prompt_template, card_id, limiter, model=model
            )
            return card_id, result, stale

    tasks = [handle(card_id, stale) for card_id, stale in plan.stale_by_card.items()]

    for coro in asyncio.as_completed(tasks):
        card_id, result, stale = await coro
        done += 1

        if result is not None:
            jp = by_id[card_id].get("translations", {}).get("ja", {})
            source_values = dict(field_keys(jp))
            cards_translated += 1

            # Whole card out — but only the stale fields are kept. Everything else in
            # the reply is discarded, which is what protects manual corrections.
            for field_key in stale:
                value = read_field(result, field_key)
                if value is None:
                    continue
                cache.put(locale, card_id, field_key, source_values[field_key], value)
                fields_updated += 1

        if on_progress:
            on_progress(done, total, card_id)

    return cards_translated, fields_updated
