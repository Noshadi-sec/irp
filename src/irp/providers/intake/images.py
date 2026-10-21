"""Render one PDF page as a PNG the agent can look at (equations, figures, tables)."""

from __future__ import annotations

from pathlib import Path

from irp.domain.errors import ErrorCode, IRPError

MIN_DPI = 50
MAX_DPI = 300


def page_count(pdf: Path) -> int:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf))
    try:
        return len(document)
    finally:
        document.close()


def render_page(pdf: Path, page: int, dpi: int, destination: Path) -> tuple[int, int]:
    """Render 1-based `page` at `dpi` into `destination`; return (width, height) in pixels."""
    import pypdfium2 as pdfium

    if not MIN_DPI <= dpi <= MAX_DPI:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"dpi must be between {MIN_DPI} and {MAX_DPI}.",
            details={"dpi": dpi},
        )
    document = pdfium.PdfDocument(str(pdf))
    try:
        total = len(document)
        if not 1 <= page <= total:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                f"The paper has {total} pages; page {page} does not exist.",
                details={"pages": total},
            )
        bitmap = document[page - 1].render(scale=dpi / 72)
        image = bitmap.to_pil()
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG", optimize=True)
        return image.width, image.height
    finally:
        document.close()
