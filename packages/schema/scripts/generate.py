"""Generate JSON Schema and TypeScript from the pydantic models.

This is the script that makes "the contract is defined exactly once" true. Run it after
touching any model:

    make generate       # regenerate and write
    make check          # verify the committed output is current (fails if stale)

Outputs, all committed to git:

    json-schema/card.schema.json            the canonical card collection
    json-schema/localized-card.schema.json  the API response shape
    dist/card.d.ts                          TypeScript types
    dist/enums.ts                           runtime enum arrays for filter UIs

Committing generated output is a deliberate trade (see docs/adr/0001): it means a
frontend contributor can clone, `npm install`, and get types without a Python
toolchain. `--check` is what stops the committed copy going stale.

Adding a model: append to `MODELS` below. Nothing else changes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from holo_schema import (
    BLOOM_LEVEL_VALUES,
    CARD_TYPE_VALUES,
    COLOR_VALUES,
    DEFAULT_LOCALE,
    FUSED_COLORS,
    KEYWORD_TYPE_VALUES,
    LOCALE_VALUES,
    MAIN_CARD_TYPES,
    MAX_BATCH,
    OSHI_CARD_TYPES,
    RARITY_VALUES,
    SCHEMA_VERSION,
    SOURCE_LOCALE,
    TIMING_VALUES,
    YELL_CARD_TYPES,
    CardCollection,
    LocalizedCard,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PACKAGE_ROOT / "json-schema"
DIST_DIR = PACKAGE_ROOT / "dist"

# The models to generate from. Add here; the rest is automatic.
MODELS: list[tuple[type[BaseModel], str]] = [
    (CardCollection, "card"),
    (LocalizedCard, "localized-card"),
]

JSTT_VERSION = "15.0.4"

BANNER = """/**
 * DO NOT EDIT — generated from the pydantic models in packages/schema/src/holo_schema/.
 *
 * Regenerate with `make generate`. `make check` fails if this file is stale.
 */
"""


def strip_nullable(node: Any) -> Any:
    """Rewrite `anyOf: [T, null]` into plain `T`.

    Pydantic renders `Optional[int]` as `{"anyOf": [{"type":"integer"}, {"type":"null"}]}`,
    which generates `hp?: number | null` in TypeScript. That is wrong for this dataset:
    an absent field is *omitted* from the JSON, never present-and-null. Verified by
    census over all 2,448 cards — zero null values, only missing keys.

    Combined with `exclude_none=True` at serialisation time, this makes the TypeScript
    say exactly what the data does: `hp?: number`.
    """
    if isinstance(node, dict):
        any_of = node.get("anyOf")
        if isinstance(any_of, list) and {"type": "null"} in any_of:
            remaining = [entry for entry in any_of if entry != {"type": "null"}]
            if len(remaining) == 1:
                node.pop("anyOf")
                node.pop("default", None)
                node.update(remaining[0])
        return {key: strip_nullable(value) for key, value in node.items()}
    if isinstance(node, list):
        return [strip_nullable(item) for item in node]
    return node


def build_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Produce the cleaned JSON Schema for one model."""
    schema = strip_nullable(model.model_json_schema())
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema


def render_enums() -> str:
    """Emit the enum types and their runtime values as TypeScript.

    Both the `type` and the `const` are emitted here, from the same Python tuple, so
    they cannot disagree. The types are *not* imported from `card.d.ts`: pydantic
    inlines `Literal` unions at their use site rather than naming them, so there is no
    `ColorCode` type over there to import.

    v1 kept a hand-written copy of these values in `constants/card-data.ts`, which had
    drifted from the data in two ways — a missing "HR" rarity (making 24 cards
    unfilterable in the UI) and bloom levels spelled "1st"/"2nd" against the data's
    "first"/"second". Generating them means that class of bug cannot recur.
    """
    def as_type(name: str, values: tuple[str, ...]) -> str:
        body = " | ".join(f'"{value}"' for value in values)
        return f"export type {name} = {body};"

    def as_array(name: str, values: tuple[str, ...], ts_type: str) -> str:
        body = ", ".join(f'"{value}"' for value in values)
        return f"export const {name}: readonly {ts_type}[] = [{body}] as const;"

    fused = "\n".join(
        f'  {key}: [{", ".join(chr(34) + c + chr(34) for c in parts)}],'
        for key, parts in FUSED_COLORS.items()
    )

    return "\n".join(
        [
            BANNER,
            "// --- Enum types ---",
            "",
            as_type("Locale", LOCALE_VALUES),
            as_type("CardTypeCode", CARD_TYPE_VALUES),
            as_type("RarityCode", RARITY_VALUES),
            as_type("ColorCode", COLOR_VALUES),
            as_type("BloomLevelCode", BLOOM_LEVEL_VALUES),
            as_type("KeywordTypeCode", KEYWORD_TYPE_VALUES),
            as_type("TimingCode", TIMING_VALUES),
            "",
            "// --- Enum values, for filter UIs and validation ---",
            "",
            as_array("LOCALES", LOCALE_VALUES, "Locale"),
            as_array("CARD_TYPES", CARD_TYPE_VALUES, "CardTypeCode"),
            as_array("RARITIES", RARITY_VALUES, "RarityCode"),
            as_array("COLORS", COLOR_VALUES, "ColorCode"),
            as_array("BLOOM_LEVELS", BLOOM_LEVEL_VALUES, "BloomLevelCode"),
            as_array("KEYWORD_TYPES", KEYWORD_TYPE_VALUES, "KeywordTypeCode"),
            as_array("TIMINGS", TIMING_VALUES, "TimingCode"),
            "",
            "// --- Domain constants ---",
            "",
            f'export const SOURCE_LOCALE: Locale = "{SOURCE_LOCALE}";',
            f'export const DEFAULT_LOCALE: Locale = "{DEFAULT_LOCALE}";',
            f"export const SCHEMA_VERSION = {SCHEMA_VERSION};",
            "",
            "/** Most ids or card numbers one batch request may carry. The Worker",
            " *  400s above this; the site chunks to fit. A legal deck (1 + 50 + 20)",
            " *  already exceeds it, so the two must agree. */",
            f"export const MAX_BATCH = {MAX_BATCH};",
            "",
            "// --- Deck sections (see architecture review Candidate 03) ---",
            "",
            as_array("OSHI_CARD_TYPES", OSHI_CARD_TYPES, "CardTypeCode"),
            as_array("MAIN_CARD_TYPES", MAIN_CARD_TYPES, "CardTypeCode"),
            as_array("YELL_CARD_TYPES", YELL_CARD_TYPES, "CardTypeCode"),
            "",
            "/**",
            " * Fused dual-colour symbols and the colours they contain.",
            " *",
            " * `blue_red` is a single printed symbol, not shorthand for `[blue, red]` —",
            " * the card bears one icon. Use this when filtering so a \"blue\" filter also",
            " * matches `blue_red`, but never to rewrite the stored value.",
            " */",
            "export const FUSED_COLORS: Partial<Record<ColorCode, readonly ColorCode[]>> = {",
            fused,
            "};",
            "",
        ]
    )


def generate_typescript(schema_path: Path, out_path: Path) -> str:
    """Run json-schema-to-typescript over one schema file."""
    result = subprocess.run(
        [
            "npx",
            "--yes",
            f"json-schema-to-typescript@{JSTT_VERSION}",
            str(schema_path),
            "--unreachableDefinitions",
            "--additionalProperties",
            "false",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"json-schema-to-typescript failed for {schema_path.name}:\n{result.stderr}"
        )
    # Replace the tool's own banner with ours, so the regenerate instruction is right.
    body = result.stdout
    if body.startswith("/* eslint-disable */"):
        body = body.split("*/", 1)[1].lstrip("\n")
    return BANNER + "/* eslint-disable */\n\n" + body


def collect_outputs() -> dict[Path, str]:
    """Build every generated artifact in memory, keyed by destination path.

    Each model gets its own `.d.ts`. They are deliberately NOT concatenated: both
    schemas declare `Arts`, `QaItem` and `RelatedCards`, and `Arts` means different
    things in each (`Art[]` canonically, `LocalizedArt[]` in the API response). One
    merged file would either be a TS2300 redeclaration error or a silent wrong pick.

    `index.d.ts` re-exports both under distinct names so consumers have one import
    path.
    """
    outputs: dict[Path, str] = {}

    for model, slug in MODELS:
        schema = build_schema(model)
        schema_path = SCHEMA_DIR / f"{slug}.schema.json"
        outputs[schema_path] = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"

    # TypeScript generation needs the schema files on disk, so write them first.
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")

    for _model, slug in MODELS:
        ts = generate_typescript(SCHEMA_DIR / f"{slug}.schema.json", DIST_DIR)
        outputs[DIST_DIR / f"{slug}.d.ts"] = ts

    outputs[DIST_DIR / "index.d.ts"] = "\n".join(
        [
            BANNER,
            "// The canonical contract — what the pipeline writes and D1 stores.",
            'export type {',
            "  Card,",
            "  CardCollection,",
            "  Art,",
            "  Keyword,",
            "  OshiSkill,",
            "  Translation,",
            "  Translations,",
            "  TranslatedArt,",
            "  TranslatedKeyword,",
            "  TranslatedOshiSkill,",
            "  QaItem,",
            "  RelatedCards,",
            "} from './card.d.ts';",
            "",
            "// The API response shape — one card, one locale, flattened.",
            'export type {',
            "  LocalizedCard,",
            "  LocalizedArt,",
            "  LocalizedKeyword,",
            "  LocalizedOshiSkill,",
            "} from './localized-card.d.ts';",
            "",
            "// Enum types and their runtime values.",
            "export * from './enums.ts';",
            "",
        ]
    )
    outputs[DIST_DIR / "enums.ts"] = render_enums()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed output is current; exit 1 if stale. Writes nothing.",
    )
    args = parser.parse_args()

    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    outputs = collect_outputs()

    if args.check:
        stale: list[Path] = []
        for path, content in outputs.items():
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path)
        if stale:
            print("Generated files are out of date:", file=sys.stderr)
            for path in sorted(stale):
                print(f"  {path.relative_to(PACKAGE_ROOT.parent.parent)}", file=sys.stderr)
            print("\nRun `make generate` and commit the result.", file=sys.stderr)
            return 1
        print(f"✓ {len(outputs)} generated files are current")
        return 0

    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path.relative_to(PACKAGE_ROOT.parent.parent)}")
    print(f"✓ generated {len(outputs)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
