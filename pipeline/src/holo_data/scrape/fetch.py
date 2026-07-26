"""Fetch each card's detail page and download its image.

Ported from v1's `2-grab-card-info.py`. The HTML selectors and the Q&A parsing are
preserved exactly — that logic encodes a year of the official site's quirks and is the
part D3 explicitly says not to rewrite.

Two things changed, both plumbing:

- Images land in `images/png/` rather than `card_images/default/`, because Phase 1 adds
  a WebP conversion step and the two formats need separate directories (D9: PNG is a
  local intermediate, only WebP is uploaded).
- `image_path` is no longer stored on the card. It was a local filesystem path baked
  into the published data; the contract stores `image_key` and composes URLs (D9). The
  filename is derived from `image_url` at build time instead.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any, Callable

import requests
from bs4 import BeautifulSoup

from ..paths import PNG_DIR, ensure_dirs, raw_html_file

CARD_DETAIL_URL = "https://hololive-official-cardgame.com/cardlist/?id="
IMG_BASE_URL = "https://hololive-official-cardgame.com"

# v1 slept 0.1–0.3s between card requests. Kept: the official site is a small operation
# and a year of runs at this rate has not been rate-limited.
MIN_DELAY = 0.1
MAX_DELAY = 0.3


def download_image(img_src: str) -> str | None:
    """Download one card image if it is not already on disk.

    Returns the filename (not a path) so callers can derive an `image_key` without
    depending on where images happen to live.
    """
    ensure_dirs()
    img_filename = img_src.split("/")[-1]
    img_path = PNG_DIR / img_filename

    if img_path.exists():
        return img_filename

    img_response = requests.get(img_src, stream=True)
    if img_response.status_code != 200:
        return None

    with open(img_path, "wb") as img_file:
        for chunk in img_response.iter_content(1024):
            img_file.write(chunk)
    return img_filename


def fetch_card(card_id: str, download_images: bool = True) -> dict[str, Any]:
    """Fetch one card's detail page, returning its raw HTML and parsed Q&A.

    The parsing below is v1's, unchanged. Notably the Q&A block: the "Q"/"A" marker
    spans are `extract()`ed before reading the text, and related cards come from a
    *sibling* div rather than a child — both non-obvious and both load-bearing.
    """
    response = requests.get(CARD_DETAIL_URL + card_id)
    soup = BeautifulSoup(response.text, "html.parser")

    card_info: dict[str, Any] = {"id": card_id}

    card_name_div = soup.find("h1", class_="name")
    if card_name_div:
        card_info["name"] = card_name_div.get_text(strip=True)

    # --- Image ---
    try:
        img_div = soup.find("div", class_="img w100")
        if img_div and img_div.find("img"):
            img_src = img_div.find("img")["src"]
            if not img_src.startswith("http"):
                img_src = IMG_BASE_URL + img_src
            card_info["image_url"] = img_src

            if download_images:
                filename = download_image(img_src)
                card_info["image_filename"] = filename
            else:
                card_info["image_filename"] = img_src.split("/")[-1]
        else:
            card_info["image_url"] = None
            card_info["image_filename"] = None
    except Exception as exc:  # noqa: BLE001 — one bad image must not abort the run
        print(f"  error downloading image for {card_id}: {exc}")
        card_info["image_url"] = None
        card_info["image_filename"] = None

    # --- The detail block, kept as raw HTML for the extract step to parse ---
    txt_inner = soup.find("div", class_="txt-Inner")
    if txt_inner:
        card_info["raw_html"] = str(txt_inner)

    # --- Q&A ---
    try:
        qa_section = soup.find("div", class_="cardlist-Detail_QA", id="faq")
        if qa_section:
            card_info["qa_raw_html"] = str(qa_section)

            qa_items = []
            qa_list_items = qa_section.find_all("div", class_="qa-List_Item")

            for item in qa_list_items:
                qa_item: dict[str, Any] = {}

                title_div = item.find("div", class_="qa-List_Ttl")
                if title_div:
                    qa_item["title"] = title_div.get_text(strip=True)

                question_p = item.find("p", class_="qa-List_Txt-Q")
                if question_p:
                    # The leading "Q" marker is a span; drop it before reading text.
                    question_span = question_p.find("span")
                    if question_span:
                        question_span.extract()
                    qa_item["question"] = question_p.get_text(strip=True)

                answer_p = item.find("p", class_="qa-List_Txt-A")
                if answer_p:
                    answer_span = answer_p.find("span")
                    if answer_span:
                        answer_span.extract()
                    qa_item["answer"] = answer_p.get_text(strip=True)

                # Related cards live in a sibling div, not inside the item.
                relation_div = item.find_next_sibling("div", class_="relation")
                if relation_div:
                    relation_p = relation_div.find_all("p")
                    if len(relation_p) > 1:
                        qa_item["related_cards"] = relation_p[1].get_text(strip=True)

                qa_items.append(qa_item)

            card_info["qa_items"] = qa_items
        else:
            card_info["qa_raw_html"] = None
            card_info["qa_items"] = []
    except Exception as exc:  # noqa: BLE001
        print(f"  error parsing Q&A for {card_id}: {exc}")
        card_info["qa_raw_html"] = None
        card_info["qa_items"] = []

    return card_info


def fetch_cards(
    card_ids: list[str],
    download_images: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch every card, sleeping between requests.

    A card that raises is skipped with a warning rather than aborting the run — a single
    bad page should not cost a 2,500-card scrape.
    """
    all_cards: list[dict[str, Any]] = []
    total = len(card_ids)

    for index, card_id in enumerate(card_ids):
        try:
            all_cards.append(fetch_card(card_id, download_images=download_images))
        except Exception as exc:  # noqa: BLE001
            print(f"  error processing card {card_id}: {exc}")

        if on_progress:
            on_progress(index + 1, total, card_id)

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    return all_cards


def save_raw(cards: list[dict[str, Any]]) -> None:
    ensure_dirs()
    raw_html_file().write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_raw() -> list[dict[str, Any]]:
    path = raw_html_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
