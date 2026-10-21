"""Pull numbers out of run logs and result files, keeping where each one came from.

These functions only read text that the application layer has already tied to
a completed run by hash. Every value carries its line (or JSON pointer / CSV
row), so a report can cite the exact place a number was printed.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
from dataclasses import dataclass
from typing import Any, Literal

from irp.domain.numbers import NUMBER_PATTERN

Reduce = Literal["last", "first", "max", "min", "mean"]


@dataclass(frozen=True)
class Occurrence:
    value: float
    raw: str
    line: int | None = None
    pointer: str | None = None
    row: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"value": self.value, "raw": self.raw}
        if self.line is not None:
            out["line"] = self.line
        if self.pointer is not None:
            out["pointer"] = self.pointer
        if self.row is not None:
            out["row"] = self.row
        return out


class ExtractionError(ValueError):
    """The spec is valid but the source holds no matching number."""


def key_occurrences(text: str, key: str) -> list[Occurrence]:
    """`key: 0.93`, `key=0.93` and `"key": 0.93` forms, one match per line at most."""
    escaped = re.escape(key)
    pattern = re.compile(
        rf"""(?<![\w.]){escaped}["']?\s*[:=]\s*["']?({NUMBER_PATTERN}%?)(?![\w.])"""
    )
    found: list[Occurrence] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in pattern.finditer(line):
            token = match.group(1).rstrip("%")
            if not any(ch.isdigit() for ch in token):
                continue
            value = float(token.replace(",", ""))
            if math.isfinite(value):
                found.append(Occurrence(value=value, raw=line.strip()[:240], line=line_no))
                break
    return found


def regex_occurrences(text: str, regex: str) -> list[Occurrence]:
    """Lines matching `regex`; the number is group `value`, else group 1."""
    try:
        pattern = re.compile(regex)
    except re.error as exc:
        raise ValueError(f"Invalid regex {regex!r}: {exc}") from exc
    if pattern.groups < 1:
        raise ValueError("The regex needs a capture group around the number, e.g. 'acc (\\S+)'.")
    found: list[Occurrence] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = pattern.search(line)
        if not match:
            continue
        group = match.group("value") if "value" in pattern.groupindex else match.group(1)
        if group is None:
            continue
        try:
            value = float(group.strip().rstrip("%").replace(",", ""))
        except ValueError:
            continue
        if math.isfinite(value):
            found.append(Occurrence(value=value, raw=line.strip()[:240], line=line_no))
    return found


def json_pointer_occurrences(text: str, pointer: str) -> list[Occurrence]:
    """RFC 6901 pointer into a JSON document; a list of numbers yields one occurrence each."""
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Not valid JSON: {exc}") from exc
    if pointer and not pointer.startswith("/"):
        raise ValueError("A JSON pointer starts with '/', e.g. '/test/accuracy'.")
    node: Any = document
    for part in pointer.split("/")[1:] if pointer else []:
        token = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node):
                raise ExtractionError(f"Pointer {pointer!r} does not exist.")
            node = node[int(token)]
        elif isinstance(node, dict):
            if token not in node:
                raise ExtractionError(f"Pointer {pointer!r} does not exist.")
            node = node[token]
        else:
            raise ExtractionError(f"Pointer {pointer!r} does not exist.")
    values = node if isinstance(node, list) else [node]
    found: list[Occurrence] = []
    for index, item in enumerate(values):
        if isinstance(item, bool) or not isinstance(item, int | float):
            continue
        if math.isfinite(float(item)):
            item_pointer = f"{pointer}/{index}" if isinstance(node, list) else pointer
            found.append(Occurrence(value=float(item), raw=json.dumps(item), pointer=item_pointer))
    return found


def csv_occurrences(text: str, column: str) -> list[Occurrence]:
    """One occurrence per row with a numeric value in `column`."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or column not in reader.fieldnames:
        raise ExtractionError(f"Column {column!r} is not in the CSV header {reader.fieldnames}.")
    found: list[Occurrence] = []
    for row_index, row in enumerate(reader, start=1):
        cell = (row.get(column) or "").strip()
        try:
            value = float(cell.rstrip("%"))
        except ValueError:
            continue
        if math.isfinite(value):
            # Header is line 1; DictReader rows start on line 2 for simple CSV.
            found.append(Occurrence(value=value, raw=cell, row=row_index, line=row_index + 1))
    return found


def reduce_occurrences(
    occurrences: list[Occurrence], how: Reduce
) -> tuple[float, list[Occurrence]]:
    """Reduce to one value and return the occurrences that support it."""
    if not occurrences:
        raise ExtractionError("No matching numbers were found.")
    if how == "last":
        return occurrences[-1].value, [occurrences[-1]]
    if how == "first":
        return occurrences[0].value, [occurrences[0]]
    if how == "max":
        best = max(occurrences, key=lambda o: o.value)
        return best.value, [best]
    if how == "min":
        best = min(occurrences, key=lambda o: o.value)
        return best.value, [best]
    return statistics.fmean(o.value for o in occurrences), list(occurrences)
