"""Fetch the list of card ids from the official site.

Ported from v1's `1-grab-card-id-list.py`. The scraping logic — how `max_page` is dug
out of an inline `var max_page = 57;` script, and how ids are pulled from `?id=` hrefs —
is preserved exactly. Only the file I/O and progress reporting changed.
"""

from __future__ import annotations

import json
from typing import Callable

import requests
from bs4 import BeautifulSoup

from ..paths import card_ids_file, ensure_dirs

CARD_SEARCH_URL = "https://hololive-official-cardgame.com/cardlist/cardsearch"
CARD_LIST_PAGE_URL = "https://hololive-official-cardgame.com/cardlist/cardsearch_ex?page="


def get_max_page(url: str = CARD_SEARCH_URL) -> int:
    """Read the page count out of the card search page's inline script.

    The site renders `var max_page = 57;` into a <script> tag rather than exposing it in
    the markup, so this parses the assignment out of the script body.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    scripts = soup.find_all("script")
    max_page = 1

    for script in scripts:
        if script.string and "max_page" in script.string:
            script_content = script.string
            max_page_line = [
                line for line in script_content.split("\n") if "max_page" in line
            ]
            if max_page_line:
                max_page = int(max_page_line[0].split("=")[1].strip("; "))
                break

    return max_page


def fetch_card_ids(
    on_progress: Callable[[int, int], None] | None = None,
) -> list[str]:
    """Walk every card-list page and collect the card ids.

    Args:
        on_progress: called with (page, max_page) after each page.

    Returns:
        Card ids in site order. Not deduplicated — v1 did not deduplicate either, and
        the ids are unique in practice.
    """
    max_page = get_max_page()
    card_ids: list[str] = []

    for page in range(1, max_page + 1):
        response = requests.get(CARD_LIST_PAGE_URL + str(page))
        soup = BeautifulSoup(response.text, "html.parser")
        for card in soup.find_all("a"):
            href = card.get("href")
            if href and "?id=" in href:
                id_part = href.split("?id=")[1]
                if "&" in id_part:
                    card_id = id_part.split("&")[0]
                else:
                    card_id = id_part
                card_ids.append(card_id)

        if on_progress:
            on_progress(page, max_page)

    return card_ids


def save_card_ids(card_ids: list[str]) -> None:
    ensure_dirs()
    card_ids_file().write_text(
        json.dumps(card_ids, indent=2) + "\n", encoding="utf-8"
    )


def load_card_ids() -> list[str]:
    path = card_ids_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
