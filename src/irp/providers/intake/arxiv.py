"""arXiv identity, metadata and downloads.

LaTeX source comes first because it has the exact equations; PDF parsers often
break math. Requests follow arXiv's API etiquette: an identifying User-Agent and
no more than one request every three seconds from this process.
"""

from __future__ import annotations

import re
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx

from irp.domain.errors import ErrorCode, IRPError
from irp.identity import PRODUCT

NEW_STYLE = re.compile(r"^(?P<id>\d{4}\.\d{4,5})(?P<version>v\d+)?$")
OLD_STYLE = re.compile(r"^(?P<id>[a-z][a-z\-]*(?:\.[A-Z]{2})?/\d{7})(?P<version>v\d+)?$")
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
MIN_INTERVAL_S = 3.0


@dataclass(frozen=True)
class ArxivRef:
    id: str
    version: str | None

    @property
    def versioned(self) -> str:
        return f"{self.id}{self.version or ''}"


def parse_arxiv_ref(text: str) -> ArxivRef | None:
    """Accept bare IDs, `arXiv:` prefixes and abs/pdf/e-print/html URLs."""
    candidate = text.strip()
    if candidate.lower().startswith("arxiv:"):
        candidate = candidate[6:].strip()
    if candidate.startswith(("http://", "https://")):
        parsed = urlparse(candidate)
        host = parsed.netloc.lower()
        if not (host == "arxiv.org" or host.endswith(".arxiv.org")):
            return None
        path = parsed.path.strip("/")
        for prefix in ("abs/", "pdf/", "e-print/", "html/", "src/"):
            if path.startswith(prefix):
                candidate = path[len(prefix) :]
                break
        else:
            return None
        candidate = candidate.removesuffix(".pdf").rstrip("/")
    for pattern in (NEW_STYLE, OLD_STYLE):
        match = pattern.match(candidate)
        if match:
            return ArxivRef(id=match.group("id"), version=match.group("version"))
    return None


@dataclass(frozen=True)
class Download:
    url: str
    content: bytes
    content_type: str


class Fetcher(Protocol):
    def get(self, url: str) -> Download: ...


class HttpFetcher:
    """httpx-based fetcher with a size cap and arXiv's request spacing."""

    _lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, timeout_s: float = 60.0, max_bytes: int = MAX_DOWNLOAD_BYTES) -> None:
        self.timeout_s = timeout_s
        self.max_bytes = max_bytes

    def get(self, url: str) -> Download:
        self._throttle(url)
        try:
            with (
                httpx.Client(
                    timeout=self.timeout_s,
                    follow_redirects=True,
                    headers={"User-Agent": PRODUCT.user_agent},
                ) as client,
                client.stream("GET", url) as response,
            ):
                if response.status_code == 404:
                    raise IRPError(
                        ErrorCode.PAPER_UNAVAILABLE,
                        f"{url} returned 404.",
                        remediation="Check the arXiv ID and version.",
                    )
                if response.status_code >= 400:
                    raise IRPError(
                        ErrorCode.PAPER_UNAVAILABLE,
                        f"{url} returned HTTP {response.status_code}.",
                        remediation="Retry later; arXiv may be rate limiting or unavailable.",
                        details={"status": response.status_code},
                    )
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise IRPError(
                            ErrorCode.PAPER_UNAVAILABLE,
                            f"{url} is larger than {self.max_bytes // (1024 * 1024)} MiB.",
                            remediation="Download the paper yourself and pass the local path.",
                        )
                    chunks.append(chunk)
                return Download(
                    url=str(response.url),
                    content=b"".join(chunks),
                    content_type=response.headers.get("content-type", ""),
                )
        except httpx.HTTPError as exc:
            raise IRPError(
                ErrorCode.PAPER_UNAVAILABLE,
                f"Could not download {url}: {exc}",
                remediation="Check network access, or pass a local PDF or LaTeX directory.",
            ) from exc

    @classmethod
    def _throttle(cls, url: str) -> None:
        if "arxiv.org" not in urlparse(url).netloc:
            return
        with cls._lock:
            wait = cls._last_request + MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            cls._last_request = time.monotonic()


@dataclass(frozen=True)
class ArxivMetadata:
    id: str
    version: str
    title: str
    authors: list[str]
    published: str | None
    updated: str | None
    abstract: str
    primary_category: str | None
    doi: str | None


def fetch_metadata(ref: ArxivRef, fetcher: Fetcher) -> ArxivMetadata:
    """Resolve title, authors and the exact version through the arXiv API."""
    download = fetcher.get(f"https://export.arxiv.org/api/query?id_list={ref.versioned}")
    try:
        # arXiv's own HTTPS API; expat refuses external entities and bounds entity expansion.
        root = ET.fromstring(download.content)  # noqa: S314
    except ET.ParseError as exc:
        raise IRPError(
            ErrorCode.PAPER_UNAVAILABLE,
            f"The arXiv API returned unreadable metadata for {ref.versioned}.",
            remediation="Retry later.",
        ) from exc
    entry = root.find(f"{ATOM}entry")
    if entry is None:
        raise IRPError(
            ErrorCode.PAPER_UNAVAILABLE,
            f"arXiv has no paper {ref.versioned}.",
            remediation="Check the arXiv ID.",
        )
    entry_id = (entry.findtext(f"{ATOM}id") or "").strip()
    title = " ".join((entry.findtext(f"{ATOM}title") or "").split())
    if not entry_id or title == "Error":
        raise IRPError(
            ErrorCode.PAPER_UNAVAILABLE,
            f"arXiv has no paper {ref.versioned}.",
            remediation="Check the arXiv ID.",
            details={"api_message": " ".join((entry.findtext(f"{ATOM}summary") or "").split())},
        )
    resolved = parse_arxiv_ref(entry_id) or ref
    category = entry.find(f"{ARXIV_NS}primary_category")
    return ArxivMetadata(
        id=resolved.id,
        version=resolved.version or ref.version or "v1",
        title=title,
        authors=[
            " ".join((author.findtext(f"{ATOM}name") or "").split())
            for author in entry.findall(f"{ATOM}author")
        ],
        published=entry.findtext(f"{ATOM}published"),
        updated=entry.findtext(f"{ATOM}updated"),
        abstract=" ".join((entry.findtext(f"{ATOM}summary") or "").split()),
        primary_category=category.get("term") if category is not None else None,
        doi=entry.findtext(f"{ARXIV_NS}doi"),
    )


def source_url(ref: ArxivRef) -> str:
    return f"https://arxiv.org/e-print/{ref.versioned}"


def pdf_url(ref: ArxivRef) -> str:
    return f"https://arxiv.org/pdf/{ref.versioned}"


def abs_url(ref: ArxivRef) -> str:
    return f"https://arxiv.org/abs/{ref.versioned}"
