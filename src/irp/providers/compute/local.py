"""Run one command on this machine and keep the receipts.

Output streams go straight to files (no pipes to fill up), the command gets its
own process group so a timeout stops every descendant, and `wait4` reports the
run's peak memory on POSIX. Files the run creates or changes are hashed so a
number extracted later can be tied to the run that wrote it.
"""

from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from irp.filesystem import sha256_file

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}
MAX_OUTPUT_FILES = 2000
MAX_HASHED_BYTES = 4 * 1024**3
TERMINATE_GRACE_S = 10.0
POLL_S = 0.2


@dataclass
class ExecutionResult:
    status: str  # succeeded | failed | timeout | cancelled | error
    exit_code: int | None
    signal: int | None
    started_at: str
    ended_at: str
    duration_s: float
    max_rss_bytes: int | None
    error: str | None


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    """Size and mtime of every regular file under `root`, skipping caches and VCS data."""
    snapshot: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return snapshot
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for name in filenames:
            path = Path(directory) / name
            try:
                stat = path.lstat()
            except OSError:
                continue
            if not path.is_symlink() and path.is_file():
                snapshot[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def changed_files(
    root: Path, before: dict[str, tuple[int, int]], prefix: str
) -> tuple[list[dict[str, Any]], bool]:
    """Hash files that are new or changed since `before`; returns (files, truncated)."""
    after = snapshot_tree(root)
    changed = sorted(path for path, meta in after.items() if before.get(path) != meta)
    files: list[dict[str, Any]] = []
    hashed = 0
    truncated = False
    for relative in changed:
        if len(files) >= MAX_OUTPUT_FILES:
            truncated = True
            break
        size = after[relative][0]
        if hashed + size > MAX_HASHED_BYTES:
            truncated = True
            continue
        path = root / relative
        try:
            digest = sha256_file(path)
        except OSError:
            continue
        hashed += size
        files.append({"path": f"{prefix}/{relative}", "sha256": digest, "bytes": size})
    return files, truncated


def gpu_names() -> list[str]:
    """GPU models reported by nvidia-smi; empty when there is none or it is absent."""
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return []
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def hardware_facts() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "gpus": gpu_names(),
    }


def _maxrss_bytes(maxrss: int) -> int:
    # Linux reports kilobytes, macOS reports bytes.
    return maxrss if sys.platform == "darwin" else maxrss * 1024


def execute_process(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_s: float | None,
) -> ExecutionResult:
    """Run `argv` to completion, timeout or interruption, writing both streams to files."""
    started_at = now_iso()
    start = time.monotonic()
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=sys.platform != "win32",
            )
        except OSError as exc:
            return ExecutionResult(
                status="error",
                exit_code=None,
                signal=None,
                started_at=started_at,
                ended_at=now_iso(),
                duration_s=time.monotonic() - start,
                max_rss_bytes=None,
                error=f"Could not start the command: {exc}",
            )
        status, exit_code, signal_number, rss = _wait(process, start, timeout_s)
    return ExecutionResult(
        status=status,
        exit_code=exit_code,
        signal=signal_number,
        started_at=started_at,
        ended_at=now_iso(),
        duration_s=round(time.monotonic() - start, 3),
        max_rss_bytes=rss,
        error=None if status in ("succeeded", "failed") else f"run ended: {status}",
    )


def _reap(process: subprocess.Popen[bytes]) -> tuple[bool, int | None]:
    """Non-blocking reap. Only this function waits on the child, so wait4 sees its usage."""
    if hasattr(os, "wait4"):
        try:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        except ChildProcessError:
            return True, None
        if pid == 0:
            return False, None
        process.returncode = os.waitstatus_to_exitcode(status)
        return True, _maxrss_bytes(usage.ru_maxrss)
    return process.poll() is not None, None


def _signal_group(process: subprocess.Popen[bytes], sig: int) -> None:
    if sys.platform == "win32":
        process.kill()
        return
    try:
        os.killpg(process.pid, sig)
    except (ProcessLookupError, PermissionError):
        return


def _wait(
    process: subprocess.Popen[bytes], start: float, timeout_s: float | None
) -> tuple[str, int | None, int | None, int | None]:
    """Wait for exit; on timeout or Ctrl-C, SIGTERM the group and SIGKILL after a grace period."""
    stop_reason: str | None = None
    terminated_at: float | None = None
    killed = False
    rss: int | None = None
    while True:
        try:
            exited, rss = _reap(process)
            if exited:
                break
            now = time.monotonic()
            if stop_reason is None and timeout_s is not None and now - start > timeout_s:
                stop_reason = "timeout"
                _signal_group(process, signal.SIGTERM)
                terminated_at = now
            if terminated_at is not None and not killed and now - terminated_at > TERMINATE_GRACE_S:
                _signal_group(process, getattr(signal, "SIGKILL", signal.SIGTERM))
                killed = True
            time.sleep(POLL_S)
        except KeyboardInterrupt:
            if stop_reason is None:
                stop_reason = "cancelled"
                _signal_group(process, signal.SIGTERM)
                terminated_at = time.monotonic()
    code = process.returncode
    signal_number = -code if code is not None and code < 0 else None
    exit_code = code if code is not None and code >= 0 else None
    if stop_reason is not None:
        return stop_reason, exit_code, signal_number, rss
    return ("succeeded" if code == 0 else "failed"), exit_code, signal_number, rss


def shell_argv(command: str) -> list[str]:
    if sys.platform == "win32":
        return ["cmd.exe", "/d", "/c", command]
    return ["/bin/sh", "-c", command]
