"""Unpack an arXiv source download without trusting its contents.

arXiv serves a gzipped tar for multi-file submissions, a gzipped single file
for one-file submissions, and a PDF when no source exists. Members that escape
the destination, links, devices and oversized archives are refused rather than
"cleaned up".
"""

from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from irp.domain.errors import ErrorCode, IRPError

MAX_MEMBERS = 5000
MAX_TOTAL_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class Unpacked:
    kind: str  # "tar", "gzip-single", "zip", "pdf", "tex"
    files: list[str]


def detect_kind(content: bytes) -> str:
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"\x1f\x8b"):
        return "gzip"
    if content.startswith(b"PK\x03\x04"):
        return "zip"
    if b"\\documentclass" in content[:20000] or b"\\begin{document}" in content:
        return "tex"
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:"):
            return "tar"
    except (tarfile.TarError, EOFError):
        return "unknown"


def _safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise IRPError(
            ErrorCode.PAPER_UNAVAILABLE,
            f"The source archive contains an unsafe path: {name!r}.",
            remediation="Download the source yourself, inspect it, and pass the directory.",
        )
    return path


def _refuse(detail: str) -> IRPError:
    return IRPError(
        ErrorCode.PAPER_UNAVAILABLE,
        f"The source archive was refused: {detail}",
        remediation="Download the source yourself, inspect it, and pass the directory.",
    )


def unpack_source(content: bytes, destination: Path) -> Unpacked:
    """Extract into `destination` (which must be empty) and list the files written."""
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError(f"{destination} is not empty")
    kind = detect_kind(content)
    if kind == "pdf":
        return Unpacked(kind="pdf", files=[])
    if kind == "tex":
        (destination / "main.tex").write_bytes(content)
        return Unpacked(kind="tex", files=["main.tex"])
    if kind == "zip":
        return _unpack_zip(content, destination)
    if kind == "gzip":
        try:
            raw = gzip.decompress(content)
        except (OSError, EOFError) as exc:
            raise _refuse(f"corrupt gzip data ({exc})") from exc
        if len(raw) > MAX_TOTAL_BYTES:
            raise _refuse("larger than 512 MiB uncompressed")
        try:
            archive = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")  # noqa: SIM115 - closed by _unpack_tar
        except (tarfile.TarError, EOFError):
            (destination / "main.tex").write_bytes(raw)
            return Unpacked(kind="gzip-single", files=["main.tex"])
        return _unpack_tar(archive, destination)
    if kind == "tar":
        archive = tarfile.open(fileobj=io.BytesIO(content), mode="r:")  # noqa: SIM115 - closed by _unpack_tar
        return _unpack_tar(archive, destination)
    raise _refuse("unrecognized format")


def _unpack_tar(archive: tarfile.TarFile, destination: Path) -> Unpacked:
    written: list[str] = []
    total = 0
    with archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS:
            raise _refuse(f"more than {MAX_MEMBERS} members")
        for member in members:
            if member.isdir():
                continue
            if not member.isfile():
                # Links, devices and FIFOs never belong in paper source.
                continue
            relative = _safe_relative(member.name)
            total += member.size
            if total > MAX_TOTAL_BYTES:
                raise _refuse("larger than 512 MiB uncompressed")
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            with extracted, target.open("wb") as handle:
                handle.write(extracted.read())
            written.append(relative.as_posix())
    return Unpacked(kind="tar", files=sorted(written))


def _unpack_zip(content: bytes, destination: Path) -> Unpacked:
    written: list[str] = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise _refuse(f"more than {MAX_MEMBERS} members")
        for info in infos:
            if info.is_dir():
                continue
            relative = _safe_relative(info.filename)
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise _refuse("larger than 512 MiB uncompressed")
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as handle:
                handle.write(source.read())
            written.append(relative.as_posix())
    return Unpacked(kind="zip", files=sorted(written))
