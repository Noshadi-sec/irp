"""File primitives shared by providers and workflows: hashing, atomic writes, locks, containment."""

from __future__ import annotations

import contextlib
import hashlib
import os
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

from irp.domain.errors import ErrorCode, IRPError

LOCK_TIMEOUT_S = 60.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write beside the target, fsync, then rename over it so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            with contextlib.suppress(OSError):
                temp.chmod(path.stat().st_mode & 0o7777)
        temp.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            temp.unlink()
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


@contextlib.contextmanager
def file_lock(lock_path: Path, timeout_s: float = LOCK_TIMEOUT_S) -> Iterator[None]:
    """Exclusive advisory lock shared by the CLI, the MCP server and background runners."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                _try_lock(handle)
                break
            except OSError as exc:
                if time.monotonic() > deadline:
                    raise IRPError(
                        ErrorCode.EXECUTION_FAILURE,
                        f"Timed out waiting for {lock_path}.",
                        remediation="Another IRP process is writing to this study; retry when it finishes.",
                    ) from exc
                time.sleep(0.05)
        yield
    finally:
        with contextlib.suppress(OSError):
            _unlock(handle)
        handle.close()


if sys.platform == "win32":
    import msvcrt

    def _try_lock(handle: object) -> None:
        handle.seek(0)  # type: ignore[attr-defined]
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]

    def _unlock(handle: object) -> None:
        handle.seek(0)  # type: ignore[attr-defined]
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]

else:
    import fcntl

    def _try_lock(handle: object) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]

    def _unlock(handle: object) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]


def contained_path(base: Path, relative: str, *, what: str) -> Path:
    """Resolve `relative` under `base`, refusing absolute paths and escapes (including via symlinks)."""
    if not relative or Path(relative).is_absolute():
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"{what} must be a relative path inside {base.name}/, got {relative!r}.",
        )
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"{what} {relative!r} points outside {base.name}/.",
        ) from exc
    return candidate


def posix_relative(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()
