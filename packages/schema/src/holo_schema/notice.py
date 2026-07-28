"""Rules notices — the things the official site publishes into the card list that are
not cards.

The site's card list is not exclusively cards. Id 2459 (デッキ構築ルール) is a Selection
Cup **format-legality notice**: it states which products are legal for that event and
how card-number matching works across reprints. It has a card's envelope — id, name,
image, `card_sets`, ability text — and no card number, no rarity, and the bare
`サポート` card type that no printed card has ever used.

Why a separate model rather than a widened `Card`:

- `Card.card_number` and `Card.rarity_code` are `NOT NULL` in the D1 schema and correct
  for all 2,463 real cards. Admitting a notice into `cards` means dropping both
  constraints on a populated production table — which SQLite can only do by rebuilding
  it — to weaken an invariant that protects everything else. A scraper regression that
  stopped parsing rarity would then validate silently, which is the failure ADR 0001's
  strict contract exists to catch.
- A notice is not deck-addable, not filterable by colour or rarity, and not searchable
  as a card. Every one of those would need a special case at the consumer, and Phase 5's
  lesson (F-019) is that a rule no test exercises is a rule that quietly stops holding.
- The planned deck simulator wants to ask "is this deck legal for this format?". That
  question is answered by a notice record, not by a card row carrying two NULLs.

Why an R2 artifact rather than a D1 table: this is the `/api/filter-options` shape from
ADR 0004 — a handful of records, the same answer for every user until the next pipeline
run, never filtered or joined. D1 earns its place when a query needs an index; nothing
here does. It also means adding notices requires no migration against the live database.

Notices ride the *same* scrape and translate path as cards — they are fetched, extracted
and translated identically, and their prose lands in the same field-level cache. Only
storage and serving differ.
"""

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .annotations import FullText
from .enums import Locale

_STRICT = ConfigDict(extra="forbid")


class NoticeTranslation(BaseModel):
    """One locale's rendering of a notice.

    `body` is the notice's rules text — the same source field a card's `ability_text`
    comes from, so it translates through the existing cache with no new machinery.
    """

    model_config = _STRICT

    name: Annotated[str, FullText(weight=3.0)]
    body: Annotated[Optional[str], FullText()] = None


class Notice(BaseModel):
    """A non-card entry from the official card list.

    Deliberately a subset of `Card`'s envelope: the fields a notice genuinely has, and
    none of the ones it does not. There is no `card_number`, no `rarity_code` and no
    `card_type_code` — the type is what selected this model in the first place, so
    carrying it would be restating the tautology.
    """

    model_config = _STRICT

    # The scraper's own numeric-string id, same namespace as `Card.id`. Kept in one
    # namespace deliberately: `id` uniquely identifies an entry in the site's card list,
    # whether or not that entry is a card, and two id spaces that can collide would be
    # worse than one that cannot.
    id: str

    image_key: str
    source_image_url: str

    # Which products or events the notice governs, e.g.
    # "【使用可能カード】セレクションカップ". Same vocabulary as `Card.card_sets`, and
    # that shared vocabulary is the join: the notice explains the set value that the
    # 2,464-card refresh added to ~660 cards.
    card_sets: list[str] = Field(default_factory=list)

    translations: dict[Locale, NoticeTranslation]

    @model_validator(mode="after")
    def _source_locale_present(self) -> "Notice":
        """The source language must always be present — same rule as `Card`.

        A notice without `ja` cannot be re-translated or corrected, and its body is the
        only statement of a rule that affects deck legality. Shipping one with no source
        text would be shipping a rule nobody can check.
        """
        from .enums import SOURCE_LOCALE

        if SOURCE_LOCALE not in self.translations:
            raise ValueError(
                f"notice {self.id} is missing the source locale '{SOURCE_LOCALE}'"
            )
        return self


class NoticeCollection(BaseModel):
    """What `build` writes to `notices.json` and `publish` uploads to R2.

    Mirrors `CardCollection` — same `generated_at` / `schema_version` envelope — so a
    consumer that already reads one artifact needs no new conventions to read this one.
    """

    model_config = _STRICT

    generated_at: str
    schema_version: int = 1
    notices: list[Notice] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "NoticeCollection":
        seen: set[str] = set()
        for notice in self.notices:
            if notice.id in seen:
                raise ValueError(f"duplicate notice id: {notice.id}")
            seen.add(notice.id)
        return self
