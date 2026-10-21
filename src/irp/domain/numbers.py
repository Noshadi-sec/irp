"""Read numbers the way papers and logs write them, keeping the original text."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Signed decimal with optional thousands separators and exponent. Unicode minus
# signs are common in LaTeX-rendered PDFs and are normalized before parsing.
NUMBER_PATTERN = r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?:[eE][-+]?\d+)?"
_NUMBER_RE = re.compile(rf"(?<![\w.])({NUMBER_PATTERN})")
_SYMBOL_UNIT_RE = re.compile("^\\s?(%|\u00d7|x)(?![A-Za-z])")  # \u00d7 is the multiplication sign
_WORD_UNIT_RE = re.compile(r"^\s?(ms|s|sec|min|h|hours?|GB|MB|GiB|MiB|k|K|M|B)(?![A-Za-z])")
_MINUS_SIGNS = str.maketrans({"\u2212": "-", "\u2013": "-", "\u2012": "-"})


@dataclass(frozen=True)
class ParsedNumber:
    value: float
    text: str
    unit: str | None


def normalize_number_text(text: str) -> str:
    """Normalize LaTeX and typographic forms such as `$94.1\\%$` or a Unicode minus sign."""
    cleaned = text.translate(_MINUS_SIGNS)
    cleaned = cleaned.replace("\\%", "%").replace("$", "").replace("\\times", "\u00d7")
    cleaned = re.sub(
        r"\\(?:mathbf|textbf|bf|underline|emph|mathrm|text)\{([^{}]*)\}", r"\1", cleaned
    )
    return cleaned.strip()


def parse_number(text: str) -> ParsedNumber:
    """Parse the first number in `text`, with a trailing unit when one is present.

    Raises ValueError when the text has no finite number.
    """
    cleaned = normalize_number_text(text)
    for match in _NUMBER_RE.finditer(cleaned):
        token = match.group(1)
        if not any(ch.isdigit() for ch in token):
            continue
        value = float(token.replace(",", ""))
        if not math.isfinite(value):
            continue
        rest = cleaned[match.end() :]
        unit_match = _SYMBOL_UNIT_RE.match(rest) or _WORD_UNIT_RE.match(rest)
        unit = None
        if unit_match:
            unit = "x" if unit_match.group(1) == "\u00d7" else unit_match.group(1)
        return ParsedNumber(value=value, text=text.strip(), unit=unit)
    raise ValueError(f"No number found in {text!r}")


def find_numbers(line: str) -> list[tuple[float, int, int]]:
    """Every finite number in a line, with its character span in the normalized line."""
    cleaned = normalize_number_text(line)
    found: list[tuple[float, int, int]] = []
    for match in _NUMBER_RE.finditer(cleaned):
        token = match.group(1)
        if not any(ch.isdigit() for ch in token):
            continue
        try:
            value = float(token.replace(",", ""))
        except ValueError:
            continue
        if math.isfinite(value):
            found.append((value, match.start(1), match.end(1)))
    return found


def decimals_in(text: str) -> int:
    """Digits after the decimal point in the first number, used to match paper precision."""
    match = re.search(r"\d+\.(\d+)", normalize_number_text(text))
    return len(match.group(1)) if match else 0


def numbers_match(paper_text: str, candidate: float) -> bool:
    """True when `candidate` equals the paper's number at the paper's printed precision."""
    parsed = parse_number(paper_text)
    places = decimals_in(paper_text)
    return round(candidate, places) == round(parsed.value, places)


def is_power_of_ten(value: float) -> bool:
    """Accept only 10^k for k in [-6, 6]; unit conversions must never hide a fudge factor."""
    if value <= 0:
        return False
    exponent = math.log10(value)
    rounded = round(exponent)
    return -6 <= rounded <= 6 and math.isclose(exponent, rounded, abs_tol=1e-12)
