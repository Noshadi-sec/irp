"""PDF text for papers without LaTeX source.

pypdf ships with IRP and gives page-addressed text. Docling (optional,
`irp-agents[docling]`) recovers better structure and tables. Both lose display
math, so get_page_image exists for equations and figures.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

from irp.domain.errors import ErrorCode, IRPError
from irp.providers.intake.latex import SourceLine

HEADING_RE = re.compile(
    r"^(?P<number>(?:\d+|[A-H])(?:\.\d+){0,2})\.?\s+(?P<title>[A-Z][^.!?]{1,90})$"
)
NAMED_HEADINGS = {
    "abstract",
    "references",
    "acknowledgments",
    "acknowledgements",
    "appendix",
    "conclusion",
    "introduction",
}
CAPTION_RE = re.compile(
    r"^(?P<kind>Table|Figure|Fig\.|Algorithm)\s+(?P<number>[A-Z]?\d+(?:\.\d+)?)\s*[:.|]\s*(?P<caption>.*)$"
)
EQUATION_NUMBER_RE = re.compile(r"\((?P<number>\d{1,3})\)\s*$")


def docling_available() -> bool:
    return importlib.util.find_spec("docling") is not None


def pdf_file_label(page: int) -> str:
    return f"paper.pdf#page={page}"


def read_pdf_lines(pdf: Path) -> tuple[list[SourceLine], int, list[dict[str, Any]]]:
    """Every extracted line with its page, the page count, and the outline when present."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(pdf))
        lines: list[SourceLine] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for line_number, line in enumerate(text.splitlines(), start=1):
                lines.append(
                    SourceLine(file=pdf_file_label(page_number), line=line_number, text=line)
                )
        outline = _outline(reader)
        return lines, len(reader.pages), outline
    except PdfReadError as exc:
        raise IRPError(
            ErrorCode.PAPER_UNAVAILABLE,
            f"The PDF could not be read: {exc}",
            remediation="Check that the file is a complete, unencrypted PDF.",
        ) from exc


def _outline(reader: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def walk(nodes: Any, level: int) -> None:
        for node in nodes:
            if isinstance(node, list):
                walk(node, level + 1)
                continue
            try:
                page = reader.get_destination_page_number(node) + 1
            except Exception:  # noqa: BLE001, S112 - malformed outlines are common; skip the entry
                continue
            entries.append(
                {"title": " ".join(str(node.title).split()), "page": page, "level": level}
            )

    try:
        walk(reader.outline, 1)
    except Exception:  # noqa: BLE001 - an unreadable outline only loses navigation
        return []
    return entries


def index_pdf_lines(
    lines: list[SourceLine], pages: int, outline: list[dict[str, Any]]
) -> dict[str, Any]:
    """Sections from the outline when present, else from numbered headings; captions for items."""
    sections: list[dict[str, Any]] = []
    if outline:
        for entry in outline:
            start = _first_line_on_page(lines, entry["page"], entry["title"])
            if start is None:
                continue
            sections.append(
                {
                    "id": f"sec:{len(sections) + 1}",
                    "number": None,
                    "title": entry["title"],
                    "level": entry["level"],
                    "labels": [],
                    "flat_start": start,
                }
            )
    else:
        back_matter = False
        for i, source in enumerate(lines):
            text = source.text.strip()
            match = HEADING_RE.match(text)
            if text.lower() in ("references", "appendix", "appendices", "supplementary material"):
                back_matter = True
            # "A Simple Framework..." is a title, not appendix A: letters count only after the references.
            if match and match.group("number").isalpha() and not back_matter:
                match = None
            if match and len(text) <= 100:
                sections.append(
                    {
                        "id": f"sec:{match.group('number')}",
                        "number": match.group("number"),
                        "title": match.group("title").strip(),
                        "level": match.group("number").count(".") + 1,
                        "labels": [],
                        "flat_start": i,
                    }
                )
            elif text.lower() in NAMED_HEADINGS:
                sections.append(
                    {
                        "id": f"sec:{text.lower()}",
                        "number": None,
                        "title": text,
                        "level": 1,
                        "labels": [],
                        "flat_start": i,
                    }
                )
    _dedupe_ids(sections)
    for position, section in enumerate(sections):
        following = [s for s in sections[position + 1 :] if s["level"] <= section["level"]]
        section["flat_end"] = (following[0]["flat_start"] - 1) if following else len(lines) - 1
        section["start"] = {
            "file": lines[section["flat_start"]].file,
            "line": lines[section["flat_start"]].line,
        }
        section["end"] = {
            "file": lines[section["flat_end"]].file,
            "line": lines[section["flat_end"]].line,
        }
    items: list[dict[str, Any]] = []
    for i, source in enumerate(lines):
        text = source.text.strip()
        caption = CAPTION_RE.match(text)
        if caption:
            kind = {
                "Table": "table",
                "Figure": "figure",
                "Fig.": "figure",
                "Algorithm": "algorithm",
            }[caption.group("kind")]
            prefix = {"table": "tab", "figure": "fig", "algorithm": "alg"}[kind]
            items.append(
                {
                    "id": f"{prefix}:{caption.group('number')}",
                    "kind": kind,
                    "numbers": [caption.group("number")],
                    "number_inferred": False,
                    "caption": caption.group("caption")[:400],
                    "labels": [],
                    "flat_start": max(0, i - 2),
                    "flat_end": min(len(lines) - 1, i + 2),
                    "start": {"file": source.file, "line": source.line},
                    "end": {"file": source.file, "line": source.line},
                }
            )
            continue
        equation = EQUATION_NUMBER_RE.search(text)
        if equation and len(text) < 160 and any(ch in text for ch in "=≤≥∑∫"):
            items.append(
                {
                    "id": f"eq:{equation.group('number')}",
                    "kind": "equation",
                    "numbers": [equation.group("number")],
                    "number_inferred": False,
                    "caption": None,
                    "labels": [],
                    "flat_start": max(0, i - 1),
                    "flat_end": i,
                    "start": {"file": source.file, "line": source.line},
                    "end": {"file": source.file, "line": source.line},
                }
            )
    _dedupe_ids(items)
    return {
        "source_format": "pdf",
        "line_count": len(lines),
        "pages": pages,
        "abstract": next(
            (
                {
                    "id": "abstract",
                    "title": s["title"],
                    "flat_start": s["flat_start"],
                    "flat_end": s["flat_end"],
                }
                for s in sections
                if s["title"].lower() == "abstract"
            ),
            None,
        ),
        "sections": sections,
        "items": items,
        "math_warning": "PDF text loses display math; use get_page_image for equations.",
    }


def _first_line_on_page(lines: list[SourceLine], page: int, title: str) -> int | None:
    label = pdf_file_label(page)
    candidates = [i for i, line in enumerate(lines) if line.file == label]
    if not candidates:
        return None
    words = title.lower().split()[:3]
    for i in candidates:
        lowered = lines[i].text.lower()
        if words and all(word in lowered for word in words):
            return i
    return candidates[0]


def _dedupe_ids(entries: list[dict[str, Any]]) -> None:
    seen: dict[str, int] = {}
    for entry in entries:
        base = entry["id"]
        if base in seen:
            seen[base] += 1
            entry["id"] = f"{base}~{seen[base]}"
        else:
            seen[base] = 1


def docling_markdown(pdf: Path) -> list[SourceLine]:
    """Convert with Docling and return markdown lines (experimental provider)."""
    if not docling_available():
        raise IRPError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Docling is not installed.",
            remediation="Install the optional parser: `uv tool install 'irp-agents[docling]'`, "
            "or use parser='pypdf'.",
        )
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(str(pdf))
    markdown = result.document.export_to_markdown()
    return [
        SourceLine(file="docling.md", line=n, text=line)
        for n, line in enumerate(markdown.splitlines(), start=1)
    ]


def index_markdown_lines(lines: list[SourceLine]) -> dict[str, Any]:
    """Docling markdown: headings become sections; table blocks and captions become items."""
    sections: list[dict[str, Any]] = []
    for i, source in enumerate(lines):
        match = re.match(r"^(#{1,4})\s+(.*)$", source.text)
        if match:
            title = match.group(2).strip()
            number = re.match(r"^((?:\d+|[A-H])(?:\.\d+)*)\.?\s", title)
            sections.append(
                {
                    "id": f"sec:{number.group(1)}" if number else f"sec:{len(sections) + 1}",
                    "number": number.group(1) if number else None,
                    "title": title,
                    "level": len(match.group(1)),
                    "labels": [],
                    "flat_start": i,
                }
            )
    _dedupe_ids(sections)
    for position, section in enumerate(sections):
        following = [s for s in sections[position + 1 :] if s["level"] <= section["level"]]
        section["flat_end"] = (following[0]["flat_start"] - 1) if following else len(lines) - 1
        section["start"] = {"file": "docling.md", "line": lines[section["flat_start"]].line}
        section["end"] = {"file": "docling.md", "line": lines[section["flat_end"]].line}
    index = index_pdf_lines(lines, pages=0, outline=[])
    return {
        "source_format": "pdf",
        "line_count": len(lines),
        "pages": None,
        "abstract": None,
        "sections": sections,
        "items": index["items"],
        "math_warning": "Docling markdown can drop display equations; use get_page_image for math.",
    }
