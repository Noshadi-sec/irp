"""CLI output: readable text on a terminal, JSON with --json. stdout carries results only."""

from __future__ import annotations

import json
import sys
from typing import Any

import typer

from irp.domain.errors import IRPError


def _scalar(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_text(value: Any, indent: int = 0) -> list[str]:
    """A YAML-like view: nested keys indented, short lists inline, multi-line text kept intact."""
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict) and item:
                lines.append(f"{pad}{key}:")
                lines.extend(render_text(item, indent + 1))
            elif isinstance(item, list) and item and any(isinstance(x, dict | list) for x in item):
                lines.append(f"{pad}{key}:")
                for element in item:
                    sub = render_text(element, indent + 2)
                    if sub:
                        first = sub[0].lstrip()
                        lines.append(f"{pad}  - {first}")
                        lines.extend(sub[1:])
            elif isinstance(item, list):
                lines.append(f"{pad}{key}: {', '.join(_scalar(x) for x in item) if item else '-'}")
            elif isinstance(item, str) and "\n" in item:
                lines.append(f"{pad}{key}: |")
                lines.extend(f"{pad}  {line}" for line in item.splitlines())
            else:
                lines.append(f"{pad}{key}: {_scalar(item)}")
    elif isinstance(value, list):
        for element in value:
            sub = render_text(element, indent + 1)
            if sub:
                lines.append(f"{pad}- {sub[0].lstrip()}")
                lines.extend(sub[1:])
    else:
        lines.append(f"{pad}{_scalar(value)}")
    return lines


def emit(result: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        indent = 2 if sys.stdout.isatty() else None
        typer.echo(json.dumps(result, indent=indent, ensure_ascii=False))
    else:
        typer.echo("\n".join(render_text(result)))


def emit_error(error: IRPError, json_mode: bool) -> None:
    if json_mode:
        typer.echo(json.dumps({"error": error.to_dict()}, ensure_ascii=False))
        return
    typer.secho(f"error ({error.code.value}): {error.message}", err=True, fg=typer.colors.RED)
    if error.remediation:
        typer.echo(f"next: {error.remediation}", err=True)
    if error.details:
        for line in render_text(error.details, 1):
            typer.echo(line, err=True)
