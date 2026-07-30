"""Machine-translate the glossary's undecided entries, for maintainer review.

The glossary was seeded from the hand-written i18n maps, which covered 215 of 296 card
names and 25 of 35 sets. The remainder have no decision, so masking restores them as
Japanese — correct, but it is why calibration reported strings "left Japanese" in locales
that should have none.

This fills them with machine output **marked as unreviewed**, so the gap becomes a review
queue rather than a silence. A `review: true` flag on an entry means "a model wrote this,
nobody has looked".

It uses the same per-kind prompt as the pipeline, because these are card names and the
card-name prompt is the one tuned for them.

    uv run python pipeline/scripts/fill_glossary.py --dry-run
    uv run python pipeline/scripts/fill_glossary.py --confirm
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "pipeline" / ".env")

from holo_data.glossary import Glossary  # noqa: E402
from holo_data.translate.poe import DEFAULT_MODEL, RateLimiter  # noqa: E402
from holo_data.translate.prompts_v2 import LOCALE_NAMES, build_prompt  # noqa: E402
from holo_data.translate.runner import POE_BASE_URL  # noqa: E402

# One call per locale per kind is plenty: 81 names is ~700 characters.
BATCH_CHARS = 4000


async def fill(kind: str, glossary: Glossary, locale: str, model: str) -> dict[str, str]:
    """Translate every undecided key for one locale."""
    import openai

    missing = glossary.missing(locale)
    if not missing:
        return {}

    client = openai.AsyncOpenAI(
        api_key=__import__("os").getenv("POE_API_KEY"), base_url=POE_BASE_URL
    )
    limiter = RateLimiter()
    filled: dict[str, str] = {}

    # `card_name` for names, `tag` for sets — a set name is a product title, closest in
    # register to a label. Neither is masked: these *are* the proper nouns.
    prompt_kind = "card_name" if kind == "names" else "tag"

    batch: list[str] = []
    chars = 0
    for key in missing + [None]:  # sentinel flushes the last batch
        if key is not None and chars + len(key) <= BATCH_CHARS:
            batch.append(key)
            chars += len(key)
            continue

        if batch:
            payload = json.dumps(
                {str(i): text for i, text in enumerate(batch)},
                ensure_ascii=False,
                indent=2,
            )
            prompt = build_prompt(prompt_kind, locale, payload, with_context=False)
            await limiter.wait_if_needed()
            response = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}]
            )
            text = response.choices[0].message.content.strip()
            reply = json.loads(text[text.find("{") : text.rfind("}") + 1])
            for index, source in enumerate(batch):
                if value := reply.get(str(index)):
                    filled[source] = value

        batch = [key] if key is not None else []
        chars = len(key) if key is not None else 0

    return filled


async def run(confirm: bool, model: str) -> int:
    total_missing = 0
    plans: dict[str, Glossary] = {}

    for kind in ("names", "sets"):
        glossary = Glossary.load(kind)
        plans[kind] = glossary
        for locale in LOCALE_NAMES:
            gaps = len(glossary.missing(locale))
            total_missing += gaps
            if gaps:
                print(f"  {kind}/{locale}: {gaps} undecided")

    if total_missing == 0:
        print("✓ nothing undecided")
        return 0

    print(f"\n{total_missing} entries to fill across {len(LOCALE_NAMES)} locales")
    if not confirm:
        print("This costs money. Re-run with --confirm.")
        return 0

    for kind, glossary in plans.items():
        for locale in LOCALE_NAMES:
            filled = await fill(kind, glossary, locale, model)
            for key, value in filled.items():
                entry = glossary.entries[key]
                entry.translations[locale] = value
                # Marked so `holo-data glossary --review` can list exactly what a human
                # has not looked at. Machine output that is indistinguishable from a
                # curated decision is how a bad name survives for a year.
                entry.review = True
            print(f"  {kind}/{locale}: filled {len(filled)}")
        glossary.save()

    print("\n✓ glossary filled — every new value is marked `review: true`")
    print("  list them with: holo-data glossary --review")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    return asyncio.run(run(args.confirm, args.model))


if __name__ == "__main__":
    raise SystemExit(main())
