"""Read LaTeX source into one line-addressed document and index its structure.

Every flattened line keeps the file and line it came from, so claims and method
map entries can cite `sections/method.tex:12` instead of a guess. Numbering of
tables, figures and equations is inferred from document order; labels are exact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_INCLUDE_DEPTH = 20
SECTION_LEVELS = {
    "part": 0,
    "chapter": 0,
    "section": 1,
    "subsection": 2,
    "subsubsection": 3,
}
SECTION_RE = re.compile(
    r"\\(part|chapter|section|subsection|subsubsection)(\*)?\s*(?:\[[^\]]*\])?\s*\{"
)
INPUT_RE = re.compile(r"\\(input|include|subfile)\s*\{([^}]+)\}|\\input\s+([^\s{}\\]+)")
IMPORT_RE = re.compile(r"\\(?:sub)?import\*?\s*\{([^}]*)\}\s*\{([^}]+)\}")
BEGIN_RE = re.compile(r"\\begin\s*\{([A-Za-z]+\*?)\}")
END_RE = re.compile(r"\\end\s*\{([A-Za-z]+\*?)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^}]+)\}")
CAPTION_RE = re.compile(r"\\caption(?:of\{[^}]*\})?\s*(?:\[[^\]]*\])?\s*\{")
NONUMBER_RE = re.compile(r"\\(?:nonumber|notag)\b")

ENVIRONMENT_KINDS = {
    "table": "table",
    "table*": "table",
    "wraptable": "table",
    "figure": "figure",
    "figure*": "figure",
    "wrapfigure": "figure",
    "equation": "equation",
    "equation*": "equation",
    "align": "equation",
    "align*": "equation",
    "gather": "equation",
    "gather*": "equation",
    "multline": "equation",
    "multline*": "equation",
    "eqnarray": "equation",
    "eqnarray*": "equation",
    "algorithm": "algorithm",
    "algorithm*": "algorithm",
    "algorithm2e": "algorithm",
}
NUMBERED_MULTILINE = {"align", "gather", "eqnarray"}


@dataclass(frozen=True)
class SourceLine:
    file: str
    line: int
    text: str


@dataclass
class LatexDocument:
    main_file: str
    lines: list[SourceLine] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)


def strip_comment(text: str) -> str:
    """Drop an unescaped `%` comment; `\\%` stays."""
    match = re.search(r"(?<!\\)%", text)
    return text if match is None else text[: match.start()]


def find_main_file(root: Path) -> Path | None:
    """The file with \\documentclass and \\begin{document}, preferring common names."""
    candidates: list[tuple[int, int, Path]] = []
    for path in sorted(root.rglob("*.tex")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        code = "\n".join(strip_comment(line) for line in text.splitlines())
        if "\\documentclass" not in code:
            continue
        score = 0
        if "\\begin{document}" in code:
            score += 10
        if path.stem.lower() in {"main", "paper", "ms", "manuscript", "article"}:
            score += 3
        if path.parent == root:
            score += 1
        candidates.append((score, len(text), path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _resolve_input(root: Path, base_dir: Path, name: str) -> Path | None:
    name = name.strip()
    for directory in (base_dir, root):
        candidate = (directory / name).resolve()
        for option in (candidate, candidate.with_name(candidate.name + ".tex")):
            try:
                option.relative_to(root.resolve())
            except ValueError:
                continue
            if option.is_file():
                return option
    return None


def flatten(root: Path, main: Path) -> LatexDocument:
    """Inline \\input/\\include/\\subfile/\\import, keeping each line's origin."""
    root = root.resolve()
    document = LatexDocument(main_file=main.resolve().relative_to(root).as_posix())
    visiting: set[Path] = set()

    def visit(path: Path, depth: int) -> None:
        resolved = path.resolve()
        if depth > MAX_INCLUDE_DEPTH or resolved in visiting:
            return
        visiting.add(resolved)
        relative = resolved.relative_to(root).as_posix()
        text = resolved.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            code = strip_comment(line)
            include = INPUT_RE.search(code)
            imported = IMPORT_RE.search(code)
            document.lines.append(SourceLine(file=relative, line=number, text=line))
            if imported:
                target = _resolve_input(
                    root, resolved.parent / imported.group(1), imported.group(2)
                )
                if target is None:
                    document.missing_inputs.append(imported.group(2))
                else:
                    visit(target, depth + 1)
            elif include:
                name = include.group(2) or include.group(3)
                target = _resolve_input(root, resolved.parent, name)
                if target is None:
                    document.missing_inputs.append(name)
                else:
                    visit(target, depth + 1)
        visiting.discard(resolved)

    visit(main, 0)
    return document


def _balanced_argument(lines: list[SourceLine], index: int, start_col: int, limit: int = 40) -> str:
    """Read a brace group that may continue over the next lines."""
    depth = 1
    collected: list[str] = []
    text = strip_comment(lines[index].text)[start_col:]
    current = index
    while True:
        for pos, char in enumerate(text):
            if char == "{" and (pos == 0 or text[pos - 1] != "\\"):
                depth += 1
            elif char == "}" and (pos == 0 or text[pos - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    collected.append(text[:pos])
                    return " ".join(" ".join(collected).split())
        collected.append(text)
        current += 1
        if current >= len(lines) or current - index > limit:
            return " ".join(" ".join(collected).split())
        text = strip_comment(lines[current].text)


def _letter(n: int) -> str:
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(ord("A") + rem) + out
    return out


def index_document(document: LatexDocument) -> dict[str, Any]:
    """Sections, abstract, tables, figures, equations and algorithms with line spans."""
    lines = document.lines
    sections: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    counters = {"section": 0, "subsection": 0, "subsubsection": 0}
    item_counters = {"table": 0, "figure": 0, "equation": 0, "algorithm": 0}
    in_appendix = False
    in_document = not any("\\begin{document}" in strip_comment(line.text) for line in lines)
    stack: list[dict[str, Any]] = []
    abstract: dict[str, Any] | None = None
    open_section_stack: list[dict[str, Any]] = []

    def origin(i: int) -> dict[str, Any]:
        return {"file": lines[i].file, "line": lines[i].line}

    for i, source in enumerate(lines):
        code = strip_comment(source.text)
        if "\\begin{document}" in code:
            in_document = True
        if not in_document:
            # Preamble macros redefine \section and friends; only the body has structure.
            continue
        if "\\appendix" in code:
            in_appendix = True
            counters = {"section": 0, "subsection": 0, "subsubsection": 0}
        for match in SECTION_RE.finditer(code):
            command, starred = match.group(1), match.group(2) == "*"
            level = SECTION_LEVELS[command]
            title = _balanced_argument(lines, i, match.end())
            number = None
            if not starred and command in counters:
                counters[command] += 1
                if command == "section":
                    counters["subsection"] = counters["subsubsection"] = 0
                elif command == "subsection":
                    counters["subsubsection"] = 0
                head = _letter(counters["section"]) if in_appendix else str(counters["section"])
                number = {
                    "section": head,
                    "subsection": f"{head}.{counters['subsection']}",
                    "subsubsection": f"{head}.{counters['subsection']}.{counters['subsubsection']}",
                }[command]
            while open_section_stack and open_section_stack[-1]["level"] >= level:
                closed = open_section_stack.pop()
                closed["flat_end"] = i - 1
            section: dict[str, Any] = {
                "id": f"sec:{number}" if number else f"sec:*{len(sections) + 1}",
                "number": number,
                "title": title,
                "level": level,
                "appendix": in_appendix,
                "labels": [],
                "flat_start": i,
                "flat_end": len(lines) - 1,
                "start": origin(i),
            }
            sections.append(section)
            open_section_stack.append(section)
        for match in BEGIN_RE.finditer(code):
            env = match.group(1)
            if env == "abstract" and abstract is None:
                abstract = {
                    "id": "abstract",
                    "title": "Abstract",
                    "flat_start": i,
                    "start": origin(i),
                }
            kind = ENVIRONMENT_KINDS.get(env)
            if kind is None:
                continue
            nested = any(open_item["kind"] == kind for open_item in stack)
            entry: dict[str, Any] = {
                "kind": kind,
                "environment": env,
                "flat_start": i,
                "start": origin(i),
                "labels": [],
                "caption": None,
                "nested": nested,
                "lines_with_rows": 0,
                "nonumber": 0,
            }
            stack.append(entry)
        for match in LABEL_RE.finditer(code):
            label = match.group(1).strip()
            if stack:
                stack[-1]["labels"].append(label)
            elif open_section_stack:
                open_section_stack[-1]["labels"].append(label)
        caption = CAPTION_RE.search(code)
        if caption and stack and stack[-1]["caption"] is None:
            stack[-1]["caption"] = _balanced_argument(lines, i, caption.end())[:400]
        if stack and stack[-1]["kind"] == "equation":
            stack[-1]["lines_with_rows"] += code.count("\\\\")
            stack[-1]["nonumber"] += len(NONUMBER_RE.findall(code))
        for match in END_RE.finditer(code):
            env = match.group(1)
            if env == "abstract" and abstract is not None and "flat_end" not in abstract:
                abstract["flat_end"] = i
                abstract["end"] = origin(i)
            if ENVIRONMENT_KINDS.get(env) is None or not stack:
                continue
            closing = next((e for e in reversed(stack) if e["environment"] == env), None)
            if closing is None:
                continue
            stack.remove(closing)
            closing["flat_end"] = i
            closing["end"] = origin(i)
            if closing["nested"]:
                continue
            kind = closing["kind"]
            numbers: list[str] = []
            # Starred math environments are unnumbered; figure* and table* are
            # two-column floats and keep their numbers.
            if not (env.endswith("*") and kind == "equation"):
                if kind == "equation":
                    base = env.rstrip("*")
                    rows = closing["lines_with_rows"] + 1 if base in NUMBERED_MULTILINE else 1
                    count = (
                        max(0, rows - closing["nonumber"])
                        if base in NUMBERED_MULTILINE
                        else (0 if closing["nonumber"] else 1)
                    )
                    for _ in range(count):
                        item_counters["equation"] += 1
                        numbers.append(str(item_counters["equation"]))
                else:
                    item_counters[kind] += 1
                    numbers.append(str(item_counters[kind]))
            prefix = {"table": "tab", "figure": "fig", "equation": "eq", "algorithm": "alg"}[kind]
            identifier = f"{prefix}:{numbers[0]}" if numbers else f"{prefix}:*{len(items) + 1}"
            items.append(
                {
                    "id": identifier,
                    "kind": kind,
                    "environment": env,
                    "numbers": numbers,
                    "number_inferred": True,
                    "caption": closing["caption"],
                    "labels": closing["labels"],
                    "flat_start": closing["flat_start"],
                    "flat_end": closing["flat_end"],
                    "start": closing["start"],
                    "end": closing["end"],
                }
            )
    for section in open_section_stack:
        section["flat_end"] = len(lines) - 1
    for section in sections:
        section["end"] = origin(section["flat_end"]) if lines else None
    for item in items:
        item["section"] = _containing_section(sections, item["flat_start"])
    return {
        "source_format": "latex",
        "main_file": document.main_file,
        "line_count": len(lines),
        "missing_inputs": sorted(set(document.missing_inputs)),
        "abstract": abstract,
        "sections": sections,
        "items": items,
    }


def _containing_section(sections: list[dict[str, Any]], flat_line: int) -> str | None:
    best = None
    for section in sections:
        contains = section["flat_start"] <= flat_line <= section["flat_end"]
        if contains and (best is None or section["level"] >= best["level"]):
            best = section
    return best["id"] if best else None
