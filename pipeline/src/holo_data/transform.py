"""Structured scrape output → the JP half of the card contract.

Ported from v1's `4-to-i18n.py`. The value mappings live in `mappings.py`; the shape
this produces is `holo_schema.Card` with only the `ja` translation filled in. The other
six locales are added by `translate`.

Two changes from v1, both following Phase 0 decisions:

- Output is snake_case, matching the contract (v1 emitted camelCase here and snake_case
  from the API, which is one of the drifts ADR 0001 removes).
- `image_key` replaces `imagePath`. v1 stored `card_images/default/x.png` — folder
  layout and file extension baked into the data. D9 stores the key and composes URLs, so
  changing CDN or format needs no reseed. The key is `{set}/{filename}` derived from the
  official image URL, which also disambiguates reprints that share a filename.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from . import mappings
from .paths import ensure_dirs, i18n_file


def get_field(card: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    """Look a field up by any of its known labels, top level first then `info`."""
    for key in keys:
        if key in card:
            return card[key]

    info = card.get("info")
    if isinstance(info, dict):
        for key in keys:
            if key in info:
                return info[key]

    return default


def image_key_from_url(image_url: str | None, filename: str | None) -> str | None:
    """Build the CDN-agnostic image key: `{set}/{filename-without-extension}`.

    The official site serves `/wp-content/images/cardlist/hBP08/hBP01-028_C_02.png`, so
    the set folder is available and is what makes reprints distinct. v1 dropped it and
    used a flat `default/` bucket, which collided: hBP03-044_SR.png exists under both
    hBP03 and hCO01 as two different cards. `CardCollection` rejects duplicate keys, so
    that collision cannot reach R2.
    """
    if not image_url and not filename:
        return None

    name = (filename or image_url.split("/")[-1]).rsplit(".", 1)[0]

    if image_url and "/cardlist/" in image_url:
        set_folder = image_url.split("/cardlist/")[1].split("/")[0]
        if set_folder:
            return f"{set_folder}/{name}"

    return f"default/{name}"


def _colors(card: dict[str, Any]) -> list[str] | None:
    """Colour codes, from the alt text of the colour icons."""
    field = get_field(card, mappings.LABELS["color"])
    if not field:
        return None

    if isinstance(field, list):
        codes = []
        for entry in field:
            if isinstance(entry, dict) and "images" in entry:
                for img in entry["images"]:
                    if "alt" in img:
                        codes.append(mappings.COLOR.get(img["alt"], "unknown"))
        return codes or None

    if isinstance(field, dict):
        if "value" in field:
            return [mappings.COLOR.get(field["value"], "unknown")]
        if "images" in field:
            for img in field["images"]:
                if "alt" in img:
                    return [mappings.COLOR.get(img["alt"], "unknown")]
        return None

    if isinstance(field, str):
        return [mappings.COLOR.get(field, "unknown")]

    return None


def _baton_touch(card: dict[str, Any]) -> tuple[int | None, list[str] | None]:
    field = get_field(card, mappings.LABELS["baton_touch"])
    if not field:
        return None, None

    if isinstance(field, list):
        total = 0
        types: list[str] = []
        for entry in field:
            if isinstance(entry, dict) and "count" in entry:
                total += entry["count"]
                for img in entry.get("images", []):
                    if "alt" in img:
                        types.append(mappings.COLOR.get(img["alt"], "unknown"))
        return total or None, types or None

    if isinstance(field, dict) and "count" in field:
        return field["count"], None

    return None, None


def _arts(card: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Split arts into the language-independent half and the JP-translated half.

    The contract keeps these apart (`Card.arts` vs `Translation.arts`) because costs and
    damage are the same in every language while names and effects are not. They pair by
    index.
    """
    field = get_field(card, mappings.LABELS["arts"])
    if not field or not isinstance(field, list):
        return [], []

    base: list[dict[str, Any]] = []
    translated: list[dict[str, Any]] = []

    for art in field:
        if not isinstance(art, dict):
            continue

        entry: dict[str, Any] = {}
        cost_icons = art.get("cost_icons")
        if isinstance(cost_icons, list):
            # The extractor collects every <img> in the arts block, which includes the
            # 特攻 bonus-damage icon (alt "紫+50", src tokkou_50_purple.png). That is not
            # a cost, so filter it out by filename — otherwise 482 cards get an
            # `unknown` cost type and fail validation.
            real_costs = [
                icon
                for icon in cost_icons
                if isinstance(icon, dict) and "tokkou_" not in icon.get("src", "")
            ]
            # v1 counted every icon here, including the 特攻 one, so `cost_count` could
            # exceed `len(cost_types)` by one. That is arguably a v1 bug — a bonus-damage
            # marker is not a cost — but it is the number the live site has shipped for a
            # year, and Phase 1's job is data equivalence, not correction. Revisit
            # separately if the count is ever used for anything but display.
            entry["cost_count"] = len(cost_icons)
            cost_types = []
            for icon in real_costs:
                if "alt" in icon:
                    cost_types.append(mappings.COLOR.get(icon["alt"], "unknown"))
            if cost_types:
                entry["cost_types"] = cost_types

        damage = art.get("damage")
        if damage:
            match = re.match(r"(\d+)(\+?)", str(damage))
            if match:
                entry["damage"] = int(match.group(1))
                if match.group(2) == "+":
                    entry["is_plus"] = True

        # 特攻 — bonus damage against particular colours.
        tokkou = art.get("tokkou")
        if isinstance(tokkou, list) and tokkou:
            targets: list[str] = []
            values: list[int] = []
            for icon in tokkou:
                alt = icon.get("alt", "") if isinstance(icon, dict) else ""
                src = icon.get("src", "") if isinstance(icon, dict) else ""
                # The alt text is the colour *and* the bonus ("紫+50"), so the bare
                # colour has to be split off before the mapping will match. Looking up
                # the whole string silently drops every special art.
                colour = mappings.COLOR.get(alt.split("+")[0].strip())
                # The bonus amount is in the filename, e.g. tokkou_50_blue.png.
                amount = re.search(r"tokkou_(\d+)", src)
                if colour and amount:
                    targets.append(colour)
                    values.append(int(amount.group(1)))
            if targets:
                entry["special_targets"] = targets
                entry["special_values"] = values

        base.append(entry)

        art_translation: dict[str, Any] = {}
        if art.get("name"):
            art_translation["name"] = art["name"]
        if art.get("effect"):
            art_translation["effect"] = art["effect"]
        translated.append(art_translation)

    return base, translated


def _skill(card: dict[str, Any], key: str) -> tuple[dict | None, dict | None]:
    skill = card.get(key)
    if not isinstance(skill, dict):
        return None, None

    base: dict[str, Any] = {}
    timing = skill.get("timing")
    if timing and timing in mappings.TIMING:
        base["timing_code"] = mappings.TIMING[timing]

    translation: dict[str, Any] = {}
    for field in ("name", "effect", "timing"):
        if skill.get(field):
            translation[field] = skill[field]

    return (base or None), (translation or None)


def to_card(card: dict[str, Any]) -> dict[str, Any]:
    """Convert one structured card into contract shape, JP translation only."""
    out: dict[str, Any] = {"id": card.get("id", "")}
    translation: dict[str, Any] = {}

    card_number = get_field(card, mappings.LABELS["card_number"])
    if card_number:
        out["card_number"] = card_number

    image_key = image_key_from_url(card.get("image_url"), card.get("image_filename"))
    if image_key:
        out["image_key"] = image_key
    if card.get("image_url"):
        out["source_image_url"] = card["image_url"]

    if card.get("name"):
        translation["name"] = card["name"]

    card_type = get_field(card, mappings.LABELS["card_type"])
    if card_type:
        out["card_type_code"] = mappings.CARD_TYPE.get(card_type, "unknown")

    colors = _colors(card)
    if colors:
        out["color_codes"] = colors

    bloom = get_field(card, mappings.LABELS["bloom_level"])
    if bloom:
        out["bloom_level_code"] = mappings.BLOOM_LEVEL.get(bloom, "unknown")

    for label_key, out_key in (("hp", "hp"), ("life", "life")):
        value = get_field(card, mappings.LABELS[label_key])
        if value:
            try:
                out[out_key] = int(value)
            except (ValueError, TypeError):
                pass

    tags_field = get_field(card, mappings.LABELS["tags"])
    if isinstance(tags_field, list) and tags_field:
        tags: list[str] = []
        tag_translations: list[str] = []
        for tag in tags_field:
            name = tag["name"] if isinstance(tag, dict) and "name" in tag else tag
            if isinstance(name, str):
                # The card-level tag is the stable identity; the translated one keeps
                # the display "#" prefix. Both are kept — they genuinely differ on 268
                # card-locale pairs. See ADR 0001.
                tags.append(name.replace("#", ""))
                tag_translations.append(name)
        if tags:
            out["tags"] = tags
            translation["tags"] = tag_translations

    rarity = get_field(card, mappings.LABELS["rarity"])
    if rarity:
        out["rarity_code"] = rarity

    card_set = card.get("card_set")
    if isinstance(card_set, dict) and isinstance(card_set.get("value"), list):
        if card_set["value"]:
            out["card_sets"] = card_set["value"]
    elif isinstance(card_set, str) and card_set:
        out["card_sets"] = [card_set]

    illustrator = get_field(card, mappings.LABELS["illustrator"])
    if illustrator:
        out["illustrator"] = illustrator

    for label_key, field in (("ability_text", "ability_text"), ("extra", "extra")):
        value = get_field(card, mappings.LABELS[label_key])
        if value:
            translation[field] = value

    baton_count, baton_types = _baton_touch(card)
    if baton_count is not None:
        out["baton_touch_count"] = baton_count
    if baton_types:
        out["baton_touch_types"] = baton_types

    base_arts, translated_arts = _arts(card)
    if base_arts:
        out["arts"] = base_arts
    if any(translated_arts):
        translation["arts"] = translated_arts

    keyword = card.get("keyword")
    if isinstance(keyword, dict):
        # The keyword *type* is the icon's alt text ("コラボエフェクト"); `name` is the
        # ability's own title ("レッツダンス！"). Reading `name` here yields no type at
        # all — it cost 1,124 cards their keyword on the first run.
        icon = keyword.get("icon")
        type_name = icon.get("alt") if isinstance(icon, dict) else None
        type_code = mappings.KEYWORD_TYPE.get(type_name) if type_name else None
        if type_code:
            out["keyword"] = {"type": type_name, "type_code": type_code}
            keyword_translation = {
                key: keyword[key] for key in ("name", "effect") if keyword.get(key)
            }
            if keyword_translation:
                translation["keyword"] = keyword_translation

    for source_key, out_key in (
        ("oshi_skill", "oshi_skill"),
        ("sp_oshi_skill", "sp_oshi_skill"),
    ):
        base, skill_translation = _skill(card, source_key)
        if base:
            out[out_key] = base
        if skill_translation:
            translation[out_key] = skill_translation

    qa_items = card.get("qa_items")
    if isinstance(qa_items, list) and qa_items:
        translation["qa_items"] = qa_items

    out["translations"] = {"ja": translation}
    return out


def transform_cards(
    structured: list[dict[str, Any]],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    cards = []
    total = len(structured)
    for index, card in enumerate(structured):
        cards.append(to_card(card))
        if on_progress:
            on_progress(index + 1, total)
    return cards


def save_i18n(cards: list[dict[str, Any]]) -> None:
    ensure_dirs()
    i18n_file().write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_i18n() -> list[dict[str, Any]]:
    path = i18n_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
