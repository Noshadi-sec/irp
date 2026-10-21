"""Intake workflows: fetch_paper, get_section and get_page_image."""

from __future__ import annotations

import json
import re
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from irp.application.context import OperationContext
from irp.application.study import (
    Study,
    create_study,
    open_study,
    resolve_study_path,
    tree_digest,
)
from irp.contracts.inputs import FetchPaperInput, GetPageImageInput, GetSectionInput
from irp.domain.errors import ErrorCode, IRPError
from irp.filesystem import atomic_write_bytes, atomic_write_text, sha256_file
from irp.identity import STUDY_MANIFEST
from irp.providers.intake import arxiv, images, latex, pdf
from irp.providers.intake.archive import detect_kind, unpack_source

INDEX_FILE = "index.json"
TEXT_FILE = "text.json"
PDF_FILE = "paper.pdf"
SOURCE_DIR = "source"


def fetch_paper(request: FetchPaperInput, context: OperationContext) -> dict[str, Any]:
    root = resolve_study_path(request.study)
    if (root / STUDY_MANIFEST).is_file():
        study = open_study(request.study)
        if study.state().paper is not None:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                "This study already has its paper. A study holds one paper.",
                remediation="Create a new study directory for another paper or version.",
            )
    else:
        study = create_study(request.study, paper_ref=request.paper, actor=context.actor)
    try:
        paper = _acquire(study, request, context)
    except BaseException:
        # No paper.fetched record exists yet, so these files are IRP's own
        # partial download; clear them so a retry starts clean.
        shutil.rmtree(study.paper_dir, ignore_errors=True)
        study.paper_dir.mkdir(parents=True, exist_ok=True)
        raise
    study.log.append("paper.fetched", {"paper": paper}, actor=context.actor)
    return {
        "study": str(study.root),
        "paper": {
            key: paper.get(key)
            for key in (
                "title",
                "arxiv_id",
                "version",
                "authors",
                "source_format",
                "parser",
                "links",
            )
        },
        "files": paper["files"],
        "outline": _outline_summary(_load_index(study)),
        "next": "Read the paper with get_section (start with 'abstract' and 'index'), then record every "
        "claim with add_claim before writing any code.",
    }


def _acquire(study: Study, request: FetchPaperInput, context: OperationContext) -> dict[str, Any]:
    paper_dir = study.paper_dir
    ref = arxiv.parse_arxiv_ref(request.paper)
    paper: dict[str, Any] = {"ref": request.paper, "files": [], "links": {}}
    source_download: bytes | None = None
    pdf_bytes: bytes | None = None
    local = Path(request.paper).expanduser()
    if ref is not None:
        metadata = arxiv.fetch_metadata(ref, context.fetcher)
        resolved = arxiv.ArxivRef(id=metadata.id, version=metadata.version)
        paper.update(
            {
                "kind": "arxiv",
                "arxiv_id": metadata.id,
                "version": metadata.version,
                "title": metadata.title,
                "authors": metadata.authors,
                "published": metadata.published,
                "updated": metadata.updated,
                "abstract": metadata.abstract,
                "primary_category": metadata.primary_category,
                "doi": metadata.doi,
                "links": {
                    "abs": arxiv.abs_url(resolved),
                    "pdf": arxiv.pdf_url(resolved),
                    "source": arxiv.source_url(resolved),
                },
            }
        )
        if request.prefer == "latex":
            download = context.fetcher.get(arxiv.source_url(resolved))
            if detect_kind(download.content) == "pdf":
                pdf_bytes = download.content
            else:
                source_download = download.content
        if pdf_bytes is None and (request.with_pdf or source_download is None):
            pdf_bytes = context.fetcher.get(arxiv.pdf_url(resolved)).content
    elif request.paper.startswith(("http://", "https://")):
        download = context.fetcher.get(request.paper)
        kind = detect_kind(download.content)
        paper.update({"kind": "url", "links": {"source": request.paper}, "title": None})
        if kind == "pdf":
            pdf_bytes = download.content
        elif kind in ("gzip", "zip", "tar", "tex"):
            source_download = download.content
        else:
            raise IRPError(
                ErrorCode.PAPER_UNAVAILABLE,
                f"{request.paper} is neither a PDF nor a LaTeX source archive.",
                remediation="Pass the direct PDF link or an arXiv ID.",
            )
    elif local.exists():
        local = local.resolve()
        paper.update({"kind": "local", "title": None, "local_path": str(local)})
        if local.is_dir():
            shutil.copytree(
                local, paper_dir / SOURCE_DIR, ignore=shutil.ignore_patterns(".git", "__pycache__")
            )
        else:
            content = local.read_bytes()
            if detect_kind(content) == "pdf":
                pdf_bytes = content
            else:
                source_download = content
        sibling_pdf = next(iter(sorted(local.glob("*.pdf"))), None) if local.is_dir() else None
        if sibling_pdf is not None and pdf_bytes is None:
            pdf_bytes = sibling_pdf.read_bytes()
    else:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"{request.paper!r} is not an arXiv ID, a URL or an existing path.",
            remediation="Pass an arXiv ID such as 2501.12345, a PDF URL, or a local file path.",
        )

    if source_download is not None:
        suffix = {"gzip": ".tar.gz", "zip": ".zip", "tar": ".tar", "tex": ".tex"}.get(
            detect_kind(source_download), ".bin"
        )
        atomic_write_bytes(paper_dir / f"source-download{suffix}", source_download)
        unpacked = unpack_source(source_download, paper_dir / SOURCE_DIR)
        paper["source_archive_kind"] = unpacked.kind
    if pdf_bytes is not None:
        atomic_write_bytes(paper_dir / PDF_FILE, pdf_bytes)

    source_root = paper_dir / SOURCE_DIR
    main = latex.find_main_file(source_root) if source_root.is_dir() else None
    if main is not None and request.prefer == "latex":
        document = latex.flatten(source_root, main)
        index = latex.index_document(document)
        lines = [(line.file, line.line, line.text) for line in document.lines]
        paper["source_format"] = "latex"
        paper["parser"] = "latex"
        paper["main_file"] = f"{SOURCE_DIR}/{document.main_file}"
        if paper.get("title") is None:
            paper["title"] = _latex_title(lines)
    elif (paper_dir / PDF_FILE).is_file():
        parser = request.parser
        if parser == "auto":
            parser = "docling" if pdf.docling_available() else "pypdf"
        if parser == "docling":
            source_lines = pdf.docling_markdown(paper_dir / PDF_FILE)
            index = pdf.index_markdown_lines(source_lines)
        else:
            source_lines, pages, outline = pdf.read_pdf_lines(paper_dir / PDF_FILE)
            index = pdf.index_pdf_lines(source_lines, pages, outline)
        lines = [(line.file, line.line, line.text) for line in source_lines]
        paper["source_format"] = "pdf"
        paper["parser"] = parser
        if paper.get("title") is None:
            paper["title"] = next((text.strip() for _f, _l, text in lines if text.strip()), None)
    else:
        raise IRPError(
            ErrorCode.PAPER_UNAVAILABLE,
            "No LaTeX main file and no PDF were found for this paper.",
            remediation="Pass the paper's PDF, or a source directory that contains the \\documentclass file.",
        )
    if (paper_dir / PDF_FILE).is_file():
        try:
            paper["pages"] = images.page_count(paper_dir / PDF_FILE)
        except Exception:  # noqa: BLE001 - page count is informational; text intake already succeeded
            paper["pages"] = None
    atomic_write_text(paper_dir / INDEX_FILE, json.dumps(index, indent=1))
    atomic_write_text(paper_dir / TEXT_FILE, json.dumps(lines))
    paper["counts"] = {
        "sections": len(index["sections"]),
        "tables": sum(1 for i in index["items"] if i["kind"] == "table"),
        "figures": sum(1 for i in index["items"] if i["kind"] == "figure"),
        "equations": sum(1 for i in index["items"] if i["kind"] == "equation"),
        "algorithms": sum(1 for i in index["items"] if i["kind"] == "algorithm"),
        "lines": len(lines),
    }
    if index.get("missing_inputs"):
        paper["missing_inputs"] = index["missing_inputs"]
    files = sorted(p for p in paper_dir.iterdir() if p.is_file() and not p.name.startswith("."))
    paper["files"] = [
        {"path": study.rel(p), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in files
    ]
    if source_root.is_dir():
        # The unpacked source is evidence too: one digest over every path and byte in it.
        paper["files"].append(
            {
                "path": study.rel(source_root),
                "sha256": tree_digest(source_root),
                "tree": True,
                "file_count": sum(1 for f in source_root.rglob("*") if f.is_file()),
            }
        )
    return paper


def _latex_title(lines: list[tuple[str, int, str]]) -> str | None:
    for _file, _line, text in lines:
        match = re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{(.+)", latex.strip_comment(text))
        if match:
            title = match.group(1)
            title = re.sub(r"\\\\|\\thanks\{[^}]*\}", " ", title)
            title = re.sub(r"\\[a-zA-Z]+\s*", "", title).replace("{", "").replace("}", "")
            return " ".join(title.split()) or None
    return None


def _outline_summary(index: dict[str, Any]) -> dict[str, Any]:
    """A compact outline: every section, and tables, figures and algorithms with short captions."""
    return {
        "source_format": index["source_format"],
        "sections": [
            {"id": s["id"], "title": s["title"]} for s in index["sections"] if s["level"] <= 2
        ],
        "items": [
            {"id": i["id"], "caption": (i.get("caption") or "")[:90]}
            for i in index["items"]
            if i["kind"] in ("table", "figure", "algorithm")
        ],
        "equations": sum(1 for i in index["items"] if i["kind"] == "equation"),
        "more": "get_section id='index' returns every section, item and label.",
    }


@lru_cache(maxsize=8)
def _load_cached(path: str, mtime_ns: int) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_index(study: Study) -> dict[str, Any]:
    path = study.paper_dir / INDEX_FILE
    if not path.is_file():
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            "The paper has not been fetched for this study.",
            remediation="Call fetch_paper first.",
        )
    index: dict[str, Any] = _load_cached(str(path), path.stat().st_mtime_ns)
    return index


def load_lines(study: Study) -> list[tuple[str, int, str]]:
    path = study.paper_dir / TEXT_FILE
    if not path.is_file():
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            "The paper has not been fetched for this study.",
            remediation="Call fetch_paper first.",
        )
    raw = _load_cached(str(path), path.stat().st_mtime_ns)
    return [(str(f), int(n), str(t)) for f, n, t in raw]


def resolve_reference(index: dict[str, Any], ident: str) -> dict[str, Any] | None:
    """An id, label, or section title to its index entry."""
    wanted = ident.strip()
    if wanted == "abstract" and index.get("abstract") and "flat_end" in index["abstract"]:
        return {**index["abstract"], "kind": "abstract"}
    for entry in index["sections"]:
        if entry["id"] == wanted or wanted in entry.get("labels", []):
            return {**entry, "kind": "section"}
    for entry in index["items"]:
        if (
            entry["id"] == wanted
            or wanted in entry.get("labels", [])
            or wanted in [f"{entry['id'].split(':')[0]}:{n}" for n in entry.get("numbers", [])]
        ):
            found: dict[str, Any] = entry
            return found
    lowered = wanted.lower()
    for entry in index["sections"]:
        if entry["title"].lower() == lowered:
            return {**entry, "kind": "section"}
    for entry in index["sections"]:
        if lowered in entry["title"].lower():
            return {**entry, "kind": "section"}
    return None


def get_section(request: GetSectionInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    index = _load_index(study)
    lines = load_lines(study)
    if request.id == "index":
        return {"id": "index", "index": _full_outline(index)}
    title: str | None
    if request.id.startswith("lines:"):
        match = re.fullmatch(r"lines:(\d+)-(\d+)", request.id)
        if not match:
            raise IRPError(
                ErrorCode.INVALID_REQUEST, "Use 'lines:START-END' with flattened line numbers."
            )
        start, end = int(match.group(1)) - 1, int(match.group(2)) - 1
        title, kind = f"lines {start + 1}-{end + 1}", "lines"
    elif request.id.startswith("page:"):
        page = request.id.split(":", 1)[1]
        label = pdf.pdf_file_label(int(page)) if page.isdigit() else ""
        selected = [i for i, (file, _l, _t) in enumerate(lines) if file == label]
        if not selected:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                f"No extracted text for {request.id}.",
                remediation="Page text exists only for PDF-based studies; use get_page_image to see the page.",
            )
        start, end, title, kind = selected[0], selected[-1], f"page {page}", "page"
    else:
        entry = resolve_reference(index, request.id)
        if entry is None:
            raise IRPError(
                ErrorCode.NOT_FOUND,
                f"Nothing in the paper matches {request.id!r}.",
                remediation="Call get_section with id='index' to list sections, items and labels.",
            )
        start, end = entry["flat_start"], entry["flat_end"]
        title = entry.get("title") or entry.get("caption") or entry["id"]
        kind = entry.get("kind", "section")
    start = max(0, start)
    end = min(len(lines) - 1, end)
    total = end - start + 1
    first = start + request.offset
    last = min(end, first + request.max_lines - 1)
    rendered = _render_lines(lines, first, last) if first <= end else ""
    returned = max(0, last - first + 1)
    next_offset = request.offset + returned if first + returned <= end else None
    return {
        "id": request.id,
        "kind": kind,
        "title": title,
        "start": {"file": lines[start][0], "line": lines[start][1]} if total > 0 else None,
        "lines_total": total,
        "offset": request.offset,
        "returned": returned,
        "next_offset": next_offset,
        "text": rendered,
    }


def _render_lines(lines: list[tuple[str, int, str]], first: int, last: int) -> str:
    """cat -n style, with a header whenever the source file changes."""
    out: list[str] = []
    current_file = None
    for file, number, text in lines[first : last + 1]:
        if file != current_file:
            out.append(f"== {file} ==")
            current_file = file
        out.append(f"{number:>5}  {text}")
    return "\n".join(out)


def _full_outline(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_format": index["source_format"],
        "main_file": index.get("main_file"),
        "abstract": "abstract" if index.get("abstract") else None,
        "sections": [
            {
                "id": s["id"],
                "title": s["title"],
                "level": s["level"],
                "labels": s.get("labels", []),
                "start": s.get("start"),
            }
            for s in index["sections"]
        ],
        "items": [
            {
                "id": i["id"],
                "kind": i["kind"],
                "numbers": i.get("numbers", []),
                "labels": i.get("labels", []),
                "caption": (i.get("caption") or "")[:160],
                "start": i.get("start"),
                "section": i.get("section"),
            }
            for i in index["items"]
        ],
        "missing_inputs": index.get("missing_inputs", []),
        "notes": "Item numbers are inferred from document order; labels are exact."
        if index["source_format"] == "latex"
        else index.get("math_warning"),
    }


def get_page_image(request: GetPageImageInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    pdf_path = study.paper_dir / PDF_FILE
    if not pdf_path.is_file():
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            "This study has no PDF of the paper.",
            remediation="Fetch the paper with with_pdf=true, or read the LaTeX with get_section.",
        )
    destination = study.paper_dir / "pages" / f"page-{request.page:03d}@{request.dpi}dpi.png"
    if not destination.is_file():
        width, height = images.render_page(pdf_path, request.page, request.dpi, destination)
    else:
        from PIL import Image

        with Image.open(destination) as image:
            width, height = image.size
    return {
        "page": request.page,
        "dpi": request.dpi,
        "path": str(destination),
        "width": width,
        "height": height,
        "sha256": sha256_file(destination),
    }
