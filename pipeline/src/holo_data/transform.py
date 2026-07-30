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

**Unmapped values are reported here, because here is where the evidence dies.** A
mapping miss replaces what the site printed with `UNMAPPED` and throws the original
away, so no later stage can name it: `build` reports the values it *accepts*, and the
site's actual string is gone. `transform_cards` returns an `UnmappedReport` alongside
the cards so the operator learns what to add to `mappings.py` (issue #19).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from holo_schema.enums import NON_CARD_TYPES

from . import mappings
from .paths import ensure_dirs, i18n_file

# What every mapping table writes when it has no entry for a source value.
#
# Not a legal value in any of the four enums, so `build` fails on it — which is the
# point. It exists to occupy a required field so validation has something to reject,
# rather than to be shipped.
UNMAPPED = "unknown"


@dataclass
class UnmappedReport:
    """Source values no mapping table covered, and the cards that carried them.

    **This is the only place the offending string still exists.** The mapping tables
    substitute `UNMAPPED` and discard what the site actually printed, so by the time
    `build` validates, the error it can raise names the values we *accept* — "Input
    should be 'debut', 'first', 'second' or 'spot'" — and never the one that caused it.
    An operator hitting that got a blocked build, a card id, and no way to learn what to
    add to `mappings.py` short of opening the card's page by hand.

    Collected here because this is the moment the evidence is destroyed. See issue #19.
    """

    # field name -> source value -> card ids that carried it
    values: dict[str, dict[str, list[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )

    def record(self, field_name: str, source: str, card_id: str) -> None:
        self.values[field_name][source].append(card_id)

    @property
    def is_empty(self) -> bool:
        return not self.values

    @property
    def card_count(self) -> int:
        """Distinct cards affected — a markup change hits many, a new type hits one."""
        ids = {
            card_id
            for sources in self.values.values()
            for card_ids in sources.values()
            for card_id in card_ids
        }
        return len(ids)

    def rows(self) -> list[tuple[str, str, list[str]]]:
        """`(field, source value, card ids)`, most-affected first then alphabetical."""
        return sorted(
            (
                (field_name, source, card_ids)
                for field_name, sources in self.values.items()
                for source, card_ids in sources.items()
            ),
            key=lambda row: (-len(row[2]), row[0], row[1]),
        )


def _mapped(
    table: dict[str, str],
    source: Any,
    field_name: str,
    card: dict[str, Any],
    report: UnmappedReport | None,
    default: str | None = UNMAPPED,
) -> str | None:
    """Look a source value up, recording it if the table has no entry.

    `default=None` is for the lookups whose caller *skips* the value rather than writing
    a sentinel — a different failure (silent omission rather than a blocked build), but
    the same missing mapping, so it belongs in the same report.
    """
    code = table.get(source) if isinstance(source, str) else None
    if code is None and report is not None and isinstance(source, str) and source:
        report.record(field_name, source, str(card.get("id", "")))
    return code if code is not None else default


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


def _colors(
    card: dict[str, Any], report: UnmappedReport | None = None
) -> list[str] | None:
    """Colour codes, from the alt text of the colour icons."""
    field = get_field(card, mappings.LABELS["color"])
    if not field:
        return None

    def code(source: Any) -> str | None:
        return _mapped(mappings.COLOR, source, "color", card, report)

    if isinstance(field, list):
        codes = []
        for entry in field:
            if isinstance(entry, dict) and "images" in entry:
                for img in entry["images"]:
                    if "alt" in img:
                        codes.append(code(img["alt"]))
        return codes or None

    if isinstance(field, dict):
        if "value" in field:
            return [code(field["value"])]
        if "images" in field:
            for img in field["images"]:
                if "alt" in img:
                    return [code(img["alt"])]
        return None

    if isinstance(field, str):
        return [code(field)]

    return None


def _baton_touch(
    card: dict[str, Any], report: UnmappedReport | None = None
) -> tuple[int | None, list[str] | None]:
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
                        types.append(
                            _mapped(
                                mappings.COLOR, img["alt"], "baton_touch", card, report
                            )
                        )
        return total or None, types or None

    if isinstance(field, dict) and "count" in field:
        return field["count"], None

    return None, None


def _arts(
    card: dict[str, Any], report: UnmappedReport | None = None
) -> tuple[list[dict], list[dict]]:
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
            # v1 also emitted `cost_count = len(cost_icons)` — the unfiltered list — so it
            # read one high on exactly the 482 arts with a 特攻 icon. Nothing ever read it,
            # and `len(cost_types)` is the real count, so v2 does not emit it at all
            # (F-002).
            cost_types = []
            for icon in real_costs:
                if "alt" in icon:
                    cost_types.append(
                        _mapped(
                            mappings.COLOR, icon["alt"], "arts.cost_types", card, report
                        )
                    )
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
                colour = _mapped(
                    mappings.COLOR,
                    alt.split("+")[0].strip(),
                    "arts.special_targets",
                    card,
                    report,
                    default=None,
                )
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


def _skill(
    card: dict[str, Any], key: str, report: UnmappedReport | None = None
) -> tuple[dict | None, dict | None]:
    skill = card.get(key)
    if not isinstance(skill, dict):
        return None, None

    base: dict[str, Any] = {}
    timing = skill.get("timing")
    if timing:
        # Unlike the four enums above this one *omits* rather than substituting, so an
        # unmapped timing produces a valid card with no `timing_code` — it ships, and
        # the site renders a skill with no timing badge. Silent by construction, which
        # is why it is reported here even though it never blocks a build.
        code = _mapped(mappings.TIMING, timing, f"{key}.timing", card, report, default=None)
        if code:
            base["timing_code"] = code

    translation: dict[str, Any] = {}
    for field in ("name", "effect", "timing"):
        if skill.get(field):
            translation[field] = skill[field]

    return (base or None), (translation or None)


def to_card(
    card: dict[str, Any], report: UnmappedReport | None = None
) -> dict[str, Any]:
    """Convert one structured card into contract shape, JP translation only.

    Pass an `UnmappedReport` to collect the source values no mapping covered. It is
    optional so a caller that only wants the card — every test here, and `to_notice` —
    need not carry one, but `transform_cards` always does: the report is the only record
    of what the site printed, and this function is where that string is discarded.
    """
    out: dict[str, Any] = {"id": card.get("id", "")}
    translation: dict[str, Any] = {}

    # The site renders a missing card number as the literal string "null" inside the
    # number span (id 2459), not as an empty element. Storing that verbatim would put a
    # card_number of "null" in an indexed column and in the full-text index, where it
    # would match searches for the word. Dropped here so the contract sees the field as
    # genuinely absent, which is what `_card_fields_present` reasons about.
    card_number = get_field(card, mappings.LABELS["card_number"])
    if card_number and card_number != "null":
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
        out["card_type_code"] = _mapped(
            mappings.CARD_TYPE, card_type, "card_type", card, report
        )

    colors = _colors(card, report)
    if colors:
        out["color_codes"] = colors

    bloom = get_field(card, mappings.LABELS["bloom_level"])
    if bloom:
        out["bloom_level_code"] = _mapped(
            mappings.BLOOM_LEVEL, bloom, "bloom_level", card, report
        )

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

    baton_count, baton_types = _baton_touch(card, report)
    if baton_count is not None:
        out["baton_touch_count"] = baton_count
    if baton_types:
        out["baton_touch_types"] = baton_types

    base_arts, translated_arts = _arts(card, report)
    if base_arts:
        out["arts"] = base_arts
    if any(translated_arts):
        translation["arts"] = translated_arts

    keyword = card.get("keyword")
    if isinstance(keyword, dict):
        # The keyword *type* is the icon's alt text ("コラボエフェクト"); `name` is the
        # ability's own title ("レッツダンス！"). Reading `name` here yields no type at
        # all — it cost 1,124 cards their keyword on the first run.
        #
        # Omits rather than substituting, like the skill timing above: an unmapped
        # keyword type drops the whole keyword and the card ships without it. That is
        # the exact shape of the 1,124-card bug, so it is reported even though nothing
        # blocks on it.
        icon = keyword.get("icon")
        type_name = icon.get("alt") if isinstance(icon, dict) else None
        type_code = (
            _mapped(
                mappings.KEYWORD_TYPE, type_name, "keyword.type", card, report,
                default=None,
            )
            if type_name
            else None
        )
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
        base, skill_translation = _skill(card, source_key, report)
        if base:
            out[out_key] = base
        if skill_translation:
            translation[out_key] = skill_translation

    qa_items = card.get("qa_items")
    if isinstance(qa_items, list) and qa_items:
        translation["qa_items"] = qa_items

    out["translations"] = {"ja": translation}
    return out


def is_notice(entry: dict[str, Any]) -> bool:
    """Is this entry a rules notice rather than a card?

    Keyed on `card_type_code` so there is exactly one place that decides, and both
    `build` and the tests ask the same question. See `holo_schema.notice`.
    """
    return entry.get("card_type_code") in NON_CARD_TYPES


def to_notice(entry: dict[str, Any]) -> dict[str, Any]:
    """Project a card-shaped entry into `Notice` shape.

    Called at *build* time, not scrape time. Everything upstream — fetch, extract,
    transform, translate — treats a notice exactly like a card, which is the point: the
    notice's prose is `ability_text`, already a translatable scalar, so it flows through
    the field-level cache with no new machinery and no second code path to keep in sync.

    The remap is small on purpose. `ability_text` becomes `body` because on a notice the
    text is not a card's rules text but the notice itself; the card-only fields (number,
    rarity, colour, HP, arts, …) are dropped rather than carried as nulls.
    """
    translations: dict[str, Any] = {}
    for locale, translation in (entry.get("translations") or {}).items():
        projected: dict[str, Any] = {}
        if translation.get("name"):
            projected["name"] = translation["name"]
        # A notice's text arrives as `ability_text` — it is what the site puts under
        # 能力テキスト. `extra` is checked too so a site change that moves the prose does
        # not silently produce a bodyless notice.
        body = translation.get("ability_text") or translation.get("extra")
        if body:
            projected["body"] = body
        if projected:
            translations[locale] = projected

    return {
        "id": entry["id"],
        "image_key": entry.get("image_key", ""),
        "source_image_url": entry.get("source_image_url", ""),
        "card_sets": entry.get("card_sets") or [],
        "translations": translations,
    }


def transform_cards(
    structured: list[dict[str, Any]],
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[dict[str, Any]], UnmappedReport]:
    """Transform every scraped entry, notices included.

    Notices stay in this list and in `cards_i18n.json`. They are split out at build
    time by `is_notice`, so the translate step sees one homogeneous set of entries and
    needs no knowledge that notices exist.

    Returns the cards **and** the report of source values no mapping covered. The report
    is not optional: this is the only point in the pipeline where those strings exist,
    and every downstream error can name only the values we accept (issue #19).
    """
    cards = []
    report = UnmappedReport()
    total = len(structured)
    for index, card in enumerate(structured):
        cards.append(to_card(card, report))
        if on_progress:
            on_progress(index + 1, total)
    return cards, report


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
