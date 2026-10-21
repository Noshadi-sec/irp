"""The four verdicts and the arithmetic behind them."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Literal

from irp.domain.claims import SuccessBar

Verdict = Literal["reproduced", "close", "not_reproduced", "could_not_run"]
VERDICTS: tuple[Verdict, ...] = ("reproduced", "close", "not_reproduced", "could_not_run")

# How each verdict reads in a report. "Not reproduced" always names the run:
# a single failed attempt is evidence about this run, not a judgment of the paper.
VERDICT_LABELS: dict[str, str] = {
    "reproduced": "reproduced",
    "close": "close",
    "not_reproduced": "not reproduced by this run",
    "could_not_run": "could not run",
}


@dataclass(frozen=True)
class Aggregate:
    value: float
    count: int
    std: float | None
    values: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "count": self.count,
            "std": self.std,
            "values": list(self.values),
        }


def aggregate(values: list[float]) -> Aggregate:
    """Mean over seeds, with the sample standard deviation when there are two or more."""
    if not values:
        raise ValueError("aggregate needs at least one value")
    mean = statistics.fmean(values)
    std = statistics.stdev(values) if len(values) > 1 else None
    return Aggregate(value=mean, count=len(values), std=std, values=tuple(values))


@dataclass(frozen=True)
class Judgement:
    verdict: Verdict
    paper_value: float
    measured_value: float
    difference: float
    relative_difference: float | None
    reproduced_allowance: float
    close_allowance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "paper_value": self.paper_value,
            "measured_value": self.measured_value,
            "difference": self.difference,
            "relative_difference": self.relative_difference,
            "reproduced_allowance": self.reproduced_allowance,
            "close_allowance": self.close_allowance,
        }


def judge(paper_value: float, measured: float, bar: SuccessBar) -> Judgement:
    """Place one measured value against the claim's success bar."""
    if not (math.isfinite(paper_value) and math.isfinite(measured)):
        raise ValueError("judge needs finite values")
    difference = measured - paper_value
    relative = None if paper_value == 0 else difference / abs(paper_value)
    reproduced_allowance = bar.reproduced.allowance(paper_value)
    close_allowance = max(bar.close.allowance(paper_value), reproduced_allowance)
    # Shortfall is how far the measurement falls on the wrong side of the claim.
    if bar.comparator == "approx":
        shortfall = abs(difference)
    elif bar.comparator == "at_least":
        shortfall = max(0.0, -difference)
    else:
        shortfall = max(0.0, difference)
    # A hair of float slack so 93.1 vs 94.1 with a 1.0 bound is not lost to rounding.
    slack = 1e-12 * max(1.0, abs(paper_value))
    if shortfall <= reproduced_allowance + slack:
        verdict: Verdict = "reproduced"
    elif shortfall <= close_allowance + slack:
        verdict = "close"
    else:
        verdict = "not_reproduced"
    return Judgement(
        verdict=verdict,
        paper_value=paper_value,
        measured_value=measured,
        difference=difference,
        relative_difference=relative,
        reproduced_allowance=reproduced_allowance,
        close_allowance=close_allowance,
    )


def summarize(verdicts: list[str]) -> dict[str, int]:
    counts: dict[str, int] = dict.fromkeys(VERDICTS, 0)
    for verdict in verdicts:
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts
