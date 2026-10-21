"""An offline arXiv: serves the toy paper as e-print source, Atom metadata and a PDF."""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

from irp.domain.errors import ErrorCode, IRPError
from irp.providers.intake.arxiv import Download
from tests.support.pdf import make_pdf

TOY_PAPER = Path(__file__).resolve().parents[2] / "examples" / "toy-paper" / "paper"
TOY_ID = "2501.00001"

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/{id}{version}</id>
    <updated>2025-01-02T00:00:00Z</updated>
    <published>2025-01-01T00:00:00Z</published>
    <title>Least Squares Recovers a Linear
      Trend in Ten Thousand Samples</title>
    <summary>We fit a line to noisy samples.</summary>
    <author><name>Ada Example</name></author>
    <author><name>Alan Example</name></author>
    <arxiv:primary_category term="stat.ML" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""

TOY_PDF_PAGES = [
    [
        "Least Squares Recovers a Linear Trend",
        "Abstract",
        "We fit a line to noisy samples of y = 2x + 1.",
        "1 Introduction",
        "Ordinary least squares is the simplest estimator.",
    ],
    [
        "2 Method",
        "We minimize the squared error.        (2)",
        "y = w x + b + e        (1)",
        "3 Experiments",
        "Table 1: Least squares on synthetic data, mean over three seeds.",
        "OLS (ours) 2.00 0.0100",
    ],
]


def toy_source_tarball() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for path in sorted(TOY_PAPER.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(TOY_PAPER).as_posix())
    return gzip.compress(buffer.getvalue())


class FakeArxiv:
    """Answers the URLs IRP requests; records them for assertions."""

    def __init__(self, *, version: str = "v2", with_source: bool = True) -> None:
        self.version = version
        self.with_source = with_source
        self.requests: list[str] = []
        self.pdf = make_pdf(TOY_PDF_PAGES)

    def get(self, url: str) -> Download:
        self.requests.append(url)
        if url.startswith("https://export.arxiv.org/api/query"):
            body = ATOM.format(id=TOY_ID, version=self.version).encode()
            return Download(url=url, content=body, content_type="application/atom+xml")
        if url.startswith("https://arxiv.org/e-print/"):
            if not self.with_source:
                return Download(url=url, content=self.pdf, content_type="application/pdf")
            return Download(
                url=url, content=toy_source_tarball(), content_type="application/x-eprint-tar"
            )
        if url.startswith("https://arxiv.org/pdf/"):
            return Download(url=url, content=self.pdf, content_type="application/pdf")
        raise IRPError(ErrorCode.PAPER_UNAVAILABLE, f"unexpected URL {url}")
