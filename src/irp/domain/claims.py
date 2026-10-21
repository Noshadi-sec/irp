"""Claims: the paper's numbers, where they appear, and the bar for reproducing them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from irp.domain.numbers import decimals_in, find_numbers, parse_number

Comparator = Literal["approx", "at_least", "at_most"]
LocationKind = Literal["table", "figure", "section", "equation", "algorithm", "text", "appendix"]

# Conventions, not statistical tests. A claim that does not state its own bar
# uses these and the report labels the bar as the default.
DEFAULT_REPRODUCED_REL = 0.01
DEFAULT_CLOSE_REL = 0.05


@dataclass(frozen=True)
class Tolerance:
    """One bound: relative to the paper's value, absolute, or both (either suffices)."""

    rel: float | None = None
    abs: float | None = None

    def allowance(self, paper_value: float) -> float:
        bounds = []
        if self.rel is not None:
            bounds.append(self.rel * abs(paper_value))
        if self.abs is not None:
            bounds.append(self.abs)
        return max(bounds) if bounds else 0.0

    def to_dict(self) -> dict[str, float]:
        out: dict[str, float] = {}
        if self.rel is not None:
            out["rel"] = self.rel
        if self.abs is not None:
            out["abs"] = self.abs
        return out

    def describe(self) -> str:
        parts = []
        if self.rel is not None:
            parts.append(f"{self.rel * 100:g}% relative")
        if self.abs is not None:
            parts.append(f"{self.abs:g} absolute")
        return " or ".join(parts) if parts else "exact"


@dataclass(frozen=True)
class SuccessBar:
    comparator: Comparator
    reproduced: Tolerance
    close: Tolerance
    is_default: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparator": self.comparator,
            "reproduced": self.reproduced.to_dict(),
            "close": self.close.to_dict(),
            "is_default": self.is_default,
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> SuccessBar:
        return SuccessBar(
            comparator=raw["comparator"],
            reproduced=Tolerance(**raw["reproduced"]),
            close=Tolerance(**raw["close"]),
            is_default=bool(raw.get("is_default", False)),
        )


def build_success_bar(
    *,
    comparator: Comparator,
    tolerance_rel: float | None,
    tolerance_abs: float | None,
    close_rel: float | None,
    close_abs: float | None,
) -> SuccessBar:
    """Apply defaults only for bounds the caller left out, and say so."""
    explicit = any(v is not None for v in (tolerance_rel, tolerance_abs, close_rel, close_abs))
    reproduced = Tolerance(rel=tolerance_rel, abs=tolerance_abs)
    if reproduced.rel is None and reproduced.abs is None:
        reproduced = Tolerance(rel=DEFAULT_REPRODUCED_REL)
    close = Tolerance(rel=close_rel, abs=close_abs)
    if close.rel is None and close.abs is None:
        close = Tolerance(
            rel=max(DEFAULT_CLOSE_REL, (reproduced.rel or 0.0) * 2) if reproduced.rel else None,
            abs=reproduced.abs * 5 if reproduced.abs is not None else None,
        )
        if close.rel is None and close.abs is None:
            close = Tolerance(rel=DEFAULT_CLOSE_REL)
    return SuccessBar(
        comparator=comparator, reproduced=reproduced, close=close, is_default=not explicit
    )


@dataclass(frozen=True)
class PaperLocation:
    """Where a claim appears: the human label plus optional exact source coordinates."""

    kind: LocationKind
    label: str
    source_file: str | None = None
    source_line: int | None = None
    page: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "label": self.label}
        if self.source_file is not None:
            out["source_file"] = self.source_file
        if self.source_line is not None:
            out["source_line"] = self.source_line
        if self.page is not None:
            out["page"] = self.page
        return out


def locate_value(
    value_text: str,
    lines: list[tuple[str, int, str]],
    *,
    near: tuple[str, int] | None = None,
    window: int = 3,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Find where the paper prints this number, at the paper's precision.

    `lines` holds (file, line, text) for the paper. With `near`, only the lines
    within `window` of that file:line are searched. The check guards against a
    claim value that appears nowhere in the paper; it cannot prove the value is
    attached to the right metric.
    """
    target = parse_number(value_text).value
    places = decimals_in(value_text)
    matches: list[dict[str, Any]] = []
    for file, line_no, text in lines:
        if near is not None and (file != near[0] or abs(line_no - near[1]) > window):
            continue
        if any(_printed_equal(found, target, places) for found, _s, _e in find_numbers(text)):
            matches.append({"file": file, "line": line_no, "text": text.strip()[:240]})
            if len(matches) >= limit:
                break
    return matches


def _printed_equal(found: float, target: float, places: int) -> bool:
    """94.1 matches 94.1 and 94.10, but not 94.12: same value at the printed precision."""
    epsilon = 10.0 ** -(places + 6)
    return (
        abs(found - round(found, places)) < epsilon and abs(round(found, places) - target) < epsilon
    )


def claim_value(value_text: str) -> tuple[float, str | None]:
    parsed = parse_number(value_text)
    return parsed.value, parsed.unit
