"""Execute a run exactly as its run.started record describes, and record the result.

The same function serves foreground runs (inside the CLI or MCP process) and
background runs (a detached `python -m irp.application.runner` process),
so both produce identical evidence. A heartbeat file shows the owner is alive;
a run whose heartbeat stops without a result is recorded as lost.

Usage: python -m irp.application.runner STUDY_DIR RUN_ID
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

from irp.application.evidence_log import utc_now
from irp.application.study import Study, open_study
from irp.domain.errors import IRPError, not_found
from irp.filesystem import atomic_write_text, sha256_file
from irp.providers.compute import local
from irp.providers.compute.modal import run_in_modal

HEARTBEAT_INTERVAL_S = 5.0
HEARTBEAT_STALE_S = 90.0
ARCHIVE_MAX_BYTES = 10 * 1024 * 1024
ARCHIVE_SUFFIXES = {
    ".json",
    ".jsonl",
    ".csv",
    ".tsv",
    ".txt",
    ".log",
    ".yaml",
    ".yml",
    ".md",
    ".out",
    ".tex",
}


def run_dir(study: Study, run_id: str) -> Path:
    return study.runs_dir / run_id


def heartbeat_path(study: Study, run_id: str) -> Path:
    return run_dir(study, run_id) / "heartbeat"


class Heartbeat:
    """Touch a file every few seconds while a run is owned by this process."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._beat, daemon=True)

    def __enter__(self) -> Heartbeat:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write()
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=HEARTBEAT_INTERVAL_S * 2)

    def _write(self) -> None:
        with contextlib.suppress(OSError):
            self.path.write_text(
                json.dumps({"pid": os.getpid(), "at": time.time()}), encoding="utf-8"
            )

    def _beat(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL_S):
            self._write()


def heartbeat_age(study: Study, run_id: str) -> float | None:
    path = heartbeat_path(study, run_id)
    try:
        beat = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return time.time() - float(beat.get("at", 0))


def _stream_record(study: Study, path: Path) -> dict[str, Any]:
    return {"path": study.rel(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _archive_outputs(study: Study, run_id: str, outputs: list[dict[str, Any]]) -> None:
    """Keep an immutable copy of small text outputs; later runs may overwrite code/ files."""
    archive_root = run_dir(study, run_id) / "outputs"
    for entry in outputs:
        source = study.root / entry["path"]
        if entry["bytes"] > ARCHIVE_MAX_BYTES or source.suffix.lower() not in ARCHIVE_SUFFIXES:
            entry["archived"] = None
            continue
        target = archive_root / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha256_file(target) != entry["sha256"]:
            # Changed between hashing and copying: keep no archive rather than a mismatched one.
            target.unlink()
            entry["archived"] = None
            continue
        entry["archived"] = study.rel(target)


def _exclude_new_outputs(
    code_dir: Path, before: dict[str, tuple[int, int]], outputs: list[dict[str, Any]]
) -> None:
    """Files a run creates are artifacts, not code: keep them out of the snapshot commits.

    They stay hashed in evidence and archived under runs/<id>/outputs. The list
    lives in .git/info/exclude, which is local to this repository and never committed.
    """
    exclude = code_dir / ".git" / "info" / "exclude"
    if not exclude.parent.is_dir():
        return
    created = sorted(
        entry["path"].removeprefix("code/")
        for entry in outputs
        if entry["path"].removeprefix("code/") not in before
    )
    if not created:
        return
    existing = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    known = set(existing.splitlines())
    additions = [f"/{path}" for path in created if f"/{path}" not in known]
    if not additions:
        return
    with exclude.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write("\n".join(additions) + "\n")


def execute_recorded_run(study: Study, run_id: str, *, actor: str) -> dict[str, Any]:
    state = study.state()
    run = state.runs.get(run_id)
    if run is None:
        raise not_found("run", run_id)
    if run.completed is not None:
        return run.completed
    spec = run.started
    directory = run_dir(study, run_id)
    directory.mkdir(parents=True, exist_ok=True)
    stdout_path = directory / "stdout.txt"
    stderr_path = directory / "stderr.txt"
    with Heartbeat(heartbeat_path(study, run_id)):
        if spec.get("compute", "local") == "local":
            completed = _execute_local(study, spec, stdout_path, stderr_path)
        else:
            completed = _execute_modal(study, spec, stdout_path, stderr_path)
    completed["run_id"] = run_id
    study.log.append("run.completed", completed, actor=actor)
    return completed


def _execute_local(
    study: Study, spec: dict[str, Any], stdout_path: Path, stderr_path: Path
) -> dict[str, Any]:
    code_dir = study.code_dir
    before = local.snapshot_tree(code_dir)
    env = dict(os.environ)
    env.update(spec.get("env_vars", {}))
    prefix = [str(study.root / p) for p in spec.get("path_prefix", [])]
    if prefix:
        env["PATH"] = os.pathsep.join([*prefix, env.get("PATH", "")])
    if "VIRTUAL_ENV_REL" in spec:
        env["VIRTUAL_ENV"] = str(study.root / spec["VIRTUAL_ENV_REL"])
    cwd = (code_dir / spec.get("cwd", ".")).resolve()
    result = local.execute_process(
        spec["launcher"],
        cwd=cwd,
        env=env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_s=spec.get("timeout_s"),
    )
    outputs, truncated = local.changed_files(code_dir, before, prefix="code")
    _archive_outputs(study, spec["id"], outputs)
    _exclude_new_outputs(code_dir, before, outputs)
    return {
        "status": result.status,
        "exit_code": result.exit_code,
        "signal": result.signal,
        "started_at": result.started_at,
        "ended_at": result.ended_at,
        "duration_s": result.duration_s,
        "max_rss_bytes": result.max_rss_bytes,
        "stdout": _stream_record(study, stdout_path),
        "stderr": _stream_record(study, stderr_path),
        "outputs": outputs,
        "outputs_truncated": truncated,
        "error": result.error,
        "hardware": local.hardware_facts()
        if spec.get("isolation") != "container"
        else _container_hardware(spec),
    }


def _container_hardware(spec: dict[str, Any]) -> dict[str, Any]:
    facts = local.hardware_facts()
    facts["container"] = True
    facts["gpu_requested"] = "--gpus" in spec.get("launcher", [])
    return facts


def _execute_modal(
    study: Study, spec: dict[str, Any], stdout_path: Path, stderr_path: Path
) -> dict[str, Any]:
    started_at = utc_now()
    start = time.monotonic()
    work_dir = run_dir(study, spec["id"]) / "modal"
    modal_spec = {
        "app_name": "irp",
        "python": spec["python"],
        "requirements": str(study.root / spec["requirements"])
        if spec.get("requirements")
        else None,
        "code_dir": str(study.code_dir),
        "command": spec["command"],
        "gpu": spec["gpu"],
        "gpu_count": spec["gpu_count"],
        "timeout_s": spec["timeout_s"],
        "outputs": spec.get("outputs", []),
    }
    try:
        result = run_in_modal(modal_spec, work_dir, spec["timeout_s"])
        error = result.get("error")
    except IRPError as exc:
        result, error = {"status": "error", "exit_code": None, "outputs": {}}, exc.message
    stdout_path.write_text(result.get("stdout") or "", encoding="utf-8")
    stderr_path.write_text(result.get("stderr") or "", encoding="utf-8")
    outputs: list[dict[str, Any]] = []
    for relative, payload in sorted(result.get("outputs", {}).items()):
        if "base64" not in payload:
            continue
        target = run_dir(study, spec["id"]) / "outputs" / "code" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(payload["base64"]))
        outputs.append(
            {
                "path": f"code/{relative}",
                "sha256": sha256_file(target),
                "bytes": target.stat().st_size,
                "archived": study.rel(target),
                "remote": True,
            }
        )
    status = result.get("status", "error")
    return {
        "status": status if status in ("succeeded", "failed") else "error",
        "exit_code": result.get("exit_code"),
        "signal": None,
        "started_at": started_at,
        "ended_at": utc_now(),
        "duration_s": round(time.monotonic() - start, 3),
        "max_rss_bytes": None,
        "stdout": _stream_record(study, stdout_path),
        "stderr": _stream_record(study, stderr_path),
        "outputs": outputs,
        "outputs_truncated": False,
        "error": error,
        "hardware": {"provider": "modal", "gpus": [f"{spec['gpu']} x{spec['gpu_count']}"]},
        "cost_usd": None,
        "client_log": study.rel(work_dir / "modal-client.log")
        if (work_dir / "modal-client.log").exists()
        else None,
    }


def mark_lost_runs(study: Study, *, actor: str) -> list[str]:
    """Record a result for runs whose owner stopped beating without one."""
    lost = []
    for run_id, run in study.state().runs.items():
        if run.completed is not None:
            continue
        age = heartbeat_age(study, run_id)
        started_long_ago = _started_age(run.started) > HEARTBEAT_STALE_S
        if (age is None and started_long_ago) or (age is not None and age > HEARTBEAT_STALE_S):
            directory = run_dir(study, run_id)
            directory.mkdir(parents=True, exist_ok=True)
            for name in ("stdout.txt", "stderr.txt"):
                (directory / name).touch(exist_ok=True)
            study.log.append(
                "run.completed",
                {
                    "run_id": run_id,
                    "status": "error",
                    "exit_code": None,
                    "signal": None,
                    "started_at": run.started.get("requested_at"),
                    "ended_at": utc_now(),
                    "duration_s": None,
                    "max_rss_bytes": None,
                    "stdout": _stream_record(study, directory / "stdout.txt"),
                    "stderr": _stream_record(study, directory / "stderr.txt"),
                    "outputs": [],
                    "outputs_truncated": False,
                    "error": "The process that owned this run stopped without recording a result. Its "
                    "command may still be running; check your process list before starting it again.",
                    "hardware": None,
                },
                actor=actor,
            )
            lost.append(run_id)
    return lost


def _started_age(spec: dict[str, Any]) -> float:
    from datetime import datetime

    try:
        started = datetime.fromisoformat(str(spec.get("requested_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    return time.time() - started.timestamp()


def write_runner_marker(study: Study, run_id: str, pid: int) -> None:
    atomic_write_text(
        run_dir(study, run_id) / "runner.json",
        json.dumps({"pid": pid, "started_at": utc_now()}) + "\n",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: python -m irp.application.runner STUDY_DIR RUN_ID\n")
        return 2
    study = open_study(argv[0])
    try:
        execute_recorded_run(study, argv[1], actor="runner")
    except IRPError as exc:
        sys.stderr.write(json.dumps({"error": exc.to_dict()}) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
