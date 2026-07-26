"""Parse each card's raw HTML into structured data.

Ported from v1's `3-extract-card-info.py`. **The parsing logic below is verbatim.**

This is the file D3 is about. Every selector here (`div.info`, `div.sp.arts`,
`div.oshi.skill`, `p.ill-name`, `span.tokkou`) and every regex (the full-width-colon
card reference pattern, the `[ホロパワー：-N]` cost, the ideographic-space split between
an art's name and its damage) was arrived at by a year of running against the official
site and finding out what it actually emits. A rewrite's best case is "works exactly as
before"; its worst case is silently plausible wrong data.

Only file I/O and progress reporting were changed.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from bs4 import BeautifulSoup

from ..paths import ensure_dirs, structured_file


def parse_related_cards(related_cards_string: str) -> dict[str, Any]:
    """Parse a QA related-cards string into raw HTML plus card numbers.

    Handles both the Japanese full-width colon `[hBP08-003 ： FUWAMOCO]` and the ASCII
    colon used on the English pages.
    """
    if not related_cards_string:
        return {"raw_html": "", "card_number": []}

    card_pattern = r"\[([^：:]+)\s*[：:]\s*[^\]]+\]"
    card_matches = re.findall(card_pattern, related_cards_string)
    card_numbers = [card_number.strip() for card_number in card_matches]

    return {"raw_html": related_cards_string, "card_number": card_numbers}


def extract_structured_data(raw_html: str) -> dict[str, Any]:
    """Extract structured data from one card's detail HTML.

    Verbatim from v1. Do not tidy this without a card-by-card diff against the previous
    output — several branches exist for a handful of cards each.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    data: dict[str, Any] = {"info": {}}

    # --- Basic info: a series of <dl><dt>label</dt><dd>value</dd> pairs ---
    info_div = soup.find("div", class_="info")
    if info_div:
        dl_elements = info_div.find_all("dl")
        for dl in dl_elements:
            dt_elements = dl.find_all("dt")
            dd_elements = dl.find_all("dd")

            for i in range(len(dt_elements)):
                if i < len(dd_elements):
                    key = dt_elements[i].text.strip()

                    # A dd holds one of three things: images (colour, baton touch),
                    # links (tags), or plain text. Each is shaped differently.
                    imgs = dd_elements[i].find_all("img")
                    if imgs:
                        value_array = []
                        img_data = []
                        for img in imgs:
                            img_info = {
                                "alt": img.get("alt", ""),
                                "src": img.get("src", ""),
                            }
                            img_data.append(img_info)

                        value_array.append(
                            {
                                "count": len(imgs),
                                "images": img_data,
                                "raw_html": str(dd_elements[i]),
                            }
                        )

                        data["info"][key] = value_array
                    elif dd_elements[i].find_all("a"):
                        value_array = []
                        for tag_link in dd_elements[i].find_all("a"):
                            value_array.append(
                                {
                                    "name": tag_link.text.strip(),
                                    "href": tag_link.get("href", ""),
                                }
                            )

                        data["info"][key] = value_array
                    else:
                        data["info"][key] = dd_elements[i].text.strip()

                    # Card sets get extra treatment: one card can appear in many sets,
                    # newline-separated in a single dd.
                    if key == "収録商品" or key == "Card Set":
                        card_set_text = dd_elements[i].text.strip()
                        card_set_raw_html = str(dd_elements[i])

                        if "\n" in card_set_text:
                            card_set_values = [
                                item.strip()
                                for item in card_set_text.split("\n")
                                if item.strip()
                            ]
                        else:
                            card_set_values = [card_set_text] if card_set_text else []

                        data["card_set"] = {
                            "raw_html": card_set_raw_html,
                            "count": len(card_set_values),
                            "value": card_set_values,
                        }

    # --- Arts ---
    arts_divs = soup.find_all("div", class_="sp arts")
    if arts_divs:
        arts_list = []
        for arts_div in arts_divs:
            arts_data: dict[str, Any] = {}
            p_tags = arts_div.find_all("p")

            if len(p_tags) > 1:
                arts_content = p_tags[1]

                arts_data["full_text"] = arts_content.text.strip()

                cost_icons = []
                for img in arts_content.find_all("img"):
                    cost_icons.append(
                        {"alt": img.get("alt", ""), "src": img.get("src", "")}
                    )

                arts_data["cost_icons"] = cost_icons
                arts_data["raw_html"] = str(arts_content)

                span = arts_content.find("span")
                if span:
                    span_text = span.text.strip()

                    # Name and damage are separated by an ideographic space (U+3000).
                    parts = re.split(r"　", span_text)

                    if len(parts) > 0:
                        arts_data["name"] = parts[0].strip()

                    if len(parts) > 1:
                        damage_part = parts[1].strip()
                        damage_match = re.search(r"(\d+)([+]?)", damage_part)
                        if damage_match:
                            arts_data["damage"] = damage_match.group(0)

                    # 特攻 — bonus damage against a specific colour.
                    tokkou_span = span.find("span", class_="tokkou")
                    if tokkou_span:
                        tokkou_imgs = tokkou_span.find_all("img")
                        if tokkou_imgs:
                            tokkou_data = []
                            for img in tokkou_imgs:
                                tokkou_data.append(
                                    {
                                        "alt": img.get("alt", ""),
                                        "src": img.get("src", ""),
                                    }
                                )
                            arts_data["tokkou"] = tokkou_data

                # Effect text is everything that is not the name span.
                effect_text = ""
                for content in arts_content.contents:
                    if content.name != "span":
                        effect_text += str(content)

                if effect_text.strip():
                    effect_soup = BeautifulSoup(effect_text, "html.parser")
                    arts_data["effect"] = effect_soup.text.strip()

            arts_list.append(arts_data)

        if arts_list:
            data["arts"] = arts_list

    # --- Extra ---
    extra_div = soup.find("div", class_="extra")
    if extra_div:
        p_tags = extra_div.find_all("p")
        if len(p_tags) > 1:
            data["extra"] = p_tags[1].text.strip()

    # --- Keyword ability ---
    keyword_div = soup.find("div", class_="keyword")
    if keyword_div:
        p_tags = keyword_div.find_all("p")
        if len(p_tags) > 1:
            keyword_data: dict[str, Any] = {}
            keyword_content = p_tags[1]

            keyword_data["raw_html"] = str(keyword_content)
            keyword_data["full_text"] = keyword_content.text.strip()

            img = keyword_content.find("img")
            if img:
                keyword_data["icon"] = {
                    "alt": img.get("alt", ""),
                    "src": img.get("src", ""),
                }

            span = keyword_content.find("span")
            if span:
                keyword_name = span.text.strip()
                keyword_data["name"] = keyword_name

                effect_text = keyword_content.text.replace(span.text, "", 1).strip()
                keyword_data["effect"] = effect_text

            data["keyword"] = keyword_data

    # --- Oshi skill and SP oshi skill: same shape, two divs ---
    for div_classes, output_key in (
        ("oshi skill", "oshi_skill"),
        ("sp skill", "sp_oshi_skill"),
    ):
        skill_div = soup.find("div", class_=div_classes)
        if not skill_div:
            continue

        skill_p = skill_div.find_all("p")
        if len(skill_p) <= 1:
            continue

        skill_data: dict[str, Any] = {}
        skill_content = skill_p[1]
        skill_text = skill_content.text.strip()

        skill_data["full_text"] = skill_text
        skill_data["raw_html"] = str(skill_content)

        skill_span = skill_content.find("span")
        if skill_span:
            skill_name = skill_span.text.strip()
            skill_data["name"] = skill_name

            cost_match = re.search(r"\[ホロパワー：(-\d+)\]", skill_text)
            if cost_match:
                skill_data["cost"] = cost_match.group(1)

            timing_match = re.search(r"\[(ターンに1回|ゲームに1回)\]", skill_text)
            if timing_match:
                skill_data["timing"] = timing_match.group(1)

            parts = skill_text.split(skill_name)
            if len(parts) > 1:
                skill_data["effect"] = parts[1].strip()

        data[output_key] = skill_data

    # --- Illustrator and card number ---
    illustrator_div = soup.find("div", class_="illustrator")
    if illustrator_div:
        ill_name_p = illustrator_div.find("p", class_="ill-name")
        if ill_name_p:
            span = ill_name_p.find("span")
            if span:
                data["illustrator"] = span.text.strip()

        number_p = illustrator_div.find("p", class_="number")
        if number_p:
            span = number_p.find("span")
            if span:
                data["card_number"] = span.text.strip()

    return data


def extract_cards(
    raw_cards: list[dict[str, Any]],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Run `extract_structured_data` over every scraped card."""
    structured_cards: list[dict[str, Any]] = []
    total = len(raw_cards)

    for index, card in enumerate(raw_cards):
        processed_card: dict[str, Any] = {}

        for field in ("id", "name", "image_url", "image_filename"):
            if field in card:
                processed_card[field] = card[field]

        if "qa_items" in card:
            processed_qa_items = []
            for qa_item in card["qa_items"]:
                processed_qa = qa_item.copy()
                if "related_cards" in qa_item:
                    processed_qa["related_cards"] = parse_related_cards(
                        qa_item["related_cards"]
                    )
                processed_qa_items.append(processed_qa)
            processed_card["qa_items"] = processed_qa_items

        if "raw_html" in card:
            processed_card.update(extract_structured_data(card["raw_html"]))

        structured_cards.append(processed_card)

        if on_progress:
            on_progress(index + 1, total)

    return structured_cards


def save_structured(cards: list[dict[str, Any]]) -> None:
    ensure_dirs()
    structured_file().write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_structured() -> list[dict[str, Any]]:
    path = structured_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
