"""Write the generated tool catalog into docs/mcp-contracts.md from the contracts.

Usage: python scripts/generate_catalog.py [--check]

--check exits 1 when the committed catalog differs from the contracts, so CI
catches documentation that drifted from the code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from irp.contracts.catalog import CATALOG  # noqa: E402
from irp.identity import PRODUCT  # noqa: E402

DOC = REPO / "docs" / "mcp-contracts.md"
BEGIN = (
    "<!-- BEGIN GENERATED CATALOG: edit src/irp/contracts, then run scripts/generate_catalog.py -->"
)
END = "<!-- END GENERATED CATALOG -->"


def _type(schema: dict[str, Any], defs: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if "anyOf" in schema:
        return " or ".join(_type(option, defs) for option in schema["anyOf"])
    if "enum" in schema:
        return " \\| ".join(json.dumps(v) for v in schema["enum"])
    if "const" in schema:
        return json.dumps(schema["const"])
    kind = schema.get("type", "any")
    if kind == "array":
        return f"list of {_type(schema.get('items', {}), defs)}"
    return str(kind)


def _fields_table(schema: dict[str, Any]) -> list[str]:
    defs = schema.get("$defs", {})
    required = set(schema.get("required", []))
    rows = [
        "| Field | Type | Required | Default | Description |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, field in schema["properties"].items():
        default = "" if name in required else json.dumps(field.get("default"))
        description = (field.get("description") or "").replace("|", "\\|")
        rows.append(
            f"| `{name}` | {_type(field, defs)} | {'yes' if name in required else 'no'} | {default} | {description} |"
        )
    return rows


def render() -> str:
    lines = [
        BEGIN,
        "",
        f"{len(CATALOG)} tools, in workflow order. Every tool takes `study`, an absolute path.",
        "",
    ]
    lines += ["| Stage | Tool | What it does | Effects |", "| --- | --- | --- | --- |"]
    for contract in CATALOG:
        lines.append(
            f"| {contract.stage} | [`{contract.name}`](#{contract.name}) | {contract.summary} | {', '.join(contract.effects)} |"
        )
    for contract in CATALOG:
        schema = contract.input_model.model_json_schema()
        hints = "read-only" if contract.read_only else "writes evidence"
        if contract.open_world:
            hints += ", reaches outside the study"
        lines += [
            "",
            f"### {contract.name}",
            "",
            f"{contract.description}",
            "",
            f"_{contract.title}; {hints}._",
            "",
        ]
        lines += _fields_table(schema)
        defs = schema.get("$defs", {})
        for name, nested in defs.items():
            lines += ["", f"`{name}` fields:", ""]
            lines += _fields_table(nested)
    # No version here on purpose: the catalog is committed, but the version is
    # bumped on every release, so embedding it would make the committed copy
    # stale at release time and fail CI. The catalog tracks the contracts, not the version.
    lines += [
        "",
        f"Generated from the {PRODUCT.package_name} tool contracts by scripts/generate_catalog.py.",
        "",
        END,
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    text = DOC.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        print(f"{DOC} has no generated-catalog markers.", file=sys.stderr)
        return 1
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    updated = head + render() + tail
    if "--check" in argv:
        if updated != text:
            print(
                "docs/mcp-contracts.md is stale; run: python scripts/generate_catalog.py",
                file=sys.stderr,
            )
            return 1
        return 0
    DOC.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
